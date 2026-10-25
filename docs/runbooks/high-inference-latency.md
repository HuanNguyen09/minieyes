# Runbook: HighInferenceLatency

**Severity:** warning · **Rule:** p95 of `minieyes_inference_seconds` > 0.5 s for 5m · **Drill:** #4 (artificial delay)

## Meaning
Triton round trips from the detector are slow, so FPS drops and events arrive later. The metric has no `camera` label: the whole site is affected.

## First checks
1. Triton metrics on the dashboard: `nv_inference_queue_duration_us` vs `nv_inference_compute_infer_duration_us` — queueing or compute?
2. Edge node CPU and CPU throttling of the Triton pod (`kubectl top pods -n minieyes`).
3. Triton logs in Loki: `{site="<site>", app="triton"}`.
4. Was a new model, Triton image or detector release rolled out?

## Fix
- CPU starved → give Triton more CPU, or reduce cameras / FPS per site.
- Bad model or config change → `git revert` it in the GitOps repo.
- Triton restarting → follow [PodCrashLooping](pod-crash-looping.md).
