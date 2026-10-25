locals {
  tags = {
    Project     = "minieyes"
    Environment = "lab"
    ManagedBy   = "terraform"
  }
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
