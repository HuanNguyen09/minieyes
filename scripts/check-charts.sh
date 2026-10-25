#!/usr/bin/env bash
# helm-unittest, helm lint and kubeconform for every chart with its cloud/edge values.
set -euo pipefail
cd "$(dirname "$0")/.."
K8S_VERSION=${K8S_VERSION:-1.33.0}
# Argo CD, cert-manager and Traefik CRDs
CRD_SCHEMAS='https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'

declare -A ENV_OF=([event-api]=cloud [platform]=cloud [detector]=edge [triton]=edge [camera-sim]=edge)
for chart in "${!ENV_OF[@]}"; do
  values="deploy/values/${ENV_OF[$chart]}/$chart.yaml"
  echo "== $chart ($values)"
  helm-unittest "charts/$chart"
  helm lint --strict "charts/$chart" -f "$values"
  helm template "$chart" "charts/$chart" -f "$values" --namespace minieyes \
    | kubeconform -strict -summary -kubernetes-version "$K8S_VERSION"         -schema-location default -schema-location "$CRD_SCHEMAS" -
done
