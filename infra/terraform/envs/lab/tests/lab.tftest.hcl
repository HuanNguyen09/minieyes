mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
      arn        = "arn:aws:sts::123456789012:assumed-role/DevBox-MiniEyes-Claude/i-0123456789abcdef0"
    }
  }

  mock_data "aws_partition" {
    defaults = {
      partition = "aws"
    }
  }

  # apply runs feed generated ARNs into arguments the provider validates.
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/minieyes-mock"
    }
  }

  mock_resource "aws_iam_openid_connect_provider" {
    defaults = {
      arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    }
  }

  mock_resource "aws_ecr_repository" {
    defaults = {
      arn = "arn:aws:ecr:ap-southeast-1:123456789012:repository/minieyes-mock"
    }
  }

  mock_resource "aws_launch_template" {
    defaults = {
      id = "lt-0123456789abcdef0"
    }
  }

  mock_data "aws_eks_addon_version" {
    defaults = {
      version = "v1.0.0-eksbuild.1"
    }
  }

  mock_data "aws_iam_session_context" {
    defaults = {
      issuer_arn = "arn:aws:iam::123456789012:role/DevBox-MiniEyes-Claude"
    }
  }

  # Policy documents feed role/policy arguments; give the mock valid JSON.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  admin_cidr = "203.0.113.10/32"
}

# apply against the mock provider (nothing real is created) so route attributes are known.
run "cloud_and_site_vpcs_are_not_peered" {
  command = apply

  assert {
    condition = alltrue([
      for r in concat(tolist(module.cloud_vpc.public_routes), tolist(module.site_vpc.public_routes)) :
      r.cidr_block == "0.0.0.0/0" && coalesce(r.vpc_peering_connection_id, "none") == "none"
    ])
    error_message = "VPC route tables may only route 0.0.0.0/0 to the Internet Gateway; no peering routes."
  }

  assert {
    condition     = module.cloud_vpc.cidr_block != module.site_vpc.cidr_block
    error_message = "cloud-vpc and site-vpc must use different address ranges."
  }
}

run "registry_and_ci_roles" {
  command = apply

  assert {
    condition = toset(keys(output.ecr_repository_urls)) == toset([
      "minieyes/detector", "minieyes/event-api", "minieyes/camera-sim", "minieyes/model-yolov8n",
    ])
    error_message = "Expected the four project ECR repositories."
  }

  assert {
    condition     = output.github_push_role_arn != "" && output.github_plan_role_arn != ""
    error_message = "GitHub role ARNs must be exported for the CI workflows."
  }

  assert {
    condition     = output.account_id == "123456789012"
    error_message = "account_id output is needed by the GitOps seed."
  }
}

run "eks_in_cloud_vpc_with_deployer_as_admin" {
  command = plan

  assert {
    condition     = output.cluster_name == "minieyes-lab"
    error_message = "Cluster must be named minieyes-lab."
  }

  # The deployer runs on an instance role: the access entry needs the role ARN, not the STS session ARN.
  assert {
    condition     = contains(output.cluster_admin_arns, "arn:aws:iam::123456789012:role/DevBox-MiniEyes-Claude")
    error_message = "The role running Terraform must be a cluster admin."
  }
}
