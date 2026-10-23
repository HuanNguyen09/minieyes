# ADR-003 — Prometheus agent mode at the edge

**Status:** Accepted

## Context

Edge nodes have limited CPU, memory and disk, and connectivity to the cloud can drop. Alerts and dashboards should cover every site from one place.

## Decision

Run Prometheus in agent mode on each edge node. It scrapes local targets (detector, Triton, node_exporter, kube-state-metrics) and forwards samples with `remote_write` to the central Prometheus on EKS, which stores data and evaluates alert rules. Every series carries a `site` label. Logs follow the same pattern with Grafana Alloy pushing to Loki.

## Consequences

- The edge footprint stays small; storage and rules live in one place.
- The agent's write-ahead log buffers samples during short outages.
- A silent site is detected centrally with `absent()`-style alerts, and inhibition rules suppress per-camera alerts while the whole site is unreachable.
