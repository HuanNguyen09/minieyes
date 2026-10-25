variable "alert_email" {
  description = "Address that receives budget alerts. Pass it at apply time; never commit a real address."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be an email address."
  }
}

variable "limits_usd" {
  description = "Monthly cost alarms in USD (PRD §12, ADR-001)."
  type        = list(number)
  default     = [30, 60]
}
