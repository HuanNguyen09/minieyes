# ADR-004 — Public subnets only, no NAT Gateway

**Status:** Accepted

## Context

The whole project must stay under 100 USD of AWS credit (NFR-6). A NAT Gateway in
`ap-southeast-1` costs about 0.059 USD/h plus 0.059 USD/GB processed — roughly 45 USD a month
for one gateway before traffic, close to half the budget, and EKS nodes pull large images
(Triton is over 10 GB at the edge, the monitoring stack on EKS). The edge VPC only needs outbound
HTTPS (NFR-4), and the cloud VPC hosts a small lab cluster.

## Decision

- Both VPCs (`minieyes-cloud`, `minieyes-site`) have **public subnets only**: an Internet Gateway,
  one route table with a single `0.0.0.0/0 → IGW` route, `map_public_ip_on_launch = true`.
  **No NAT Gateway, no private subnets, no peering.**
- **EKS managed nodes run in the public subnets** with public IPv4 addresses and reach ECR, the
  EKS API and the internet directly.
- Inbound exposure is controlled by security groups, not by subnet placement: the node security
  group accepts traffic only from the cluster security group and from itself; the edge security
  group accepts only TCP 22 from `admin_cidr`; the EKS public API endpoint is restricted to
  `admin_cidr`; the NLB (installed later by GitOps, #40) allows only the edge EIP and `admin_cidr`.
- The default security group of each VPC is emptied so nothing can land in an open group.
- Route tables use inline routes, so a NAT or peering route added outside Terraform shows up as drift.

## Consequences

- Saves ~45 USD/month; public IPv4 costs 0.005 USD/h per address (2 nodes + edge EIP + NLB ≈ 15 USD/month).
- Nodes have public IPs: a mistake in a security group exposes them directly. This is the main
  accepted risk; production would put nodes in private subnets behind NAT or VPC endpoints.
- Scanners (`trivy config`) flag public IP assignment on subnets (AWS-0164) and missing VPC flow
  logs (AWS-0178); both are accepted for the lab for the reasons above (flow logs cost money and
  need a log group outside the deployer's `/aws/eks/minieyes-*` scope).
- Moving to private nodes later is additive: add private subnets and a NAT Gateway (or ECR/S3/STS
  endpoints) and point the node group at them.
