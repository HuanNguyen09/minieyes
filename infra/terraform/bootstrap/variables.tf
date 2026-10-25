variable "region" {
  description = "AWS region for the state bucket. The deployer policy only allows ap-southeast-1."
  type        = string
  default     = "ap-southeast-1"
}
