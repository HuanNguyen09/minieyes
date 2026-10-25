variable "cluster_name" {
  description = "EKS cluster name. The deployer may only manage clusters named minieyes-*."
  type        = string

  validation {
    condition     = startswith(var.cluster_name, "minieyes-")
    error_message = "cluster_name must start with \"minieyes-\"."
  }
}

variable "kubernetes_version" {
  description = "Pinned Kubernetes minor version. Keep it in EKS standard support: extended support costs 6x more per hour."
  type        = string
  default     = "1.35"

  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "kubernetes_version must be a pinned minor version such as 1.35."
  }
}

variable "subnet_ids" {
  description = "Subnets (at least two AZs) for the control plane ENIs and the nodes."
  type        = list(string)
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
    error_message = "admin_cidrs must be non-empty and must not contain 0.0.0.0/0."
  }
}

variable "admin_principal_arns" {
  description = "IAM role/user ARNs granted cluster-admin through EKS access entries."
  type        = list(string)
}

variable "permissions_boundary_arn" {
  description = "ARN of the permissions boundary every minieyes-* role must carry (Boundary-MiniEyes-Workload)."
  type        = string
}

variable "node_instance_types" {
  description = "Spot instance types for the node group; only types allowed by the deployer guardrails."
  type        = list(string)
  default     = ["t3.medium", "m6i.large", "t3.small"]

  validation {
    condition = alltrue([
      for t in var.node_instance_types : contains(["m6i.large", "t3.micro", "t3.small", "t3.medium"], t)
    ])
    error_message = "node_instance_types may only contain m6i.large, t3.micro, t3.small or t3.medium."
  }
}

variable "node_desired_size" {
  description = "Desired number of nodes."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags for resources that provider default_tags do not reach (node instances, volumes and ENIs via the launch template)."
  type        = map(string)

  validation {
    condition     = lookup(var.tags, "Project", "") == "minieyes"
    error_message = "tags must contain Project = \"minieyes\"."
  }
}
