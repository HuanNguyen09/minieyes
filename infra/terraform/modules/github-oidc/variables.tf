variable "github_repo" {
  description = "GitHub repository (owner/name) whose workflows may assume the roles."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repo))
    error_message = "github_repo must look like owner/name, without wildcards."
  }
}

variable "permissions_boundary_arn" {
  description = "ARN of the permissions boundary every minieyes-* role must carry (Boundary-MiniEyes-Workload)."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:policy/", var.permissions_boundary_arn))
    error_message = "permissions_boundary_arn must be an IAM policy ARN."
  }
}

variable "ecr_repository_arns" {
  description = "ECR repositories the push role may push to."
  type        = list(string)
}

variable "state_bucket_name" {
  description = "Terraform state bucket the plan role may read."
  type        = string
}
