# ADR-002 — Pull-based GitOps for edge sites

**Status:** Accepted

## Context

Real edge boxes sit behind customer NAT and firewalls. A CI system cannot reach their Kubernetes API, and storing a kubeconfig for every site in CI widens the blast radius of a leaked secret.

## Decision

Run Argo CD inside each cluster (the EKS cluster and every edge k3s node). Each instance pulls its own path from the GitOps repo. CI only builds and pushes images, then commits the new image tag to Git.

## Consequences

- Edge sites need outbound HTTPS only; no inbound ports are opened.
- Git is the single source of truth; rollback is `git revert`.
- Each site runs its own Argo CD, so the fleet view is assembled in Grafana rather than in one Argo CD UI. A hub-and-spoke Argo CD over a VPN tunnel is the alternative if central control becomes more important than isolation.
