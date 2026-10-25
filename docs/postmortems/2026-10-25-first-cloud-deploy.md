# Postmortem: Event API unreachable for ~1 h on the first cloud deploy

- **Date:** 2026-10-25 (UTC), lab environment `minieyes-lab`
- **Impact:** for about an hour after the cloud GitOps root was applied, `events.<domain>`
  served no API: edge detections stayed in the detector's buffer (no loss: the buffer holds
  1,000 events and was later drained). No customer impact (lab).
- **Detection:** manual: `curl https://events.<domain>/healthz` returned 503, Argo CD showed
  `event-api` OutOfSync/Degraded and `traefik` Unknown.

## Timeline

| Time (UTC) | Event |
|---|---|
| 17:20 | `kubectl apply` of `clusters/cloud/root.yaml`; Argo CD creates 8 Applications |
| 17:31 | cert-manager, Prometheus operator and the migration Job `Pending`: **Too many pods** |
| 17:35 | Cause found: Spot picked `t3.small` for both nodes (11 pods max with the VPC CNI) |
| 17:52 | Node group replaced: 3 × `t3.medium` (#24 fix `a18ba5d`) |
| 17:58 | `traefik` Application cannot render: chart 41 rejects `ports.web.redirections` |
| 18:05 | Values fixed (`14a8209`); Argo CD keeps the old manifest: the `platform` sync is stuck waiting for Ingress health that needs Traefik |
| 18:30 | Stuck operation terminated; Traefik and the NLB come up |
| 18:38 | Certificates stay `pending`: NLB `loadBalancerSourceRanges` block Let's Encrypt's HTTP-01 validators |
| 18:47 | Source filtering moved to a Traefik `ipAllowList` middleware (`65589d0`); 4 certificates issued |
| 18:52 | API still 503: the HPA (wave 0) is Degraded before its Deployment (wave 1) exists, so wave 1 never runs |
| 19:00 | HPA moved to wave 2 (`63c05e3`); `/healthz` 200, buffered events delivered |
| 19:20 | Follow-ups: metrics-server add-on (HPA health), vpc-cni network policy agent (policies were not enforced) |

## Root causes

1. **Capacity:** the node group allowed `t3.small`, which cannot host the platform pods.
2. **Upstream schema change:** Traefik chart 41 moved the redirection settings; nothing rendered
   the upstream charts with our values before deploy.
3. **Ordering deadlocks in Argo CD:** an Ingress health check that depends on the controller
   being deployed by the same sync, and an HPA in an earlier wave than its target.
4. **Conflicting requirements not tested together:** L4 source restriction on the NLB versus
   HTTP-01 validation from the internet.

## What went well

- The detector buffered every event during the outage and delivered them afterwards; the
  publisher design (buffer + retry + idempotent API) did exactly its job.
- Every fix landed as a tested commit (helm-unittest / terraform test), not a manual patch.

## Actions

| Action | Status |
|---|---|
| Exclude `t3.small`, three nodes by default | done (`a18ba5d`) |
| Test the Traefik values shape and ACME bypass | done (`14a8209`) |
| HPA after Deployment, tested | done (`63c05e3`) |
| L7 allow-list instead of NLB source ranges, tested | done (`65589d0`) |
| metrics-server and network policy agent as EKS add-ons, tested | done |
| CI renders upstream charts (`gitops/ci/validate.yaml`) on every GitOps PR | written; needs the `workflow` scope |
| Runbook: terminating a stuck Argo CD operation | in `docs/BAO-CAO-DU-AN.md` §7 |
