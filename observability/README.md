# observability/

Observability as code for MiniEyes (PRD FR-PLT-6, §7.2, §7.3, ADR-003). This
directory holds configuration only; deploying it is the GitOps repo's job
(`HuanNguyen09/minieyes-gitops`). This file says what each piece is and how it
is meant to be consumed.

```text
edge site (k3s)                                   cloud (EKS, namespace monitoring)
┌──────────────────────────────┐                 ┌──────────────────────────────────────────┐
│ detector  triton  node_exp.  │  remote_write   │ kube-prometheus-stack                     │
│ kube-state-metrics  pod logs │ ──────────────▶ │  Prometheus (remote-write receiver)       │
│        Grafana Alloy         │  metrics.<dom>  │   └ PrometheusRule minieyes ─▶ Alertmanager ─▶ Telegram
│  external label site=<site>  │ ──────────────▶ │  Grafana (dashboards via sidecar)         │
└──────────────────────────────┘  logs.<dom>     │ Loki (single binary, gp3 PVC)             │
                                                 └──────────────────────────────────────────┘
```

## Layout

| Path | What | Consumed by |
|---|---|---|
| `alerts/minieyes.rules.yaml` | Alert rules, PRD §7.3 (source of truth) | promtool tests; rendered into the PrometheusRule below |
| `alerts/tests/*.yaml` | promtool unit tests: fire and not-fire case per alert | `make test-rules`, CI |
| `kube-prometheus-stack/prometheusrule-minieyes.yaml` | **Generated** PrometheusRule CR wrapping the rules | `kustomization.yaml` |
| `scripts/build_prometheusrule.py` | Regenerates the CR (`--check` fails when stale) | developers, pytest |
| `kube-prometheus-stack/values.yaml` | Helm values for `prometheus-community/kube-prometheus-stack` on EKS | Argo CD Application (cloud) |
| `kube-prometheus-stack/servicemonitor-event-api.yaml` | ServiceMonitor for the Event API | `kustomization.yaml` |
| `alertmanager/alertmanager.yaml` | Alertmanager routing, grouping, inhibition, Telegram receiver | `kustomization.yaml` → Secret `alertmanager-minieyes` |
| `alertmanager/test.sh` | `amtool check-config` + `amtool config routes test` cases | `make test-rules`, CI |
| `kustomization.yaml` | Cloud extras: PrometheusRule, ServiceMonitor, Alertmanager config Secret | Argo CD Application (cloud), plain directory/kustomize source |
| `alloy/config.alloy` | Grafana Alloy pipeline for an edge site | `alloy/kustomization.yaml` → ConfigMap `alloy-config` |
| `alloy/values.yaml` | Helm values for `grafana/alloy` at the edge | Argo CD Application (site) |
| `alloy/kustomization.yaml` | Renders ConfigMap `alloy-config` from `config.alloy` | Argo CD Application (site) |
| `edge/kube-state-metrics-values.yaml` | Helm values for `prometheus-community/kube-state-metrics` at the edge | Argo CD Application (site) |
| `tests/` | pytest: rule structure, runbook links, Alertmanager grouping/inhibition (live) | `make test-rules` |

## Versions the values were rendered against

`helm template` succeeded with these chart versions (pin them in the Argo CD Applications):

| Chart | Version |
|---|---|
| `prometheus-community/kube-prometheus-stack` | 92.13.1 |
| `prometheus-community/kube-state-metrics` | 8.7.1 |
| `grafana/alloy` | 1.14.3 |
| `grafana/loki` | 7.5.0 |

`alloy validate` / `alloy fmt` were run with Grafana Alloy v1.20.1; promtool 2.55.1; amtool/Alertmanager 0.27.0.

## Cloud (EKS, namespace `monitoring`)

1. **kube-prometheus-stack** Application: chart above + `kube-prometheus-stack/values.yaml`.
   - `prometheus.prometheusSpec.enableRemoteWriteReceiver: true`; the ingress from #40 must expose
     **only** `/api/v1/write` of the Prometheus Service as `https://metrics.<base_domain>` with basic auth.
   - `externalLabels.site: cloud`, so alerts from cloud-only series also carry `site`.
   - Rule, ServiceMonitor and PodMonitor selectors are open (`*NilUsesHelmValues: false`).
   - Alertmanager reads its config from the Secret `alertmanager-minieyes` and mounts the Secret
     `alertmanager-telegram` at `/etc/alertmanager/secrets/alertmanager-telegram/`.
   - Grafana admin credentials come from the Secret `grafana-admin` (`admin-user`, `admin-password`).
2. **minieyes-observability** Application: this directory (`observability/`) as a kustomize source.
   It creates the PrometheusRule `minieyes`, the ServiceMonitor `event-api` and the Secret
   `alertmanager-minieyes` (from `alertmanager/alertmanager.yaml`; it contains no credentials).
3. **Secrets created outside Git** (External Secrets or Sealed Secrets, FR-PLT-7):

   | Secret (ns `monitoring`) | Keys | Used by |
   |---|---|---|
   | `alertmanager-telegram` | `bot-token` | Alertmanager `bot_token_file` |
   | `grafana-admin` | `admin-user`, `admin-password` | Grafana |
   | basic-auth Secret for the `metrics.` / `logs.` ingress | htpasswd | Traefik middleware (#40) |

4. **Telegram chat id**: `alertmanager.yaml` carries a placeholder `chat_id`. A chat id is not a
   credential, but it is environment specific: set it in the GitOps repo's copy (Alertmanager 0.27
   has no `chat_id_file`).

## Edge site (k3s, namespace `monitoring`)

1. **kube-state-metrics** Application: chart above + `edge/kube-state-metrics-values.yaml`
   (Service `kube-state-metrics`, port name `http`).
2. **alloy** Application, two sources: the `grafana/alloy` chart with `alloy/values.yaml`, and the
   `alloy/` directory as kustomize source for the ConfigMap `alloy-config`. Per site, override
   `MINIEYES_SITE` and `MINIEYES_BASE_DOMAIN` (env in `alloy.extraEnv`).
3. **Secret** `alloy-push-credentials` (keys `username`, `password`), created outside Git; the same
   credentials authenticate to `metrics.` and `logs.`.

What Alloy scrapes, and the contract the charts must keep:

| Job | Discovery | Requirement on the workload |
|---|---|---|
| `detector` | pods | label `app.kubernetes.io/name: detector`, container port **named `metrics`** |
| `triton` | pods | label `app.kubernetes.io/name: triton`, container port **8002** (FR-TRI-3) |
| `node` | nodes | node_exporter on the host at `<InternalIP>:9100` (Ansible role); ufw must allow the pod CIDR |
| `kube-state-metrics` | services | Service label `app.kubernetes.io/name: kube-state-metrics`, port `http` |

Every sample is remote-written with the external label `site=<MINIEYES_SITE>`. The WAL lives on a
hostPath (`/var/lib/alloy`) so samples buffered during an outage survive an Alloy restart (up to 8 h).

## Tests

```bash
make test-rules
# or, without make:
promtool check rules observability/alerts/*.rules.yaml
promtool test rules observability/alerts/tests/*.yaml
bash observability/alertmanager/test.sh
uv run --no-project --with pytest --with pyyaml pytest observability -q
```

The live Alertmanager tests in `tests/test_alertmanager.py` run when an `alertmanager` binary is on
`PATH` and are skipped otherwise. After editing `alerts/*.rules.yaml`, regenerate the CR:

```bash
uv run --no-project --with pyyaml python observability/scripts/build_prometheusrule.py
```

Config checks that need extra binaries (run by hand or in CI):

```bash
alloy fmt observability/alloy/config.alloy   # prints the formatted file; must equal the original
MINIEYES_SITE=site-01 MINIEYES_BASE_DOMAIN=example.test MINIEYES_PUSH_USER=edge \
  alloy validate observability/alloy/config.alloy
kubectl kustomize observability/ && kubectl kustomize observability/alloy
helm template kps prometheus-community/kube-prometheus-stack --version 92.13.1 \
  -f observability/kube-prometheus-stack/values.yaml >/dev/null
```
