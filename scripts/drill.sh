#!/usr/bin/env bash
# Helpers for the failure drills (docs/drills.md). Run on the dev box with the lab up.
#
#   scripts/drill.sh alerts                       # firing alerts right now
#   scripts/drill.sh wait CameraDown firing 600   # block until the alert fires (or times out)
#   scripts/drill.sh wait CameraDown resolved 600
#
# Evidence is printed as "<UTC time> <alert> <state> <labels>", read from Prometheus through the
# Kubernetes API proxy, so no port is exposed.
set -euo pipefail
cloud=$(kubectl config get-contexts -o name | grep minieyes-lab)

prom() {  # url-encoded PromQL -> JSON
  kubectl --context "$cloud" get --raw \
    "/api/v1/namespaces/monitoring/services/kube-prometheus-stack-prometheus:9090/proxy/api/v1/query?query=$1"
}

firing() {  # [alertname] -> one line per firing alert
  local q='ALERTS%7Balertstate%3D%22firing%22%7D'
  [ -n "${1:-}" ] && q="ALERTS%7Balertstate%3D%22firing%22%2Calertname%3D%22$1%22%7D"
  prom "$q" | python3 -c '
import json, sys
for r in json.load(sys.stdin)["data"]["result"]:
    m = r["metric"]
    labels = ",".join(f"{k}={v}" for k, v in sorted(m.items())
                      if k not in ("__name__", "alertname", "alertstate", "prometheus"))
    print(m["alertname"], labels)'
}

case "${1:-}" in
  alerts) firing ;;
  wait)
    name=$2 state=$3 timeout=${4:-900} start=$(date +%s)
    while :; do
      lines=$(firing "$name" || true)
      if { [ "$state" = firing ] && [ -n "$lines" ]; } || { [ "$state" = resolved ] && [ -z "$lines" ]; }; then
        echo "$(date -u +%H:%M:%S)Z $name $state after $(( $(date +%s) - start ))s ${lines#"$name "}"
        exit 0
      fi
      [ $(( $(date +%s) - start )) -ge "$timeout" ] && { echo "$(date -u +%H:%M:%S)Z $name NOT $state within ${timeout}s"; exit 1; }
      sleep 15
    done ;;
  *) echo "usage: drill.sh alerts | wait <alert> firing|resolved [timeout]" >&2; exit 2 ;;
esac
