# ADR-003 — One Grafana Alloy agent at the edge

**Status:** Accepted (revised: replaced Prometheus agent mode + Alloy with Alloy only)

## Context

Edge nodes have limited CPU, memory and disk (an m6i.large also runs k3s, Triton and Argo CD), and connectivity to the cloud can drop. Alerts and dashboards should cover every site from one place.

## Decision

Run a single **Grafana Alloy** agent on each edge node. It scrapes local targets (detector, Triton, node_exporter, kube-state-metrics) and forwards samples with `remote_write` to the central Prometheus on EKS, and it tails pod logs and pushes them to Loki. Every series and stream carries a `site` label. Storage and alert rules live centrally.

Prometheus in agent mode plus a separate log shipper was considered; one agent is lighter and has one config to manage.

## Consequences

- Smaller edge footprint, one component to upgrade.
- Alloy's write-ahead log buffers samples during short outages.
- A silent site is detected centrally with a generic rule (`max_over_time(up[1h]) unless up`, grouped by `site`). Remote-written series remain visible for the 5-minute lookback, so detection takes about 10 minutes.
- Inhibition rules suppress per-camera alerts while the whole site is unreachable.
