variable "aws_region" {
  description = "AWS region used by the provider."
  type        = string
  default     = "eu-central-1"
}

variable "app_slug" {
  description = "Application slug used to identify IAM bootstrap scope."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]+(?:-[a-z0-9]+)*$", var.app_slug))
    error_message = "app_slug must use kebab-case (lowercase letters, digits, hyphen)."
  }
}

variable "environment_name" {
  description = "Target environment/account name, e.g. prod, dev, preview, logging, shared."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment_name))
    error_message = "environment_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "target_account_id" {
  description = "Single AWS account ID where IAM resources should be created."
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.target_account_id))
    error_message = "target_account_id must be a 12-digit AWS account ID."
  }
}

variable "github_org" {
  description = "GitHub organization name used later for trust policy scoping."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$", var.github_org))
    error_message = "github_org must be a valid GitHub org/user name (1-39 chars, alphanumeric or hyphen)."
  }
}

variable "github_repo" {
  description = "GitHub repository name used later for trust policy scoping."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.github_repo)) && length(var.github_repo) <= 100
    error_message = "github_repo must contain only letters, digits, dot, underscore, or hyphen (max 100 chars)."
  }
}
