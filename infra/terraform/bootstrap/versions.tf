terraform {
  # Bootstrap keeps local state: it creates the bucket every other stack uses.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "minieyes"
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}
