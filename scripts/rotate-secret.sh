#!/usr/bin/env bash
# Rotate a secret end to end (ADR-006). Run on the dev box with the lab up.
#
#   scripts/rotate-secret.sh site-api-key     # edge detector <-> Event API key
#   scripts/rotate-secret.sh push-password    # Alloy -> metrics./logs. basic auth
#
# Steps: new random value in SSM -> Secrets in the cloud and edge clusters -> rollout restart of
# the consumers -> verification (new value accepted, old value rejected).
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION=${AWS_REGION:-ap-southeast-1} AWS_PAGER=""
DOMAIN=${DOMAIN:-13-229-14-139.sslip.io}
what=${1:?usage: rotate-secret.sh site-api-key|push-password}

case "$what" in
  site-api-key) name=/minieyes/site-01/api-key ;;
  push-password) name=/minieyes/push-password ;;
  *) echo "unknown secret $what" >&2; exit 1 ;;
esac

old=$(aws ssm get-parameter --name "$name" --with-decryption --query Parameter.Value --output text)
new=$(openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 32)
aws ssm put-parameter --name "$name" --type SecureString --value "$new" --overwrite >/dev/null
echo "1/4 new value stored in $name (version $(aws ssm get-parameter --name "$name" --query Parameter.Version --output text))"

cloud=$(kubectl config get-contexts -o name | grep minieyes-lab)
kubectl config use-context "$cloud" >/dev/null && bash scripts/bootstrap-secrets.sh cloud >/dev/null
kubectl config use-context edge-01 >/dev/null && bash scripts/bootstrap-secrets.sh edge >/dev/null
kubectl config use-context "$cloud" >/dev/null
echo "2/4 Secrets updated in both clusters"

if [ "$what" = site-api-key ]; then
  kubectl -n minieyes rollout restart deploy/event-api >/dev/null
  kubectl -n minieyes rollout status deploy/event-api --timeout=180s >/dev/null
  kubectl --context edge-01 -n minieyes rollout restart deploy/detector >/dev/null
else
  kubectl --context edge-01 -n monitoring rollout restart ds/alloy >/dev/null
fi
echo "3/4 consumers restarted"

if [ "$what" = site-api-key ]; then
  code() { curl -s -o /dev/null -w '%{http_code}' -H "X-API-Key: $1" "https://events.$DOMAIN/events?limit=1"; }
  [ "$(code "$new")" = 200 ] && [ "$(code "$old")" = 401 ] \
    && echo "4/4 verified: new key 200, old key 401" \
    || { echo "4/4 verification FAILED" >&2; exit 1; }
else
  code() { curl -s -o /dev/null -w '%{http_code}' -u "edge:$1" -X POST "https://metrics.$DOMAIN/api/v1/write"; }
  # a valid login reaches Prometheus (400/415 for an empty body); a wrong one stops at Traefik (401)
  [ "$(code "$new")" != 401 ] && [ "$(code "$old")" = 401 ] \
    && echo "4/4 verified: new password accepted, old password 401" \
    || { echo "4/4 verification FAILED" >&2; exit 1; }
fi
