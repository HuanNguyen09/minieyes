# Plain resources instead of terraform-aws-modules/eks (ADR-004): the upstream module creates an
# IRSA OIDC provider, a KMS key and a log group by default, which the deployer guardrails deny or
# which cost money, and its internals cannot be asserted from `terraform test`.

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  # No control-plane logs: CloudWatch ingestion is not worth the cost in the lab.
  enabled_cluster_log_types = []

  # Managed add-ons (addons.tf) replace the self-managed defaults.
  bootstrap_self_managed_addons = false

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_public_access  = true
    public_access_cidrs     = var.admin_cidrs
    endpoint_private_access = true # nodes have public IPs outside admin_cidrs; they use the private endpoint
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false # admins are explicit access entries
  }

  # Fail upgrades instead of silently entering extended support (0.60 USD/h instead of 0.10).
  upgrade_policy {
    support_type = "STANDARD"
  }

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

# Cluster admins are explicit access entries (no implicit creator admin).
resource "aws_eks_access_entry" "admin" {
  for_each = toset(var.admin_principal_arns)

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.key
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  for_each = aws_eks_access_entry.admin

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value.principal_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}
