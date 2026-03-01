variable "aws_region" {
  description = "AWS region used by the provider."
  type        = string
  default     = "eu-central-1"
}

variable "app_slug" {
  description = "Application slug used to derive the organization unit name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.app_slug))
    error_message = "app_slug must use lowercase letters, numbers, and hyphens only."
  }
}

variable "tags" {
  description = "Additional tags added to the organization unit."
  type        = map(string)
  default     = {}
}
