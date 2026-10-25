#!/usr/bin/env bash
# Park and resume the lab without destroying it. Run on the dev box.
#
#   scripts/lab-power.sh down     # EKS nodes -> 0, stop the edge (control plane, NLB, EBS stay)
#   scripts/lab-power.sh up       # start the edge, EKS nodes -> 3, reopen the edge tunnel
#   scripts/lab-power.sh status
#
# Postgres and Loki keep their EBS volumes while nodes are at zero. Terraform keeps min_size=1,
# so a later `terraform plan` shows that change; `up` restores it.
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION=${AWS_REGION:-ap-southeast-1} AWS_PAGER=""
CLUSTER=minieyes-lab
NODEGROUP=minieyes-lab-spot
NODES=${NODES:-3}
DOMAIN=${DOMAIN:-13-229-14-139.sslip.io}

edge_id() {
  aws ec2 describe-instances --filters Name=tag:Name,Values=minieyes-edge \
    Name=instance-state-name,Values=pending,running,stopping,stopped \
    --query 'Reservations[0].Instances[0].InstanceId' --output text
}
cloud() { kubectl config use-context "$(kubectl config get-contexts -o name | grep "$CLUSTER")" >/dev/null; }

down() {
  aws eks update-nodegroup-config --cluster-name "$CLUSTER" --nodegroup-name "$NODEGROUP" \
    --scaling-config minSize=0,maxSize="$NODES",desiredSize=0 >/dev/null
  echo "EKS node group -> 0"
  aws ec2 stop-instances --instance-ids "$(edge_id)" >/dev/null
  echo "edge stopping"
  pkill -f "ssh .*-L 16443:127.0.0.1:6443" || true
}

up() {
  local id; id=$(edge_id)
  aws ec2 start-instances --instance-ids "$id" >/dev/null
  aws eks update-nodegroup-config --cluster-name "$CLUSTER" --nodegroup-name "$NODEGROUP" \
    --scaling-config minSize=1,maxSize=$((NODES + 1)),desiredSize="$NODES" >/dev/null
  echo "edge starting, EKS node group -> $NODES"
  aws ec2 wait instance-running --instance-ids "$id"
  aws eks wait nodegroup-active --cluster-name "$CLUSTER" --nodegroup-name "$NODEGROUP"
  cloud
  for _ in $(seq 1 60); do
    [ "$(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready')" -ge "$NODES" ] && break
    sleep 10
  done
  sleep 30  # sshd and k3s on the edge
  bash scripts/edge-kubeconfig.sh >/dev/null && echo "edge tunnel open (context edge-01)"
  status
}

status() {
  cloud
  echo "== cloud nodes"; kubectl get nodes --no-headers 2>/dev/null | awk '{print $1, $2}' || true
  echo "== cloud apps"
  kubectl -n argocd get applications --no-headers \
    -o custom-columns=APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status || true
  echo "== edge pods"
  kubectl --context edge-01 -n minieyes get pods --no-headers 2>/dev/null | awk '{print $1, $3}' \
    || echo "(edge tunnel closed: scripts/edge-kubeconfig.sh)"
  echo "== https://events.$DOMAIN/healthz: $(curl -s -o /dev/null -w '%{http_code}' "https://events.$DOMAIN/healthz" || true)"
}

"${1:?usage: lab-power.sh down|up|status}"
