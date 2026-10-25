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

## Related EKS decisions

- **Plain `aws_eks_*` resources instead of `terraform-aws-modules/eks`.** The module creates an IRSA
  OIDC provider, a KMS key and a CloudWatch log group by default; the deployer guardrails deny the
  first (only the GitHub OIDC provider may exist) and the others cost money. Its internals also
  cannot be asserted from `terraform test`. The plain version is ~200 lines and fully tested.
- **EKS Pod Identity, not IRSA**, for the EBS CSI controller (`minieyes-lab-ebs-csi`, trusted by
  `pods.eks.amazonaws.com`). vpc-cni keeps using the node role.
- **Endpoint:** public access limited to the admin CIDRs, private access on, so nodes (whose public
  IPs are not in the admin list) talk to the API through the VPC.
- **Spot instance types:** the guardrails only allow `m6i.large` and `t3.micro|small|medium`, so the
  node group lists `t3.medium`, `m6i.large`, `t3.small`. `t3.small` (2 GiB) is the weakest pool
  and is kept only to have three Spot pools; drop it if pods stop fitting.
- **Add-ons:** vpc-cni, kube-proxy and eks-pod-identity-agent are created before the node group
  (nodes need the CNI to become Ready), coredns and aws-ebs-csi-driver after it.
  `bootstrap_self_managed_addons = false`.
- **Argo CD and the gp3 StorageClass** live in `envs/lab-platform` (separate state, Helm and
  Kubernetes providers authenticated with `aws_eks_cluster_auth`), because those providers cannot
  be configured before the cluster exists.
- **No secrets envelope KMS key and no control-plane logs:** EKS encrypts secrets with an AWS-owned
  key by default, and log ingestion is not needed for the lab.
- **`upgrade_policy.support_type = STANDARD`:** EKS refuses to run the cluster in extended
  support (6x the hourly price) instead of billing it silently.
