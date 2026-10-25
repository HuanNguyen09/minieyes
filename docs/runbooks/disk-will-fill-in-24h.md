# Runbook: DiskWillFillIn24h

**Severity:** warning · **Rule:** `predict_linear(node_filesystem_avail_bytes[1h], 24h) < 0` for 30m · **Drill:** #5 (fill edge disk)

## Meaning
At the trend of the last hour, the filesystem runs out of space within 24 hours. On the edge a full disk breaks image pulls, the Alloy WAL and k3s itself.

## First checks
1. SSH to the node: `df -h` and `sudo du -xh --max-depth=2 / | sort -h | tail -20`.
2. Usual suspects: container images (`sudo k3s crictl images`), pod logs under `/var/log/pods`, the Alloy WAL (it grows while the site cannot reach the cloud), a file an app keeps writing.
3. Is `EdgeSiteSilent` firing as well? Then the WAL is buffering: fix connectivity first.

## Fix
- Remove unused images: `sudo k3s crictl rmi --prune`.
- Delete the offending files or fix the app that writes them.
- If the disk is simply too small, grow the EBS volume in Terraform, then `growpart` and `resize2fs`.
