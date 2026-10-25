# Managed add-ons. Versions resolve to the latest build for the pinned Kubernetes version at plan
# time; pin addon_version here if a later plan must stay byte-for-byte identical.

locals {
  # Needed before nodes join: networking, kube-proxy and the Pod Identity agent (DaemonSets).
  addons_before_nodes = ["vpc-cni", "kube-proxy", "eks-pod-identity-agent"]
  # Need schedulable nodes to become ACTIVE. metrics-server feeds the event-api HPA; EKS does
  # not ship it, and without it the HPA (and so the Argo CD app) stays Degraded.
  addons_after_nodes = ["coredns", "aws-ebs-csi-driver", "metrics-server"]
}

data "aws_eks_addon_version" "this" {
  for_each = toset(concat(local.addons_before_nodes, local.addons_after_nodes))

  addon_name         = each.key
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

resource "aws_eks_addon" "before_nodes" {
  for_each = toset(local.addons_before_nodes)

  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = data.aws_eks_addon_version.this[each.key].version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  # The CNI's network policy agent is what enforces the charts' NetworkPolicies (#37).
  configuration_values = each.key == "vpc-cni" ? jsonencode({ enableNetworkPolicy = "true" }) : null
}

resource "aws_eks_addon" "after_nodes" {
  for_each = toset(local.addons_after_nodes)

  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = data.aws_eks_addon_version.this[each.key].version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  # EKS Pod Identity (not IRSA): no EKS OIDC provider is needed.
  dynamic "pod_identity_association" {
    for_each = each.key == "aws-ebs-csi-driver" ? [1] : []

    content {
      role_arn        = aws_iam_role.ebs_csi.arn
      service_account = "ebs-csi-controller-sa"
    }
  }

  depends_on = [aws_eks_node_group.spot, aws_eks_addon.before_nodes]
}
