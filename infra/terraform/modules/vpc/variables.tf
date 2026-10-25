variable "name" {
  description = "Name prefix for the VPC and its resources, e.g. minieyes-cloud."
  type        = string

  validation {
    condition     = startswith(var.name, "minieyes-")
    error_message = "name must start with \"minieyes-\"."
  }
}

variable "cidr_block" {
  description = "IPv4 network CIDR of the VPC, e.g. 10.10.0.0/16 (prefix /16 to /24)."
  type        = string

  validation {
    # can() catches malformed addresses; the equality rejects host addresses such as 10.10.5.0/16.
    condition = (
      can(cidrhost(var.cidr_block, 0)) &&
      try(cidrsubnet(var.cidr_block, 0, 0) == var.cidr_block, false) &&
      try(tonumber(split("/", var.cidr_block)[1]) >= 16 && tonumber(split("/", var.cidr_block)[1]) <= 24, false)
    )
    error_message = "cidr_block must be a valid IPv4 network address with a prefix between /16 and /24."
  }
}

variable "public_subnet_count" {
  description = "Number of public subnets, each in its own availability zone."
  type        = number
  default     = 2

  validation {
    condition     = var.public_subnet_count >= 1 && var.public_subnet_count <= 4
    error_message = "public_subnet_count must be between 1 and 4."
  }
}

variable "public_subnet_tags" {
  description = "Extra tags for public subnets, e.g. kubernetes.io/role/elb = 1 for the EKS VPC."
  type        = map(string)
  default     = {}
}

variable "subnet_newbits" {
  description = "Bits added to the VPC prefix for each subnet (a /16 with 4 gives /20 subnets)."
  type        = number
  default     = 4
}
