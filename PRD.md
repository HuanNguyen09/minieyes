# MiniEyes — Product Requirements Document

| | |
|---|---|
| **Owner** | Nguyen Van Huan |
| **Status** | Approved, in progress |
| **Timeline** | 2 weeks (14 days), November 2026 |
| **Repo** | `HuanNguyen09/minieyes` (app + infra) · `HuanNguyen09/minieyes-gitops` (deployment config) |

## 1. Summary

MiniEyes detects people entering a configured **danger zone ("red zone")** in a camera feed and raises alerts. A detector at the **edge** reads an RTSP stream, runs **YOLOv8n on NVIDIA Triton Inference Server** and sends events to a **cloud** API. The platform is deployed with **Terraform, Ansible, Helm and Argo CD** on **AWS (EKS + EC2/k3s)** and observed with **Prometheus, Grafana, Loki and Alertmanager → Telegram**.

The product is a learning and portfolio vehicle for an edge-AI DevOps role. The AI is intentionally small; the value is in the platform: automation, delivery, observability and failure handling.

## 2. Goals

1. A person walking into a red zone produces an event in the cloud and a Telegram message within **10 seconds** (event) and **2 minutes** (alert).
2. All infrastructure is reproducible from code: `terraform apply` + `ansible-playbook` + Git push rebuild the whole system from zero.
3. Changes reach the edge **only through Git** (pull-based GitOps); no `kubectl apply` against edge in normal operation.
4. Every failure in the drill list (§9) is **detected by an alert** and has a **runbook**.
5. Core logic is built **test-first** (see §8); CI blocks merges on failing tests, lint or critical vulnerabilities.

## 3. Non-goals

- Training or fine-tuning models; accuracy beyond a pretrained YOLOv8n.
- GPU inference (CPU Triton is sufficient; GPU is discussed in docs only).
- Multi-tenant auth, user management, a custom web UI (Grafana is the UI).
- Production-grade HA (single node edge, small EKS). Trade-offs are documented.
- Real camera hardware or real personal video data.

## 4. Users and scenarios

| Persona | Need |
|---|---|
| **Site safety manager** | Get notified when someone enters a danger zone; see event history per camera. |
| **Platform/DevOps engineer** (the owner) | Roll out a new detector version to all sites safely, see fleet health on one dashboard, get paged only for actionable problems, recover quickly. |

Key scenarios:
1. *Intrusion:* person enters zone → event stored → dashboard updates → Telegram alert (de-duplicated by cooldown).
2. *Release:* merge to `main` → image built, scanned, pushed → tag committed to GitOps repo → Argo CD rolls out at the edge → rollback by `git revert`.
3. *Incident:* camera stream dies / Triton OOMs / edge loses connectivity → one actionable alert with a runbook link.

## 5. Functional requirements

### 5.1 Camera simulator (`apps/camera-sim`)
- FR-CAM-1 Serve a looping sample video as RTSP at `rtsp://<host>:8554/cam1`, 5 fps, 640×360 or larger.
- FR-CAM-2 Restart automatically if ffmpeg exits; expose a healthcheck.

### 5.2 Model serving (`apps/triton`)
- FR-TRI-1 Triton serves `yolov8n` (ONNX Runtime backend, CPU) from a model repository with `config.pbtxt`.
- FR-TRI-2 A reproducible script exports `yolov8n.onnx` (input `images` 1×3×640×640 FP32, output 1×84×8400).
- FR-TRI-3 Health (`/v2/health/ready`, port 8000), gRPC (8001) and metrics (8002) are reachable.

### 5.3 Detector (`apps/detector`)
- FR-DET-1 **Frame source:** read frames from RTSP on a background thread that keeps **only the latest frame** (stale frames are dropped so latency never accumulates when inference is slower than the stream); on failure reconnect with exponential backoff (base 1 s, cap 30 s, jitter); expose `minieyes_camera_up{camera}`.
- FR-DET-2 **Preprocess:** letterbox to 640×640, RGB, CHW, float32 [0,1]; keep the scale/padding to map boxes back.
- FR-DET-3 **Inference client:** abstract `InferenceClient`; Triton gRPC implementation with timeout and readiness check.
- FR-DET-4 **Postprocess:** decode YOLOv8 output, keep class `person`, confidence ≥ threshold (default 0.4), NMS (IoU 0.5), map boxes to original frame coordinates.
- FR-DET-5 **Zone rule:** zones are polygons in frame pixel coordinates loaded from YAML; a detection is *inside* when its **bottom-centre point** (feet) is inside the polygon. Invalid config fails fast with a clear error.
- FR-DET-6 **Debounce/cooldown:** raise an intrusion only after **N consecutive frames** (default 2) inside the zone; then suppress repeats for the same `(camera, zone)` for a **cooldown** (default 10 s).
- FR-DET-7 **Event publishing:** POST events to the Event API with an idempotency key and the site's API key in the `X-API-Key` header; retry with backoff; buffer up to 1,000 events in memory while the API is down; drop oldest when full and count drops.
- FR-DET-8 **Observability:** Prometheus metrics (§7.2), JSON logs with `camera`, `zone`, `event_id`; `/healthz` and `/metrics` HTTP endpoints.

### 5.4 Event API (`apps/event-api`)
- FR-API-1 `POST /events` requires a valid `X-API-Key` (one key per site, `401` otherwise), validates and stores an event; repeated `event_id` returns `200` without duplicating (idempotent), first insert returns `201`.
- FR-API-2 `GET /events` filters by `site`, `camera`, `zone`, time range; paginated, newest first.
- FR-API-3 `GET /healthz` (process alive), `GET /readyz` (DB reachable), `GET /metrics`.
- FR-API-4 PostgreSQL in deployed environments; schema managed by migrations.

Event schema:

```json
{
  "event_id": "uuid",
  "site": "site-01",
  "camera": "cam1",
  "zone": "forklift-lane",
  "type": "red_zone_intrusion",
  "confidence": 0.82,
  "bbox": [x1, y1, x2, y2],
  "occurred_at": "2026-11-03T08:15:02Z"
}
```

### 5.5 Platform
- FR-PLT-1 **Terraform** (`infra/terraform`): S3 remote state (versioned, encrypted, public access blocked); `cloud-vpc` and `site-vpc` with no peering; EKS with a Spot managed node group; ECR repos with scan-on-push; EKS add-on `aws-ebs-csi-driver` (Pod Identity) with a default `gp3` StorageClass; EKS public API endpoint restricted to the admin CIDR; edge EC2 (**m6i.large** — non-burstable CPU for sustained inference — gp3 40 GB, EIP, IMDSv2, SSH only from the admin CIDR, **instance profile with ECR read-only**); GitHub OIDC roles: a **push role** trusted only for `refs/heads/main` and a **read-only plan role** for pull requests; Argo CD installed on EKS via the Helm provider.
- FR-PLT-2 **Ansible** (`infra/ansible`): roles `common` (updates, SSH hardening, ufw), `k3s` (installed with `--disable traefik --disable servicelb`, kubelet configured with **`ecr-credential-provider`** so pulls from private ECR use the instance profile instead of 12-hour tokens), `node_exporter`, `argocd` (deploy key for the GitOps repo from Ansible Vault if the repo is private); second run reports **zero changes**.
- FR-PLT-3 **Helm** (`charts/`): one chart per service with probes, resources, non-root `securityContext`, configurable via values per environment/site.
- FR-PLT-4 **CI** (GitHub Actions): on PR — lint, unit tests, build, Trivy (fail on CRITICAL), `helm lint`/unittest, `terraform fmt/validate/test`, `promtool test rules`; on `main` — push images to ECR (tag = git SHA, skipped if the immutable tag already exists) via OIDC and commit the tag to the GitOps repo using a dedicated deploy key / GitHub App token with write access to that repo only.
- FR-PLT-5 **GitOps** (`minieyes-gitops`): App of Apps for `clusters/cloud` and `sites/site-01`; `selfHeal` and `prune` enabled.
- FR-PLT-6 **Observability:** kube-prometheus-stack on EKS with remote-write receiver; Loki on EKS (single binary, PVC storage); at the edge a **single Grafana Alloy agent** scrapes metrics (detector, Triton, node_exporter, kube-state-metrics deployed at the edge) and ships pod logs, adding `site` as an external label; Grafana dashboards and alert rules stored as code; Alertmanager → Telegram with grouping and inhibition.
- FR-PLT-8 **Ingress & TLS:** Traefik ingress controller on EKS behind one Network Load Balancer, cert-manager with Let's Encrypt. Hostnames live under `var.base_domain` — default `<nlb-ip>.sslip.io` (HTTP-01), or a Cloudflare-managed domain via DNS-01 when available. Exposed hosts: `events.` (Event API, API key), `metrics.` (remote-write, basic auth), `logs.` (Loki push, basic auth), `grafana.` (Grafana login). NLB source ranges allow only the edge EIP and the admin CIDR.
- FR-PLT-7 **Security:** no plaintext secrets in Git (External Secrets + AWS Secrets Manager, or Sealed Secrets); default-deny NetworkPolicies; Pod Security `restricted` where possible; gitleaks in CI.

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | End-to-end event latency (frame → stored) p95 < 10 s on CPU at 5 fps. |
| NFR-2 | Detector survives camera and API outages without crashing; resumes automatically. |
| NFR-3 | Images run as non-root; detector image < 500 MB; no CRITICAL CVEs at merge. |
| NFR-4 | Edge requires outbound HTTPS only; no inbound ports except SSH from one IP. |
| NFR-5 | Unit test suite runs in < 60 s with no network or Docker; coverage ≥ 80 % for `detector` and `event-api` domain code. |
| NFR-6 | Cost ≤ 100 USD of AWS credit for the whole project; `terraform destroy` leaves no billable leftovers. |

## 7. Architecture and interfaces

See [README](README.md#architecture) for diagrams and [ADRs](docs/adr/).

### 7.1 Detector internal design (ports and adapters)

```text
FrameSource ──▶ Preprocessor ──▶ InferenceClient ──▶ Postprocessor ──▶ ZoneEvaluator ──▶ Debouncer ──▶ EventPublisher
 (RTSP / fake)                    (Triton / fake)                       (pure)           (pure, Clock)   (HTTP / fake)
```

Pure domain modules (`zones`, `postprocess`, `debounce`, `backoff`) have no I/O and are tested exhaustively. Adapters (`rtsp`, `triton`, `http`) sit behind interfaces with in-memory fakes so the pipeline can be tested end-to-end without network.

### 7.2 Metrics contract

| Metric | Type | Labels |
|---|---|---|
| `minieyes_camera_up` | gauge | `camera` |
| `minieyes_frames_total` | counter | `camera` |
| `minieyes_frames_dropped_total` | counter | `camera` |
| `minieyes_inference_seconds` | histogram | — (one Triton client serves all cameras) |
| `minieyes_detections_total` | counter | `camera` |
| `minieyes_events_total` | counter | `camera`, `zone` |
| `minieyes_events_dropped_total` | counter | `reason` |
| `minieyes_publish_failures_total` | counter | — |

### 7.3 Alert contract

| Alert | Condition (summary) | For |
|---|---|---|
| `CameraDown` | `minieyes_camera_up == 0` | 1m |
| `DetectorDown` | detector scrape target down (`up{job="detector"} == 0`): a detector that cannot start exposes no `minieyes_*` series | 2m |
| `LowFPS` | frame rate < 2 fps while camera up | 5m |
| `HighInferenceLatency` | p95 `minieyes_inference_seconds` > 0.5 s | 5m |
| `PodCrashLooping` | restarts increase > 3 in 15m | 0m |
| `DiskWillFillIn24h` | `predict_linear` of free bytes < 0 in 24h | 30m |
| `DiskAlmostFull` | less than 15 % free (kubelet evicts at 10 %); catches sudden fills the 24h trend misses | 5m |
| `EdgeSiteSilent` | site seen in the last hour but sending nothing now: `group by (site) (max_over_time(up[1h])) unless group by (site) (up)` | 5m |

`EdgeSiteSilent` inhibits all other alerts with the same `site`. Because remote-written series stay visible for the 5-minute lookback after the last sample, expect detection about **10 minutes** after a site goes dark; this is acceptable for the lab and documented in the runbook.

## 8. Engineering approach: test-first

Work is split into GitHub issues; each issue lists **behaviours to drive with tests**. Use the `/tdd` skill in Claude Code per issue: write one failing test for one behaviour, make it pass with the simplest code, refactor, repeat.

| Layer | Test tool | Runs in CI |
|---|---|---|
| Python domain + adapters (fakes) | `pytest` | ✅ |
| Event API | `pytest` + FastAPI `TestClient`, SQLite for unit, Postgres via testcontainers (`-m integration`) | ✅ unit, integration on demand |
| Helm charts | `helm lint`, `helm-unittest` | ✅ |
| Kubernetes manifests | `kubeconform` | ✅ |
| Terraform | `terraform validate`, `terraform test` (plan-only with mock providers), `tflint`, `trivy config` | ✅ |
| Ansible | `ansible-lint`, Molecule (Docker) with idempotence check | ✅ (lint), Molecule locally |
| Alert rules | `promtool test rules` | ✅ |
| Alertmanager routing | `amtool check-config`, `amtool config routes test` | ✅ |
| End-to-end | `pytest -m e2e` against docker compose | locally / nightly |

## 9. Failure drills (acceptance for the platform)

| # | Fault injected | Must be detected by |
|---|---|---|
| 1 | Stop camera-sim | `CameraDown` |
| 2 | Triton memory limit 200Mi | OOMKilled, `PodCrashLooping` |
| 3 | Non-existent image tag in GitOps repo | Argo CD Degraded, ImagePullBackOff |
| 4 | Artificial delay in detector | `HighInferenceLatency`, `LowFPS` |
| 5 | Fill edge disk | `DiskWillFillIn24h` |
| 6 | Remove egress from edge Security Group | `EdgeSiteSilent` (others inhibited) |
| 7 | Manual `kubectl edit` on edge | Argo CD OutOfSync → self-heal |
| 8 | Delete a resource block in Terraform | `terraform plan` shows destroy; `prevent_destroy` blocks state bucket |

## 10. Milestones

| Milestone | Days | Exit criteria |
|---|---|---|
| **M0 Foundation** | 1 | Tooling, test harness, budget alarms |
| **M1 App** | 2–4 | `docker compose up` → intrusion event stored; e2e test green |
| **M2 Kubernetes** | 5 | Helm charts pass unittest; stack runs on local k3d |
| **M3 Infrastructure** | 6–7 | `terraform apply` builds EKS + edge; Ansible idempotent |
| **M4 Delivery** | 8–9 | Merge → running at edge in ≤ 10 min with no manual `kubectl` |
| **M5 Observability** | 10–11 | Camera stop → Telegram alert ≤ 2 min; rule tests green |
| **M6 Hardening** | 12–14 | Secrets/NetworkPolicy done; 8 drills + runbooks; teardown verified |

Cut order if behind: HPA/load test → Terraform plan-on-PR → External Secrets (use Sealed Secrets) → drills 8 → 5. **Never cut:** Terraform EKS, Argo CD, Prometheus + alerts to Telegram.

## 11. Success metrics

- All Must issues in M1–M5 closed; CI green on `main`.
- Drill table: 8/8 detected, 8 runbooks written.
- Demo video (≤ 3 min) showing intrusion → Telegram, release via Git, rollback via `git revert`.
- AWS spend ≤ 100 USD; zero billable resources after teardown.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Triton image size (> 10 GB) slows builds/pulls | Pin one tag, pre-pull on edge, 40 GB disk; fall back to ONNX Runtime in-process behind the same `InferenceClient` |
| CPU inference too slow | 5 fps, single camera, YOLOv8n |
| EKS destroy blocked by Kubernetes-created load balancers | Uninstall ingress/LoadBalancer services before `terraform destroy`; checklist in docs |
| Hidden AWS costs | Budget alarms; no NAT Gateway; teardown checklist |
| Scope vs 2 weeks (test-first effort is ~70–80 h, not 55–60 h) | Cut order in §10; `priority:should` issues are the first to go |
| Burstable CPU throttling inference | Edge uses m6i.large, not t3 |
| Edge cannot pull from private ECR (12-hour tokens) | Instance profile + kubelet `ecr-credential-provider` |

## 13. Licensing notes

YOLOv8 (Ultralytics) is AGPL-3.0; it is used here in a public, open-source personal project. Sample video must be royalty-free.
