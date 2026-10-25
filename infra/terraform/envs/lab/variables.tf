variable "region" {
  description = "AWS region. The deployer guardrails deny every other region."
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = var.region == "ap-southeast-1"
    error_message = "MiniEyes runs only in ap-southeast-1 (see infra/aws/iam)."
  }
}

variable "permissions_boundary_name" {
  description = "Name of the IAM permissions boundary every minieyes-* role must carry (infra/aws/iam/workload-boundary.json)."
  type        = string
  default     = "Boundary-MiniEyes-Workload"
}

variable "github_repo" {
  description = "GitHub repository whose Actions may assume the push (main) and plan (pull_request) roles."
  type        = string
  default     = "HuanNguyen09/minieyes"
}

variable "ecr_repositories" {
  description = "ECR repositories, one per image built by CI."
  type        = list(string)
  default     = ["minieyes/detector", "minieyes/event-api", "minieyes/camera-sim", "minieyes/model-yolov8n"]
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
