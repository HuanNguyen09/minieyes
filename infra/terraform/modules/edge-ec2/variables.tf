variable "name" {
  description = "Name of the edge site resources (role, instance profile, key pair, security group)."
  type        = string
  default     = "minieyes-edge"

  validation {
    condition     = startswith(var.name, "minieyes-")
    error_message = "name must start with \"minieyes-\"."
  }
}

variable "vpc_id" {
  description = "Site VPC id."
  type        = string
}

variable "subnet_id" {
  description = "Public subnet of the site VPC."
  type        = string
}

variable "admin_cidrs" {
  description = "CIDRs allowed to SSH (TCP 22). Nothing else is allowed inbound (NFR-4)."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
    error_message = "admin_cidrs must be non-empty and must not contain 0.0.0.0/0."
  }
}

variable "ssh_public_key" {
  description = "OpenSSH public key for the ubuntu user (Ansible)."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "ARN of the permissions boundary every minieyes-* role must carry (Boundary-MiniEyes-Workload)."
  type        = string
}

variable "instance_type" {
  description = "Edge instance type. m6i.large: non-burstable CPU for sustained inference."
  type        = string
  default     = "m6i.large"

  validation {
    condition     = var.instance_type == "m6i.large"
    error_message = "The edge must be m6i.large: burstable t3 throttles sustained inference and others are denied by the guardrails."
  }
}

variable "root_volume_size" {
  description = "Root volume size in GB (Triton image and models need room)."
  type        = number
  default     = 40
}

variable "ami_ssm_parameter" {
  description = "Public SSM parameter holding the Ubuntu 24.04 AMI id."
  type        = string
  default     = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

variable "tags" {
  description = "Tags for the root volume at launch (provider default_tags do not reach volume_tags)."
  type        = map(string)

  validation {
    condition     = lookup(var.tags, "Project", "") == "minieyes"
    error_message = "tags must contain Project = \"minieyes\"."
  }
}
