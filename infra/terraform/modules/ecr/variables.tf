variable "repositories" {
  description = "ECR repository names, one per service image. The deployer may only manage repositories named minieyes*."
  type        = list(string)

  validation {
    condition     = alltrue([for r in var.repositories : startswith(r, "minieyes")])
    error_message = "Every repository name must start with \"minieyes\"."
  }
}

variable "keep_images" {
  description = "Number of most recent images kept per repository; older ones expire."
  type        = number
  default     = 20
}

variable "force_delete" {
  description = "Delete repositories even if they contain images, so `terraform destroy` leaves nothing billable (NFR-6)."
  type        = bool
  default     = true
}
