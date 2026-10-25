# DetectorDown

**Meaning:** Alloy at `{{site}}` cannot scrape the detector for 2 minutes. No camera at that site
is being watched. `CameraDown` cannot cover this case: a detector that is not running exposes no
`minieyes_camera_up` at all.

**First checks** (dev box, `scripts/edge-kubeconfig.sh` first):

```bash
kubectl --context edge-01 -n minieyes get pods -l app.kubernetes.io/name=detector
kubectl --context edge-01 -n minieyes describe pod -l app.kubernetes.io/name=detector | tail -20
kubectl --context edge-01 -n argocd get app detector
```

| Symptom | Likely cause | Fix |
|---|---|---|
| `ImagePullBackOff` / `ErrImagePull` | tag not in ECR (bad bump), ECR credential provider broken | `git revert` the bump in minieyes-gitops; check `/etc/rancher/k3s/credential-provider-config.yaml` |
| `CrashLoopBackOff`, log `missing required settings` | Secret or values missing | `scripts/bootstrap-secrets.sh edge`; compare values with `charts/detector/values.yaml` |
| `Pending` | edge node full or NotReady | `kubectl --context edge-01 describe node` |
| pod Running but target down | NetworkPolicy or Alloy | `kubectl --context edge-01 -n monitoring logs ds/alloy` |

The detector uses the `Recreate` strategy (one reader per camera), so a failing rollout leaves no
detector running: roll back first, investigate second.
