variable "region" {
  description = "AWS region. The deployer guardrails deny every other region."
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = var.region == "ap-southeast-1"
    error_message = "MiniEyes runs only in ap-southeast-1 (see infra/aws/iam)."
  }
}

variable "admin_cidr" {
  description = "Public IP (/32) of the machine that runs Terraform, kubectl and Ansible (the dev box). Reaches the EKS API and SSH on the edge."
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be a valid IPv4 CIDR and not 0.0.0.0/0."
  }
}

variable "extra_admin_cidrs" {
  description = "Additional admin CIDRs (e.g. the owner's laptop) for the EKS API, edge SSH and later the NLB."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.extra_admin_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0"])
    error_message = "extra_admin_cidrs must be valid IPv4 CIDRs and not 0.0.0.0/0."
  }
}

variable "extra_cluster_admin_arns" {
  description = "IAM role ARNs granted EKS cluster-admin in addition to the role running Terraform."
  type        = list(string)
  default     = []
}

variable "edge_ssh_public_key" {
  description = "OpenSSH public key installed for the ubuntu user on the edge (the dev box key Ansible uses)."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) ", var.edge_ssh_public_key))
    error_message = "edge_ssh_public_key must be an OpenSSH public key."
  }
}

variable "kubernetes_version" {
  description = "Pinned EKS Kubernetes version; keep it in standard support."
  type        = string
  default     = "1.35"
}

variable "node_instance_types" {
  description = "Spot instance types for the EKS node group (deployer allows only m6i.large and t3.micro/small/medium). t3.small is left out: with the VPC CNI it fits only 11 pods and ~1.4 GiB, too small for the platform pods."
  type        = list(string)
  default     = ["t3.medium", "m6i.large"]
}

variable "base_domain" {
  description = "Base domain for ingress hosts (#40). Empty means <nlb-ip>.sslip.io, resolved by GitOps once the NLB exists."
  type        = string
  default     = ""
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

variable "create_github_oidc_provider" {
  description = "false when the account already has token.actions.githubusercontent.com (another project created it); the lab then reuses it without managing it."
  type        = bool
  default     = false
}

variable "node_desired_size" {
  description = "Spot nodes in the EKS node group. Three t3.medium-class nodes fit Argo CD, monitoring, Loki and the API."
  type        = number
  default     = 3
}
