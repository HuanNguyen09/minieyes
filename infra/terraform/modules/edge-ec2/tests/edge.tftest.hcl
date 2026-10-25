mock_provider "aws" {
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

  mock_data "aws_ssm_parameter" {
    defaults = {
      value          = "ami-0123456789abcdef0"
      insecure_value = "ami-0123456789abcdef0"
    }
  }

  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/minieyes-edge"
    }
  }

  mock_resource "aws_instance" {
    defaults = {
      id = "i-0123456789abcdef0"
    }
  }

  mock_resource "aws_eip" {
    defaults = {
      public_ip = "198.51.100.7"
    }
  }
}

variables {
  name                     = "minieyes-edge"
  vpc_id                   = "vpc-0123456789abcdef0"
  subnet_id                = "subnet-0123456789abcdef0"
  admin_cidrs              = ["203.0.113.10/32"]
  ssh_public_key           = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnlyForTests test"
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/Boundary-MiniEyes-Workload"
  tags                     = { Project = "minieyes", Environment = "lab" }
}

run "instance_type_and_encrypted_gp3_root" {
  command = plan

  assert {
    condition     = aws_instance.edge.instance_type == "m6i.large"
    error_message = "Edge must be m6i.large (non-burstable CPU for sustained inference)."
  }

  assert {
    condition = (
      aws_instance.edge.root_block_device[0].volume_type == "gp3" &&
      aws_instance.edge.root_block_device[0].volume_size == 80 &&
      aws_instance.edge.root_block_device[0].encrypted
    )
    error_message = "Root volume must be an encrypted 80 GB gp3 (Triton image 15 GB + re-pulls; 40 GB hit DiskPressure)."
  }

  assert {
    condition     = aws_instance.edge.volume_tags["Project"] == "minieyes"
    error_message = "Root volume must be tagged Project=minieyes at launch."
  }
}

run "instance_profile_has_only_ecr_read_only" {
  command = plan

  assert {
    condition     = aws_iam_role_policy_attachment.ecr_read_only.policy_arn == "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
    error_message = "Edge role must get AmazonEC2ContainerRegistryReadOnly (kubelet ecr-credential-provider)."
  }

  assert {
    condition     = aws_iam_instance_profile.edge.role == aws_iam_role.edge.name && aws_instance.edge.iam_instance_profile == aws_iam_instance_profile.edge.name
    error_message = "The edge instance must use the minieyes-edge instance profile."
  }

  assert {
    condition = (
      startswith(aws_iam_role.edge.name, "minieyes-") &&
      startswith(aws_iam_instance_profile.edge.name, "minieyes-") &&
      aws_iam_role.edge.permissions_boundary == var.permissions_boundary_arn
    )
    error_message = "Edge role and profile must be named minieyes-* and the role must carry the workload boundary."
  }
}

run "ssh_only_from_admin_and_all_egress" {
  command = plan

  assert {
    condition = length(aws_vpc_security_group_ingress_rule.ssh) == 1 && alltrue([
      for r in aws_vpc_security_group_ingress_rule.ssh :
      r.ip_protocol == "tcp" && r.from_port == 22 && r.to_port == 22 && r.cidr_ipv4 == "203.0.113.10/32"
    ])
    error_message = "Ingress must allow only TCP 22 from the admin CIDR."
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.all.ip_protocol == "-1" && aws_vpc_security_group_egress_rule.all.cidr_ipv4 == "0.0.0.0/0"
    error_message = "Egress must allow all outbound traffic."
  }
}

run "imdsv2_required" {
  command = plan

  assert {
    condition     = aws_instance.edge.metadata_options[0].http_tokens == "required"
    error_message = "Edge must require IMDSv2."
  }
}

# apply against the mock provider (nothing real is created) so the EIP address is known.
run "elastic_ip_attached_and_exported" {
  command = apply

  assert {
    condition     = aws_eip.edge.instance == aws_instance.edge.id && aws_eip.edge.domain == "vpc"
    error_message = "An Elastic IP must be attached to the edge instance."
  }

  assert {
    condition     = output.public_ip == "198.51.100.7"
    error_message = "public_ip output must be the Elastic IP (Ansible inventory)."
  }
}

run "burstable_instance_type_is_rejected" {
  command = plan

  variables {
    instance_type = "t3.medium"
  }

  expect_failures = [var.instance_type]
}
