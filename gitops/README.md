# minieyes-gitops

Desired state of every MiniEyes cluster. Argo CD in each cluster pulls its own directory
([ADR-002](https://github.com/HuanNguyen09/minieyes/blob/main/docs/adr/002-pull-gitops-for-edge.md));
nothing pushes to a cluster.

```text
clusters/cloud/        Argo CD on EKS (installed by Terraform) syncs root.yaml -> apps/
  apps/                platform (Traefik, cert-manager, TLS ingresses), event-api,
                       kube-prometheus-stack, loki, minieyes-observability
  values/              per-environment values for app-repo charts
sites/site-01/         Argo CD on the edge k3s node (installed by Ansible)
  apps/                camera-sim, triton, detector, kube-state-metrics, alloy
  values/
```

## How a release reaches a site

1. A merge to `main` in the app repo builds images tagged with the full commit SHA and pushes
   them to ECR.
2. CI commits that SHA here, in two places that must stay equal: the chart `targetRevision` in
   `apps/<app>.yaml` and the image tag in `values/<app>.yaml`. Code, chart and image always move
   together.
3. Argo CD on each cluster sees the commit and syncs; `selfHeal` reverts manual `kubectl edit`
   and `prune` deletes what was removed from Git.

Rollback is `git revert` of the bump commit.

## Namespaces

`minieyes` enforces Pod Security **restricted** (every chart passes it, see the app repo's
`tests/policy`). `monitoring` is **privileged** with a baseline warning: node-exporter (cloud)
and Alloy's hostPath WAL (edge) need host access.

## Secrets (never in this repo)

| Secret | Namespace | Keys |
|---|---|---|
| `event-api-secrets` | minieyes (cloud) | `database-url`, `api-keys`, `postgres-password` |
| `detector-api-key` | minieyes (edge) | `api-key` |
| `push-basic-auth` | monitoring (cloud) | `users` (htpasswd) |
| `alloy-push-credentials` | monitoring (edge) | `username`, `password` |
| `alertmanager-telegram`, `grafana-admin` | monitoring (cloud) | see observability/README.md |
