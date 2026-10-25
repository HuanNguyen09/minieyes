variable "region" {
  description = "AWS region for the state bucket. The deployer policy only allows ap-southeast-1."
  type        = string
  default     = "ap-southeast-1"
}

variable "budget_alert_email" {
  description = "Email for the 30/60 USD budget alarms. Pass with -var or TF_VAR_budget_alert_email; never commit it."
  type        = string
}
