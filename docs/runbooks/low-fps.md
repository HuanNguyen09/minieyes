# Runbook: LowFPS

**Severity:** warning · **Rule:** `rate(minieyes_frames_total[2m]) < 2` while `minieyes_camera_up == 1`, for 5m · **Drill:** #4 (artificial delay)

## Meaning
The camera is readable but fewer than 2 frames per second go through inference. Intrusions may be detected late or missed (the debounce needs consecutive frames).

## First checks
1. Is `HighInferenceLatency` firing for the same site? Then the cause is Triton: follow that runbook.
2. *Frames dropped* panel: a high `minieyes_frames_dropped_total` rate means inference is slower than the stream.
3. Node CPU on the dashboard and `kubectl top pods -n minieyes` on the edge: is the detector or Triton CPU-throttled?
4. Recent release? Check the Argo CD history for the site.

## Fix
- Raise detector/Triton CPU requests and limits, or remove the extra load, through the GitOps repo.
- Roll back a bad release with `git revert` in the GitOps repo.
- If the camera itself delivers < 2 fps, fix the stream settings (camera-sim serves 5 fps).
