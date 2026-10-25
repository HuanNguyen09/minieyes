# ADR-006 — Secrets in SSM Parameter Store, materialised by a script

**Status:** Accepted

## Context

The clusters need a database password, the site API key (plaintext at the edge, SHA-256 digest
in the cloud), push credentials for metrics/logs, the Grafana admin password and the Telegram
bot token. None may live in Git (#36). Options considered: External Secrets Operator (ESO) with
AWS Secrets Manager, Sealed Secrets, or Parameter Store plus a small script.

## Decision

- Values live in **SSM Parameter Store** as `SecureString` under `/minieyes/*` (KMS-encrypted,
  free tier, already reachable by the dev box role and nothing else).
- `scripts/bootstrap-secrets.sh cloud|edge` generates missing values once and writes the
  Kubernetes Secrets the GitOps repo references; it prints nothing.
- `scripts/rotate-secret.sh` rotates a value end to end (new value → Secrets in both clusters →
  rollout restart → verification).
- The edge never talks to AWS for secrets: its two Secrets are pushed from the dev box over the
  SSH tunnel, so a stolen edge instance profile cannot read them.

## Consequences

- No extra controller in either cluster, nothing to keep healthy at the edge.
- Rotation is an explicit, scripted operator action rather than continuous sync; with ESO a new
  value would propagate on its own. For one lab site this is the better trade.
- Moving to ESO later only changes how the same Secret names are produced; charts and GitOps
  stay as they are.
