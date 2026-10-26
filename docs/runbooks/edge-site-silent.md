# Runbook: EdgeSiteSilent

**Severity:** critical · **Rule:** `group by (site) (max_over_time(up[1h])) unless group by (site) (up)` for 5m · **Drill:** #6 (remove edge egress)

## Meaning
The central Prometheus received samples from `site` within the last hour but receives nothing now. The edge node, its outbound network or Grafana Alloy is down. Alertmanager inhibits every other alert with the same `site`, so this is the one message you get.

Timing: remote-written series stay visible for the 5-minute lookback, plus `for: 5m`, so the alert fires about **10 minutes** after the site goes dark. After **1 hour** without data the site falls out of the `[1h]` window and the alert resolves by itself even if the site is still down. A "resolved" message without a recovery means the site is still broken.

## First checks
1. Can you SSH to the edge EIP? If not, check the EC2 instance status (console or `aws ec2 describe-instance-status`).
2. On the node: `sudo k3s kubectl -n monitoring get pods` (is Alloy running?) and the Alloy logs for remote_write errors (401 = basic auth, TLS errors, timeouts).
3. Egress: `curl -sv https://metrics.<base_domain>/` from the node; check the site Security Group egress rules and the Traefik `ipAllowList` source ranges in the GitOps repo (`clusters/cloud/values/platform.yaml`, they must include the edge EIP); a 403 from Traefik means the IP is not allowed.
4. Are events still reaching the Event API? If yes, only the telemetry path is broken.

## Fix
- Restore egress (Security Group or NLB allow list) through Terraform.
- Restart Alloy or fix its credentials Secret.
- Reboot or replace the instance if it is unhealthy. Alloy's WAL replays buffered samples once the link is back.
