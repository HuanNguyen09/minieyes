# Failure drills (#38)

Each drill: break one thing on purpose, watch the alert fire (screenshot of Grafana/Alertmanager
or the Telegram message), follow the runbook linked from the alert's `runbook_url`, restore,
watch it resolve. Commands run on the dev box (`scripts/devbox.sh '...'`) with the lab up
(`scripts/lab-power.sh up`). Argo CD self-heals manual changes within ~3 minutes, which is
itself drill 7; for longer drills make the change in the GitOps repo instead.

| # | Drill | How | Expected | Status |
|---|---|---|---|---|
| 1 | Camera down | `kubectl --context edge-01 -n minieyes scale deploy camera-sim --replicas=0` | `minieyes_camera_up=0` in < 30 s, **CameraDown** after 1 m ([runbook](runbooks/camera-down.md)) | Behaviour verified by e2e (`camera_up` 0 → 1, compose and dev box); alert screenshot pending |
| 2 | Triton OOMKilled | GitOps: `sites/site-01/values/triton.yaml` → `resources.limits.memory: 64Mi` | pod `OOMKilled`, **PodCrashLooping**, detector logs `inference failed, frame skipped` | pending (lab up) |
| 3 | Bad image tag | GitOps: `sites/site-01/values/detector.yaml` → `image.tag: deadbeef` | `ImagePullBackOff`; with `Recreate` no detector runs, so `minieyes_camera_up` disappears and **CameraDown cannot fire**. Found while writing this drill: new **DetectorDown** (`up{job="detector"}==0` for 2 m, [runbook](runbooks/detector-down.md)); fix = `git revert` | pending |
| 4 | Latency regression | GitOps: triton `resources.limits.cpu: 200m` | **HighInferenceLatency** (p95 > 0.5 s for 5 m), **LowFPS** | pending |
| 5 | Edge disk filling | on the edge: `fallocate -l 30G /var/tmp/fill` | **DiskWillFillIn24h** ([runbook](runbooks/disk-will-fill-in-24h.md)); clean up with `rm` | pending |
| 6 | Edge loses egress | on the edge: `sudo iptables -I OUTPUT -p tcp --dport 443 -j REJECT` for 5 min | **EdgeSiteSilent** after ~10 min; no event lost once restored | Event-loss half verified: e2e "API down 30 s → stored = events_total − dropped" passes (compose and dev box) |
| 7 | Manual drift self-healed | `kubectl --context edge-01 -n minieyes scale deploy detector --replicas=0` | Argo CD shows OutOfSync then restores 1 replica in ≤ 3 min | pending (selfHeal is enabled on every Application) |
| 8 | Destructive Terraform plan caught | change `node_instance_types` | plan says `must be replaced`; `terraform-plan.yaml` calls it out on the PR | Seen for real on 2026-10-25: `module.eks.aws_eks_node_group.spot must be replaced` was read and accepted deliberately before apply; PR comment needs the CI scope |

Postmortem of a real incident: [2026-10-25 first cloud deploy](postmortems/2026-10-25-first-cloud-deploy.md).

Alerts reach Telegram only once a bot token is stored in SSM (`/minieyes/cloud/telegram-bot-token`)
and `chat_id` is set in the GitOps copy of `alertmanager.yaml`; until then use the Alertmanager
UI (`kubectl -n monitoring port-forward svc/kube-prometheus-stack-alertmanager 9093`).
