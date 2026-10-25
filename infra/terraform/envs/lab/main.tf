data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  tags = {
    Project     = "minieyes"
    Environment = "lab"
    ManagedBy   = "terraform"
  }

  account_id = data.aws_caller_identity.current.account_id

  # Every minieyes-* role must carry this boundary or the deployer's CreateRole is denied.
  permissions_boundary_arn = "arn:${data.aws_partition.current.partition}:iam::${local.account_id}:policy/${var.permissions_boundary_name}"

  state_bucket_name = "minieyes-tfstate-${local.account_id}"
}

# Two VPCs, deliberately not peered: the edge reaches the cloud only over the internet (HTTPS),
# like a box behind a customer's firewall.
module "cloud_vpc" {
  source = "../../modules/vpc"

  name                = "minieyes-cloud"
  cidr_block          = var.cloud_vpc_cidr
  public_subnet_count = 2 # EKS needs subnets in at least two AZs

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
}

module "site_vpc" {
  source = "../../modules/vpc"

  name                = "minieyes-site"
  cidr_block          = var.site_vpc_cidr
  public_subnet_count = 1
}

module "ecr" {
  source = "../../modules/ecr"

  repositories = var.ecr_repositories
}

module "github_oidc" {
  source = "../../modules/github-oidc"

  github_repo              = var.github_repo
  ecr_repository_arns      = values(module.ecr.repository_arns)
  state_bucket_name        = local.state_bucket_name
  permissions_boundary_arn = local.permissions_boundary_arn
}
