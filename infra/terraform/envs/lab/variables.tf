variable "region" {
  description = "AWS region. The deployer guardrails deny every other region."
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = var.region == "ap-southeast-1"
    error_message = "MiniEyes runs only in ap-southeast-1 (see infra/aws/iam)."
  }
}

variable "cloud_vpc_cidr" {
  description = "CIDR of the cloud VPC (EKS)."
  type        = string
  default     = "10.10.0.0/16"
}

variable "site_vpc_cidr" {
  description = "CIDR of the site VPC (edge EC2). Must not overlap the cloud VPC."
  type        = string
  default     = "10.20.0.0/16"
}
