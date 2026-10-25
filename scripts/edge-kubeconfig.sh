#!/usr/bin/env bash
# kubectl access to the edge k3s from the dev box. The k3s API is not exposed (the security
# group allows SSH from the admin CIDR only), so it is reached through an SSH tunnel.
#
#   scripts/edge-kubeconfig.sh            # opens the tunnel, writes context "edge-01"
#   kubectl --context edge-01 get pods -A
set -euo pipefail
cd "$(dirname "$0")/.."
EDGE_HOST=${EDGE_HOST:-$(terraform -chdir=infra/terraform/envs/lab output -raw edge_public_ip)}
KEY=${KEY:-$HOME/.ssh/minieyes-edge}
PORT=${PORT:-16443}

if ! ss -ltn | grep -q ":$PORT "; then
  ssh -i "$KEY" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -fN \
    -L "$PORT:127.0.0.1:6443" "ubuntu@$EDGE_HOST"
fi

cfg=$(mktemp)
ssh -i "$KEY" "ubuntu@$EDGE_HOST" sudo cat /etc/rancher/k3s/k3s.yaml \
  | sed -e "s#https://127.0.0.1:6443#https://127.0.0.1:$PORT#" \
        -e "s/: default$/: edge-01/" > "$cfg"
KUBECONFIG="$HOME/.kube/config:$cfg" kubectl config view --flatten > "$HOME/.kube/config.new"
mv "$HOME/.kube/config.new" "$HOME/.kube/config" && chmod 600 "$HOME/.kube/config" && rm -f "$cfg"
kubectl --context edge-01 get nodes
