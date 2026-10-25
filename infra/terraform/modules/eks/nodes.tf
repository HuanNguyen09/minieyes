# Launch template so node instances, volumes and ENIs are tagged Project=minieyes at creation
# (provider default_tags do not reach resources EKS launches) and IMDSv2 is enforced.
resource "aws_launch_template" "node" {
  name_prefix            = "${var.cluster_name}-node-"
  update_default_version = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2 # pods on the node network namespace still reach IMDS
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  dynamic "tag_specifications" {
    for_each = toset(["instance", "volume", "network-interface"])

    content {
      resource_type = tag_specifications.key
      tags          = merge(var.tags, { Name = "${var.cluster_name}-node" })
    }
  }

  tags = var.tags
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids

  capacity_type  = "SPOT"
  instance_types = var.node_instance_types
  ami_type       = "AL2023_x86_64_STANDARD"

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = 1
    max_size     = var.node_desired_size + 1
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  depends_on = [aws_iam_role_policy_attachment.node, aws_eks_addon.before_nodes]

  lifecycle {
    # Scaling by hand (or later an autoscaler) must not show up as drift.
    ignore_changes = [scaling_config[0].desired_size]
  }
}
