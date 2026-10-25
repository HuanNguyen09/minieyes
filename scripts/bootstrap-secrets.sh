#!/usr/bin/env bash
# Create the Kubernetes Secrets the GitOps repo expects, from values kept in SSM Parameter Store
# (/minieyes/*, SecureString). Missing values are generated once, so re-running after a rebuild
# reuses the same credentials. Nothing is printed. Run on the dev box.
#
#   scripts/bootstrap-secrets.sh cloud   # current kubectl context = EKS
#   scripts/bootstrap-secrets.sh edge    # current kubectl context = edge k3s
set -euo pipefail
export AWS_REGION=${AWS_REGION:-ap-southeast-1} AWS_PAGER=""
target=${1:?usage: bootstrap-secrets.sh cloud|edge}

param() {  # name -> value, generated and stored on first use
  local name=/minieyes/$1 value
  if ! value=$(aws ssm get-parameter --name "$name" --with-decryption \
                 --query Parameter.Value --output text 2>/dev/null); then
    value=$(openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 32)
    aws ssm put-parameter --name "$name" --type SecureString --value "$value" \
      --tags Key=Project,Value=minieyes >/dev/null
  fi
  printf %s "$value"
}

namespace() {  # name pod-security-level
  kubectl create namespace "$1" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl label namespace "$1" --overwrite \
    "pod-security.kubernetes.io/enforce=$2" "pod-security.kubernetes.io/warn=${3:-$2}" >/dev/null
}

secret() {  # namespace name key=value...
  local ns=$1 name=$2; shift 2
  local args=(); for kv in "$@"; do args+=(--from-literal="$kv"); done
  kubectl -n "$ns" create secret generic "$name" "${args[@]}" --dry-run=client -o yaml \
    | kubectl apply -f - >/dev/null
  echo "secret $ns/$name"
}

site_key=$(param site-01/api-key)
push_password=$(param push-password)

case "$target" in
  cloud)
    namespace minieyes restricted
    namespace monitoring privileged baseline
    pg=$(param cloud/postgres-password)
    digest=$(printf %s "$site_key" | sha256sum | cut -d' ' -f1)
    secret minieyes event-api-secrets \
      "postgres-password=$pg" \
      "database-url=postgresql+psycopg://minieyes:$pg@event-api-postgres:5432/minieyes" \
      "api-keys={\"site-01\": \"$digest\"}"
    secret monitoring push-basic-auth "users=edge:$(openssl passwd -apr1 "$push_password")"
    secret monitoring grafana-admin admin-user=admin "admin-password=$(param cloud/grafana-password)"
    # Telegram: set /minieyes/cloud/telegram-bot-token to the real token, then re-run
    secret monitoring alertmanager-telegram "bot-token=$(param cloud/telegram-bot-token)"
    ;;
  edge)
    namespace minieyes restricted
    namespace monitoring privileged baseline
    secret minieyes detector-api-key "api-key=$site_key"
    secret monitoring alloy-push-credentials username=edge "password=$push_password"
    ;;
  *) echo "unknown target $target" >&2; exit 1 ;;
esac
