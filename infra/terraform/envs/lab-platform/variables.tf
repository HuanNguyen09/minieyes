variable "region" {
  description = "AWS region. The deployer guardrails deny every other region."
  type        = string
  default     = "ap-southeast-1"
}

variable "cluster_name" {
  description = "EKS cluster created by envs/lab."
  type        = string
  default     = "minieyes-lab"
}

variable "argocd_chart_version" {
  description = "Exact argo-cd Helm chart version (https://github.com/argoproj/argo-helm/releases)."
  type        = string
  default     = "10.10.5"
}
