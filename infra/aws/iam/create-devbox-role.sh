#!/usr/bin/env bash
# Run once in AWS CloudShell (ap-southeast-1) as an admin:
#   git clone https://github.com/HuanNguyen09/minieyes && bash minieyes/infra/aws/iam/create-devbox-role.sh
# Creates the two deployer policies, the dev-box role and its instance profile. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

ROLE=DevBox-MiniEyes-Claude          # deliberately NOT minieyes-*: the role must not be able to edit itself
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

create_policy() {  # name file
  local arn="arn:aws:iam::${ACCOUNT}:policy/$1"
  if aws iam get-policy --policy-arn "$arn" >/dev/null 2>&1; then
    # keep at most 5 versions: drop the oldest non-default one before adding a new default
    old=$(aws iam list-policy-versions --policy-arn "$arn" \
      --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text | awk '{print $NF}')
    [ "$(aws iam list-policy-versions --policy-arn "$arn" --query 'length(Versions)')" -ge 5 ] \
      && aws iam delete-policy-version --policy-arn "$arn" --version-id "$old"
    aws iam create-policy-version --policy-arn "$arn" --policy-document "file://$2" --set-as-default >/dev/null
    echo "updated $1"
  else
    aws iam create-policy --policy-name "$1" --policy-document "file://$2" >/dev/null
    echo "created $1"
  fi
}

create_policy MiniEyesDeployerInfra deployer-infra.json
create_policy MiniEyesDeployerIam deployer-iam.json

aws iam get-role --role-name "$ROLE" >/dev/null 2>&1 \
  || aws iam create-role --role-name "$ROLE" \
       --assume-role-policy-document file://devbox-trust.json \
       --description "Dev box where Claude Code runs Terraform/Docker for MiniEyes" >/dev/null
for arn in \
  "arn:aws:iam::${ACCOUNT}:policy/MiniEyesDeployerInfra" \
  "arn:aws:iam::${ACCOUNT}:policy/MiniEyesDeployerIam" \
  "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"; do
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn "$arn"
done

aws iam get-instance-profile --instance-profile-name "$ROLE" >/dev/null 2>&1 || {
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
}
echo "done: launch the dev box with instance profile $ROLE and tag minieyes:protect=true"
