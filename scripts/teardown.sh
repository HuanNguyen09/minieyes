#!/usr/bin/env bash
# Tear the lab down and prove nothing billable is left (#39). Run on the dev box, only when the
# owner asks. Keeps infra/terraform/bootstrap (state bucket, budgets) and the dev box.
#
#   scripts/teardown.sh --check   # only list what is still billable
#   scripts/teardown.sh --yes     # destroy, then list
#
# Order matters: Kubernetes-created AWS resources (Traefik's NLB, EBS volumes of PVCs) are not in
# Terraform state and would block `terraform destroy` of the VPC, so they go first.
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION=${AWS_REGION:-ap-southeast-1} AWS_PAGER=""
BUCKET=${BUCKET:-minieyes-tfstate-$(aws sts get-caller-identity --query Account --output text)}

leftovers() {
  echo "== still billable (tagged Project=minieyes or owned by the cluster):"
  aws ec2 describe-volumes --filters Name=tag:Project,Values=minieyes \
    --query 'Volumes[].[VolumeId,Size,State]' --output text | sed 's/^/volume /'
  aws ec2 describe-volumes --filters Name=tag-key,Values=kubernetes.io/cluster/minieyes-lab \
    --query 'Volumes[].[VolumeId,Size,State]' --output text | sed 's/^/pvc-volume /'
  aws elbv2 describe-load-balancers --query 'LoadBalancers[].[LoadBalancerName,DNSName]' \
    --output text | grep -i '^a[0-9a-f]\{31\}' | sed 's/^/load-balancer /' || true
  aws ec2 describe-addresses --filters Name=tag:Project,Values=minieyes \
    --query 'Addresses[].[PublicIp,AllocationId,InstanceId]' --output text | sed 's/^/eip /'
  aws ec2 describe-nat-gateways --filter Name=tag:Project,Values=minieyes Name=state,Values=available \
    --query 'NatGateways[].NatGatewayId' --output text | sed 's/^/nat /'
  aws eks list-clusters --query 'clusters' --output text | tr '\t' '\n' | grep minieyes | sed 's/^/eks /' || true
  echo "== (dev box EIP minieyes-devbox and the bootstrap bucket are kept on purpose)"
}

case "${1:-}" in
  --check) leftovers; exit 0 ;;
  --yes) ;;
  *) echo "usage: teardown.sh --check | --yes" >&2; exit 2 ;;
esac

cloud=$(kubectl config get-contexts -o name | grep minieyes-lab || true)
if [ -n "$cloud" ] && kubectl --context "$cloud" get ns argocd >/dev/null 2>&1; then
  echo "1/4 removing GitOps roots (Argo CD deletes the apps, Traefik's NLB with them)"
  kubectl --context "$cloud" -n argocd delete application cloud-root --wait=true --timeout=10m || true
  kubectl --context "$cloud" -n traefik delete svc --all --timeout=5m || true
  echo "2/4 deleting PVCs so their EBS volumes are released"
  kubectl --context "$cloud" delete pvc --all -A --timeout=5m || true
  for _ in $(seq 1 30); do
    aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName' --output text \
      | grep -qi '^a[0-9a-f]\{31\}' || break
    sleep 10
  done
fi

echo "3/4 terraform destroy envs/lab-platform, then envs/lab"
for env in lab-platform lab; do
  terraform -chdir="infra/terraform/envs/$env" init -input=false -reconfigure \
    -backend-config="bucket=$BUCKET" >/dev/null
  terraform -chdir="infra/terraform/envs/$env" destroy -input=false -auto-approve
done

echo "4/4 verification"
leftovers
