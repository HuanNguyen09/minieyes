mock_provider "aws" {
  # Policy documents feed role arguments; give the mock valid JSON.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }

  mock_data "aws_eks_addon_version" {
    defaults = {
      version = "v1.0.0-eksbuild.1"
    }
  }
}

variables {
  cluster_name             = "minieyes-lab"
  subnet_ids               = ["subnet-0aaaaaaaaaaaaaaaa", "subnet-0bbbbbbbbbbbbbbbb"]
  admin_cidrs              = ["203.0.113.10/32"]
  admin_principal_arns     = ["arn:aws:iam::123456789012:role/DevBox-MiniEyes-Claude"]
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/Boundary-MiniEyes-Workload"
  tags                     = { Project = "minieyes", Environment = "lab" }
}

run "spot_node_group_with_several_allowed_types" {
  command = plan

  assert {
    condition     = aws_eks_node_group.spot.capacity_type == "SPOT"
    error_message = "Node group must use Spot capacity."
  }

  assert {
    condition     = aws_eks_node_group.spot.scaling_config[0].desired_size == 2
    error_message = "Node group desired size must be 2."
  }

  # The guardrails allow only m6i.large and t3.*; t3.small and t3.micro are too small for the
  # platform pods (11 pods max with the VPC CNI), which leaves two Spot pools.
  assert {
    condition     = length(aws_eks_node_group.spot.instance_types) >= 2
    error_message = "List at least two instance types to reduce Spot interruptions."
  }

  assert {
    condition = alltrue([
      for t in aws_eks_node_group.spot.instance_types : contains(["m6i.large", "t3.micro", "t3.small", "t3.medium"], t)
    ])
    error_message = "Only instance types allowed by the deployer guardrails (m6i.large, t3.micro/small/medium)."
  }
}

run "version_pinned_and_admins_from_access_entries" {
  command = plan

  assert {
    condition     = aws_eks_cluster.this.version == "1.35"
    error_message = "Cluster version must be pinned."
  }

  assert {
    condition     = aws_eks_cluster.this.access_config[0].authentication_mode == "API"
    error_message = "Cluster must use access entries (authentication_mode API)."
  }

  assert {
    condition     = toset([for e in aws_eks_access_entry.admin : e.principal_arn]) == toset(var.admin_principal_arns)
    error_message = "Every admin principal needs an access entry."
  }

  assert {
    condition = alltrue([
      for a in aws_eks_access_policy_association.admin :
      endswith(a.policy_arn, ":cluster-access-policy/AmazonEKSClusterAdminPolicy") && a.access_scope[0].type == "cluster"
    ]) && length(aws_eks_access_policy_association.admin) == length(var.admin_principal_arns)
    error_message = "Admin access entries must be associated with AmazonEKSClusterAdminPolicy at cluster scope."
  }
}

run "api_endpoint_restricted_and_no_control_plane_logs" {
  command = plan

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].public_access_cidrs == toset(["203.0.113.10/32"])
    error_message = "Public API endpoint must be restricted to the admin CIDR."
  }

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_private_access
    error_message = "Private endpoint must be on so nodes reach the API without being in admin_cidrs."
  }

  assert {
    condition     = length(aws_eks_cluster.this.enabled_cluster_log_types) == 0
    error_message = "Control-plane log types must be empty (CloudWatch cost)."
  }
}

run "managed_addons_and_ebs_csi_pod_identity" {
  command = plan

  assert {
    condition = toset(concat(keys(aws_eks_addon.before_nodes), keys(aws_eks_addon.after_nodes))) == toset([
      "vpc-cni", "kube-proxy", "eks-pod-identity-agent", "coredns", "aws-ebs-csi-driver",
    ])
    error_message = "Expected the managed add-ons vpc-cni, kube-proxy, eks-pod-identity-agent, coredns, aws-ebs-csi-driver."
  }

  # The CNI must exist before nodes join, or they never become Ready.
  assert {
    condition     = contains(keys(aws_eks_addon.before_nodes), "vpc-cni")
    error_message = "vpc-cni must be installed before the node group."
  }

  assert {
    condition = (
      length(aws_eks_addon.after_nodes["aws-ebs-csi-driver"].pod_identity_association) == 1 &&
      one(aws_eks_addon.after_nodes["aws-ebs-csi-driver"].pod_identity_association).service_account == "ebs-csi-controller-sa"
    )
    error_message = "aws-ebs-csi-driver must use a Pod Identity association for ebs-csi-controller-sa."
  }

  assert {
    condition     = aws_iam_role.ebs_csi.name == "minieyes-lab-ebs-csi"
    error_message = "EBS CSI role must be named minieyes-<cluster>-ebs-csi."
  }

  assert {
    condition = anytrue([
      for s in data.aws_iam_policy_document.pod_identity_trust.statement :
      anytrue([for p in s.principals : contains(p.identifiers, "pods.eks.amazonaws.com")])
    ])
    error_message = "EBS CSI role must trust EKS Pod Identity (pods.eks.amazonaws.com), not IRSA."
  }
}

run "every_role_is_named_minieyes_and_carries_the_boundary" {
  command = plan

  assert {
    condition = alltrue([
      for r in [aws_iam_role.cluster, aws_iam_role.node, aws_iam_role.ebs_csi] :
      startswith(r.name, "minieyes-") && r.permissions_boundary == var.permissions_boundary_arn
    ])
    error_message = "Every IAM role must be named minieyes-* and carry Boundary-MiniEyes-Workload."
  }
}

run "node_launch_template_tags_and_imdsv2" {
  command = plan

  assert {
    condition = (
      toset([for t in aws_launch_template.node.tag_specifications : t.resource_type]) == toset(["instance", "volume", "network-interface"]) &&
      alltrue([for t in aws_launch_template.node.tag_specifications : t.tags["Project"] == "minieyes"])
    )
    error_message = "Node instances, volumes and ENIs must be tagged Project=minieyes at launch."
  }

  assert {
    condition     = aws_launch_template.node.metadata_options[0].http_tokens == "required"
    error_message = "Nodes must require IMDSv2."
  }

  assert {
    condition     = aws_launch_template.node.block_device_mappings[0].ebs[0].encrypted == "true"
    error_message = "Node root volumes must be encrypted."
  }
}

run "disallowed_instance_type_is_rejected" {
  command = plan

  variables {
    node_instance_types = ["t3.medium", "m5.large", "t3.small"]
  }

  expect_failures = [var.node_instance_types]
}
