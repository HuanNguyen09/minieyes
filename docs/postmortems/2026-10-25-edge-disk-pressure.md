# Postmortem: edge DiskPressure cascade during drill 5

- **Date:** 2026-10-25 (UTC), edge `site-01`
- **Impact:** ~10 minutes with most edge pods evicted (Argo CD, camera-sim, kube-state-metrics,
  Triton); detections paused. No events lost (the API stayed up; the detector's buffer covered
  the gap).
- **Detection:** noticed while investigating why a GitOps rollback (drill 3) was slow; no alert fired.

## Timeline

| Time (UTC) | Event |
|---|---|
| 19:58 | Drill 5: 4 GB file on the 40 GB edge disk (24 GB free at that moment) |
| 20:07–20:16 | Drill 3 rollouts (bad tag, revert) pull and unpack images |
| 20:19 | Node condition **DiskPressure**; kubelet evicts pods and garbage-collects images, including the 15 GB Triton image |
| 20:19–20:24 | Rescheduled Triton re-pulls 15 GB; free space at its lowest **0.29 GB**; more evictions |
| 20:24 | Drill file removed; containerd down to 280 MB of images |
| 20:26 | `terraform apply` grows the edge volume to 80 GB; online `growpart` + `resize2fs` |
| 20:30 | Taint cleared, pods rescheduled, all edge Applications Synced/Healthy |

## Root causes

1. **Disk sized for steady state, not for recovery:** 40 GB holds one copy of the 15 GB Triton
   image, but recovery after an eviction needs room to pull it again.
2. **Alert too slow for sudden fills:** `DiskWillFillIn24h` uses a 1 h trend with `for: 30m`; the
   disk went from 30 % to DiskPressure in minutes.

## Actions

| Action | Status |
|---|---|
| Edge root volume 80 GB (`root_volume_size`, tested) | done (`terraform apply`, online resize) |
| `DiskAlmostFull` (< 15 % free for 5 m), promtool-tested, ahead of kubelet's 10 % eviction | done; verified live 22:29Z (fired at 9.2 GB free, no eviction) |
| Runbook: grow volume online, prune images, clear failed pods | done (`docs/runbooks/disk-will-fill-in-24h.md`) |
| Consider a smaller Triton image (`-py3-min` + onnxruntime backend only) | open |
