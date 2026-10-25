#!/usr/bin/env bash
# Local two-cluster lab (#20): "cloud" (event-api + Postgres) and "edge-01" (camera-sim, OVMS as
# "triton", detector), a shared registry, Pod Security restricted and NetworkPolicies enforced
# by k3s. API servers bind 127.0.0.1 (host.docker.internal can resolve to a LAN address on
# Windows). Needs docker, k3d, kubectl, helm, and the model exported (triton/scripts/export_model.py).
#
#   scripts/k3d.sh up | images | deploy | check | down
set -euo pipefail
cd "$(dirname "$0")/.."

REGISTRY=minieyes-registry
REG_PORT=15000
IN_CLUSTER=k3d-$REGISTRY:$REG_PORT
DEMO_KEY=demo-site-01-key
CLOUD=k3d-cloud
EDGE=k3d-edge-01

up() {
  k3d registry list | grep -q "$REGISTRY" || k3d registry create "$REGISTRY" --port "$REG_PORT"
  k3d cluster list | grep -q '^cloud ' || k3d cluster create cloud \
    --api-port 127.0.0.1:26443 --servers 1 --agents 0 --registry-use "$IN_CLUSTER" \
    -p "18081:30081@server:0" --k3s-arg "--disable=traefik@server:0" --wait
  k3d cluster list | grep -q '^edge-01 ' || k3d cluster create edge-01 \
    --api-port 127.0.0.1:26444 --servers 1 --agents 0 --registry-use "$IN_CLUSTER" \
    --k3s-arg "--disable=traefik@server:0" --wait
}

images() {
  docker build -q -f apps/detector/Dockerfile -t minieyes-detector:dev .
  docker build -q -f apps/event-api/Dockerfile -t minieyes-event-api:dev .
  docker build -q -t minieyes-camera-sim:dev camera-sim
  docker build -q -f triton/Dockerfile.model -t minieyes-model-yolov8n:dev triton
  for image in minieyes-detector minieyes-event-api minieyes-camera-sim minieyes-model-yolov8n; do
    docker tag "$image:dev" "localhost:$REG_PORT/$image:dev"
    docker push -q "localhost:$REG_PORT/$image:dev"
  done
}

restricted_namespace() {  # context
  kubectl --context "$1" create namespace minieyes --dry-run=client -o yaml | kubectl --context "$1" apply -f -
  kubectl --context "$1" label namespace minieyes --overwrite \
    pod-security.kubernetes.io/enforce=restricted pod-security.kubernetes.io/warn=restricted
}

secret() {  # context name key=value...
  local ctx=$1 name=$2; shift 2
  local args=(); for kv in "$@"; do args+=(--from-literal="$kv"); done
  kubectl --context "$ctx" -n minieyes create secret generic "$name" "${args[@]}" \
    --dry-run=client -o yaml | kubectl --context "$ctx" apply -f -
}

deploy() {
  local pw digest
  pw=$(kubectl --context "$CLOUD" -n minieyes get secret event-api-secrets \
         -o jsonpath='{.data.postgres-password}' 2>/dev/null | base64 -d || true)
  pw=${pw:-$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')}
  digest=$(printf %s "$DEMO_KEY" | sha256sum | cut -d' ' -f1)

  restricted_namespace "$CLOUD"
  secret "$CLOUD" event-api-secrets \
    "postgres-password=$pw" \
    "database-url=postgresql+psycopg://minieyes:$pw@event-api-postgres:5432/minieyes" \
    "api-keys={\"site-01\": \"$digest\"}"
  helm --kube-context "$CLOUD" upgrade --install event-api charts/event-api -n minieyes \
    -f deploy/k3d/cloud-event-api.yaml --wait --timeout 10m
  kubectl --context "$CLOUD" apply -f deploy/k3d/nodeport.yaml

  restricted_namespace "$EDGE"
  secret "$EDGE" detector-api-key "api-key=$DEMO_KEY"
  kubectl --context "$EDGE" apply -f deploy/k3d/edge-inference.yaml
  helm --kube-context "$EDGE" upgrade --install camera-sim charts/camera-sim -n minieyes \
    -f deploy/k3d/edge-camera-sim.yaml --wait
  helm --kube-context "$EDGE" upgrade --install detector charts/detector -n minieyes \
    -f deploy/k3d/edge-detector.yaml --wait --timeout 5m
}

check() {
  kubectl --context "$CLOUD" -n minieyes get pods
  kubectl --context "$EDGE" -n minieyes get pods
  curl -s -H "X-API-Key: $DEMO_KEY" "http://localhost:18081/events?limit=3"; echo
}

down() {
  k3d cluster delete cloud edge-01 || true
  k3d registry delete "$REGISTRY" || true
}

"${1:?usage: k3d.sh up|images|deploy|check|down}"
