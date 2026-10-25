# Failure drills (#38)

Each drill: break one thing on purpose, watch the alert fire (screenshot of Grafana/Alertmanager
or the Telegram message), follow the runbook linked from the alert's `runbook_url`, restore,
watch it resolve. Commands run on the dev box (`scripts/devbox.sh '...'`) with the lab up
(`scripts/lab-power.sh up`). Argo CD self-heals manual changes within ~3 minutes, which is
itself drill 7; for longer drills make the change in the GitOps repo instead.

| # | Drill | How | Expected | Status |
|---|---|---|---|---|
| 1 | Camera down | in the camera-sim pod: `pkill ffmpeg` every second for 200 s (Argo CD would undo a `kubectl scale` within seconds) | **CameraDown** | ✅ 2026-10-25: started 19:59:42Z, **firing 20:01:22Z** (100 s), stream back 20:03:02Z, **resolved 20:04:09Z** |
| 2 | Triton OOMKilled | GitOps: `sites/site-01/values/triton.yaml` → `resources.limits.memory: 64Mi` | pod `OOMKilled`, **PodCrashLooping**, detector logs `inference failed, frame skipped` | pending (lab up) |
| 3 | Bad image tag | GitOps commit `image.tag: deadbeef…`, rollback with `git revert` | `ImagePullBackOff`; `Recreate` leaves no detector, `minieyes_camera_up` disappears so **CameraDown cannot fire** → new **DetectorDown** ([runbook](runbooks/detector-down.md)) | ✅ pushed 20:07:23Z, **DetectorDown firing 20:10:18Z** (145 s), CameraDown silent as predicted; reverted 20:10:52Z, detector back. Finding: once the pod is gone the `up` series vanishes and DetectorDown resolves early — see follow-up below |
| 4 | Latency regression | GitOps: triton `resources.limits.cpu: 200m` | **HighInferenceLatency** (p95 > 0.5 s for 5 m), **LowFPS** | pending |
| 5 | Edge disk filling | `fallocate` 4 GB on the 40 GB edge disk | **DiskWillFillIn24h** | ⚠️ Real cascade instead: rollouts + the file pushed the node to **DiskPressure** within minutes, kubelet evicted pods and garbage-collected the 15 GB Triton image, whose re-pull filled the disk again (0.29 GB free). The 1h-trend alert never had time to fire. Fixes: edge disk 80 GB (`terraform apply`, online `growpart`), new fast alert **DiskAlmostFull** (< 15 % for 5 m) |
| 6 | Edge loses egress | on the edge: `sudo iptables -I OUTPUT -p tcp --dport 443 -j REJECT` for 5 min | **EdgeSiteSilent** after ~10 min; no event lost once restored | Event-loss half verified: e2e "API down 30 s → stored = events_total − dropped" passes (compose and dev box) |
| 7 | Manual drift self-healed | `kubectl --context edge-01 -n minieyes scale deploy detector --replicas=0` | Argo CD restores 1 replica | ✅ 20:06:07Z scaled to 0, **restored by Argo CD after 4 s**, Ready 20:06:21Z |
| 8 | Destructive Terraform plan caught | change `node_instance_types` | plan says `must be replaced`; `terraform-plan.yaml` calls it out on the PR | Seen for real on 2026-10-25: `module.eks.aws_eks_node_group.spot must be replaced` was read and accepted deliberately before apply; PR comment needs the CI scope |

Follow-up from drill 3: a pod that never starts drops out of Alloy's discovery, so `up{job="detector"}`
disappears and `DetectorDown` (`== 0`) resolves although nothing runs. Alerting on absence per site
(`group by (site)(up{job="alloy"}) unless group by (site)(up{job="detector"})`) closes that gap.

Postmortem of a real incident: [2026-10-25 first cloud deploy](postmortems/2026-10-25-first-cloud-deploy.md).

Alerts reach Telegram only once a bot token is stored in SSM (`/minieyes/cloud/telegram-bot-token`)
and `chat_id` is set in the GitOps copy of `alertmanager.yaml`; until then use the Alertmanager
UI (`kubectl -n monitoring port-forward svc/kube-prometheus-stack-alertmanager 9093`).
