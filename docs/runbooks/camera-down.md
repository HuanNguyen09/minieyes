# Runbook: CameraDown

**Severity:** critical · **Rule:** `minieyes_camera_up == 0` for 1m · **Drill:** #1 (stop camera-sim)

## Meaning
The detector at `site` cannot read the RTSP stream of `camera`. No frames means no intrusion events for that camera.

## First checks
1. Grafana *MiniEyes Overview* → *Camera up* for the site/camera: one camera or all of them?
2. Detector logs in Loki: `{site="<site>", app="detector"} | json | camera="<camera>"` — look for reconnect/backoff messages.
3. Is the source alive? `kubectl -n minieyes get pods -l app.kubernetes.io/name=camera-sim` (lab) or ping the real camera.
4. From a pod on the edge: `ffprobe rtsp://<host>:8554/<camera>` against the URL in the detector values.

## Fix
- camera-sim pod not running → let Argo CD resync it, or restart it on the edge.
- Wrong RTSP URL or credentials → fix the detector values in the GitOps repo and push.
- The detector reconnects by itself (exponential backoff, cap 30 s); the alert resolves once frames are read again.
