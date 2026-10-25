#!/usr/bin/env bash
# One-time bootstrap with an ADMIN profile. Creates only lower-privileged identities and the dev
# box; afterwards the admin key can be deleted.
#
#   AWS_PROFILE=minieyes-admin bash infra/aws/devbox/bootstrap.sh
#
# Creates (idempotent):
#   - Boundary/Deployer policies + role/instance profile DevBox-MiniEyes-Claude (../iam)
#   - IAM user operator-minieyes (start/stop + SSM shell on the dev box only, Bedrock denied);
#     its key is written straight into the local profile "minieyes-operator", never printed
#   - security group minieyes-devbox (no inbound rules) in the default VPC
#   - the dev box: Ubuntu 24.04, t3.xlarge, 100 GB gp3 (encrypted), IMDSv2, tag minieyes:role=devbox
set -euo pipefail
cd "$(dirname "$0")"
export AWS_REGION=ap-southeast-1 AWS_DEFAULT_REGION=ap-southeast-1 AWS_PAGER=""

OPERATOR=operator-minieyes
OPERATOR_POLICY=Operator-MiniEyes-DevBox
PROFILE_ROLE=DevBox-MiniEyes-Claude
INSTANCE_TYPE=${INSTANCE_TYPE:-t3.xlarge}

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "account $ACCOUNT as $(aws sts get-caller-identity --query Arn --output text)"

echo "== deployer policies, boundary and dev-box role"
bash ../iam/create-devbox-role.sh

echo "== operator user (laptop: start/stop + shell on the dev box, nothing else)"
policy_arn="arn:aws:iam::${ACCOUNT}:policy/${OPERATOR_POLICY}"
if aws iam get-policy --policy-arn "$policy_arn" >/dev/null 2>&1; then
  if [ "$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'length(Versions)')" -ge 5 ]; then
    old=$(aws iam list-policy-versions --policy-arn "$policy_arn" \
      --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text | awk '{print $NF}')
    aws iam delete-policy-version --policy-arn "$policy_arn" --version-id "$old"
  fi
  aws iam create-policy-version --policy-arn "$policy_arn" \
    --policy-document file://operator-policy.json --set-as-default >/dev/null
else
  aws iam create-policy --policy-name "$OPERATOR_POLICY" --policy-document file://operator-policy.json >/dev/null
fi
aws iam get-user --user-name "$OPERATOR" >/dev/null 2>&1 || aws iam create-user --user-name "$OPERATOR" >/dev/null
aws iam attach-user-policy --user-name "$OPERATOR" --policy-arn "$policy_arn"
if [ -z "$(aws configure get aws_access_key_id --profile minieyes-operator 2>/dev/null || true)" ]; then
  key=$(aws iam create-access-key --user-name "$OPERATOR" \
          --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text)
  aws configure set aws_access_key_id "$(cut -f1 <<<"$key")" --profile minieyes-operator
  aws configure set aws_secret_access_key "$(cut -f2 <<<"$key")" --profile minieyes-operator
  aws configure set region ap-southeast-1 --profile minieyes-operator
  unset key
  echo "operator key stored in profile minieyes-operator"
fi

echo "== dedicated dev-box network (public subnet, no NAT; nothing else of the account is touched)"
tag() { echo "ResourceType=$1,Tags=[{Key=Name,Value=minieyes-devbox}]"; }
vpc=$(aws ec2 describe-vpcs --filters Name=tag:Name,Values=minieyes-devbox --query 'Vpcs[0].VpcId' --output text)
if [ "$vpc" = "None" ]; then
  vpc=$(aws ec2 create-vpc --cidr-block 10.250.0.0/24 --tag-specifications "$(tag vpc)" \
          --query Vpc.VpcId --output text)
  aws ec2 wait vpc-available --vpc-ids "$vpc"
  aws ec2 modify-vpc-attribute --vpc-id "$vpc" --enable-dns-hostnames
  igw=$(aws ec2 create-internet-gateway --tag-specifications "$(tag internet-gateway)" \
          --query InternetGateway.InternetGatewayId --output text)
  aws ec2 attach-internet-gateway --vpc-id "$vpc" --internet-gateway-id "$igw"
  subnet=$(aws ec2 create-subnet --vpc-id "$vpc" --cidr-block 10.250.0.0/26 \
             --availability-zone ap-southeast-1a --tag-specifications "$(tag subnet)" \
             --query Subnet.SubnetId --output text)
  aws ec2 modify-subnet-attribute --subnet-id "$subnet" --map-public-ip-on-launch
  rt=$(aws ec2 create-route-table --vpc-id "$vpc" --tag-specifications "$(tag route-table)" \
         --query RouteTable.RouteTableId --output text)
  aws ec2 create-route --route-table-id "$rt" --destination-cidr-block 0.0.0.0/0 --gateway-id "$igw" >/dev/null
  aws ec2 associate-route-table --route-table-id "$rt" --subnet-id "$subnet" >/dev/null
fi
subnet=$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$vpc" --query 'Subnets[0].SubnetId' --output text)

echo "== security group without inbound rules"
sg=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values="$vpc" Name=group-name,Values=minieyes-devbox \
       --query 'SecurityGroups[0].GroupId' --output text)
if [ "$sg" = "None" ]; then
  sg=$(aws ec2 create-security-group --vpc-id "$vpc" --group-name minieyes-devbox \
         --description "MiniEyes dev box: no inbound, SSM only" --query GroupId --output text)
fi

echo "== dev box"
instance=$(aws ec2 describe-instances \
  --filters Name=tag:minieyes:role,Values=devbox Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
if [ "$instance" = "None" ]; then
  ami=$(aws ssm get-parameter \
    --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
    --query Parameter.Value --output text)
  for attempt in 1 2 3 4 5 6; do  # a new instance profile takes a few seconds to propagate
    instance=$(aws ec2 run-instances --image-id "$ami" --instance-type "$INSTANCE_TYPE" \
      --iam-instance-profile Name="$PROFILE_ROLE" --security-group-ids "$sg" --subnet-id "$subnet" \
      --metadata-options HttpTokens=required,HttpPutResponseHopLimit=1,HttpEndpoint=enabled \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=100,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}' \
      --user-data file://user-data.sh \
      --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=minieyes-devbox},{Key=minieyes:role,Value=devbox}]' \
                           'ResourceType=volume,Tags=[{Key=Name,Value=minieyes-devbox}]' \
      --query 'Instances[0].InstanceId' --output text) && break
    echo "launch failed (often a new instance profile not visible yet), retrying ($attempt)"; sleep 10
  done
  [ -n "$instance" ] && [ "$instance" != "None" ] || { echo "could not launch the dev box" >&2; exit 1; }
fi
aws ec2 wait instance-running --instance-ids "$instance"
echo "dev box $instance running; tools install takes ~5 min (/var/log/minieyes-devbox.log)"
echo "next: delete the admin access key; connect with Session Manager"
