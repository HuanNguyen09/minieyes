#!/usr/bin/env bash
# Run once in AWS CloudShell (ap-southeast-1) as an admin (not root):
#   git clone https://github.com/HuanNguyen09/minieyes && bash minieyes/infra/aws/iam/create-devbox-role.sh
# Creates the workload boundary, the three deployer policies, the dev-box role and its
# instance profile. Safe to re-run: existing policies get a new default version.
set -euo pipefail
cd "$(dirname "$0")"

ROLE=DevBox-MiniEyes-Claude   # deliberately NOT minieyes-*: the role must not be able to edit itself
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
policy_arn() { echo "arn:aws:iam::${ACCOUNT}:policy/$1"; }

create_policy() {  # name file
  local arn
  arn=$(policy_arn "$1")
  if aws iam get-policy --policy-arn "$arn" >/dev/null 2>&1; then
    # IAM keeps at most 5 versions: drop the oldest non-default one first
    if [ "$(aws iam list-policy-versions --policy-arn "$arn" --query 'length(Versions)')" -ge 5 ]; then
      old=$(aws iam list-policy-versions --policy-arn "$arn" \
        --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text | awk '{print $NF}')
      aws iam delete-policy-version --policy-arn "$arn" --version-id "$old"
    fi
    aws iam create-policy-version --policy-arn "$arn" --policy-document "file://$2" --set-as-default >/dev/null
    echo "updated $1"
  else
    aws iam create-policy --policy-name "$1" --policy-document "file://$2" >/dev/null
    echo "created $1"
  fi
}

# the boundary must exist before any minieyes-* role can be created
create_policy Boundary-MiniEyes-Workload workload-boundary.json
create_policy Deployer-MiniEyes-Infra deployer-infra.json
create_policy Deployer-MiniEyes-Iam deployer-iam.json
create_policy Deployer-MiniEyes-Guardrails deployer-guardrails.json

aws iam get-role --role-name "$ROLE" >/dev/null 2>&1 \
  || aws iam create-role --role-name "$ROLE" \
       --assume-role-policy-document file://devbox-trust.json \
       --description "Dev box where Claude Code runs Terraform/Docker for MiniEyes" >/dev/null

# policies from an earlier version of this script, if they were ever attached
for old in MiniEyesDeployerInfra MiniEyesDeployerIam; do
  aws iam detach-role-policy --role-name "$ROLE" --policy-arn "$(policy_arn "$old")" 2>/dev/null || true
done

for arn in \
  "$(policy_arn Deployer-MiniEyes-Infra)" \
  "$(policy_arn Deployer-MiniEyes-Iam)" \
  "$(policy_arn Deployer-MiniEyes-Guardrails)" \
  "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"; do
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn "$arn"
done

aws iam get-instance-profile --instance-profile-name "$ROLE" >/dev/null 2>&1 || {
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
}
echo "done: launch the dev box with instance profile $ROLE (do NOT tag it Project=minieyes)"
