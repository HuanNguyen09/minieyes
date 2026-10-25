# The "customer site" edge box: k3s is installed later by Ansible (infra/ansible).

data "aws_partition" "current" {}

data "aws_ssm_parameter" "ubuntu" {
  name = var.ami_ssm_parameter
}

# --- IAM: ECR pulls through the kubelet ecr-credential-provider, nothing else --------------------

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "edge" {
  name                 = var.name
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  permissions_boundary = var.permissions_boundary_arn
}

resource "aws_iam_role_policy_attachment" "ecr_read_only" {
  role       = aws_iam_role.edge.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "edge" {
  name = var.name
  role = aws_iam_role.edge.name
}

# --- network: SSH from admin only, all egress (NFR-4) --------------------------------------------

resource "aws_security_group" "edge" {
  name        = var.name
  description = "MiniEyes edge: SSH from admin CIDRs only, all egress"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each = toset(var.admin_cidrs)

  security_group_id = aws_security_group.edge.id
  description       = "SSH from admin"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = each.key
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.edge.id
  description       = "Outbound HTTPS to ECR, EKS ingress, GitHub and package mirrors"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_key_pair" "edge" {
  key_name   = var.name
  public_key = var.ssh_public_key
}

# --- instance --------------------------------------------------------------------------------------

resource "aws_instance" "edge" {
  ami                    = data.aws_ssm_parameter.ubuntu.insecure_value
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.edge.id]
  key_name               = aws_key_pair.edge.key_name
  iam_instance_profile   = aws_iam_instance_profile.edge.name

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # kubelet's credential provider runs on the host
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
  }

  # Tag the root volume in RunInstances itself; the guardrails deny tagging it afterwards.
  volume_tags = merge(var.tags, { Name = var.name })

  tags = { Name = var.name }

  lifecycle {
    # A newer Ubuntu AMI in SSM must not replace the running edge box.
    ignore_changes = [ami]
  }
}

resource "aws_eip" "edge" {
  domain   = "vpc"
  instance = aws_instance.edge.id

  tags = { Name = var.name }
}
