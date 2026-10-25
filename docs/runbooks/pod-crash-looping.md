# Runbook: PodCrashLooping

**Severity:** critical · **Rule:** `increase(kube_pod_container_status_restarts_total[15m]) > 3` · **Drill:** #2 (Triton memory limit 200Mi)

## Meaning
A container restarted more than 3 times in 15 minutes. `site="cloud"` means a pod on EKS; any other `site` is an edge pod.

## First checks
1. `kubectl -n <namespace> describe pod <pod>` → *Last State* reason: `OOMKilled`, `Error`, exit code.
2. Previous logs: `kubectl -n <namespace> logs <pod> -c <container> --previous`, or Loki `{site="<site>", namespace="<namespace>"}`.
3. Argo CD: was a new image or values change just synced?

## Fix
- `OOMKilled` → raise the memory limit in the chart values (Triton with YOLOv8n needs far more than 200Mi).
- Crash on start (config, missing Secret, bad image) → fix it or `git revert` the change in the GitOps repo.
- Failing liveness probe → check the probe path and timeouts against the app's `/healthz`.
