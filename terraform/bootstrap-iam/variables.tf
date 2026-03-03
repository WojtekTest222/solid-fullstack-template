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

variable "target_account_ids" {
  description = "Map of environment account names to account IDs, e.g. { prod = \"123...\", dev = \"456...\" }."
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for account_id in values(var.target_account_ids) : can(regex("^\\d{12}$", account_id))
    ])
    error_message = "Each target_account_ids value must be a 12-digit AWS account ID."
  }
}

variable "organization_account_access_role_name" {
  description = "Role name used to access member accounts after they are created by Organizations."
  type        = string
  default     = "OrganizationAccountAccessRole"
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

variable "tags" {
  description = "Additional tags added to resources created by bootstrap-iam."
  type        = map(string)
  default     = {}
}
