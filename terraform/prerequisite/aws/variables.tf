variable "aws_region" {
  description = "AWS region used by the provider."
  type        = string
  default     = "eu-central-1"
}

variable "github_org" {
  description = "GitHub owner that will host repositories created from the template."
  type        = string
  default     = ""

  validation {
    condition     = trim(var.github_org, " ") != ""
    error_message = "github_org is required and cannot be empty."
  }
}

variable "github_repo" {
  description = "GitHub repository name allowed to assume the bootstrap role from environment bootstrap."
  type        = string

  validation {
    condition     = trim(var.github_repo, " ") != "" && can(regex("^[A-Za-z0-9_.-]+$", var.github_repo))
    error_message = "github_repo is required and may contain only letters, numbers, underscore, dot, and hyphen."
  }
}

variable "github_oidc_role_name" {
  description = "IAM role name assumed by GitHub Actions through OIDC."
  type        = string
  default     = "gha-bootstrap-org"
}

variable "organization_account_access_role_name" {
  description = "Member-account role name assumed by bootstrap workflows (created by AWS Organizations)."
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "github_oidc_provider_arn" {
  description = "Optional ARN of existing GitHub OIDC provider. If set, Terraform will not create a new provider."
  type        = string
  default     = ""

  validation {
    condition     = var.github_oidc_provider_arn == "" || can(regex("^arn:[^:]+:iam::[0-9]{12}:oidc-provider/.+$", var.github_oidc_provider_arn))
    error_message = "github_oidc_provider_arn must be a valid IAM OIDC provider ARN or empty."
  }
}

variable "github_oidc_thumbprints" {
  description = "Thumbprints used when creating GitHub OIDC provider."
  type        = list(string)
  default     = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

variable "github_oidc_audience" {
  description = "OIDC audience expected from GitHub token."
  type        = string
  default     = "sts.amazonaws.com"
}

variable "github_subject_patterns" {
  description = "Optional list of sub claim patterns allowed in trust policy. If empty, defaults to repo environment bootstrap."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for pattern in var.github_subject_patterns : trim(pattern, " ") != ""])
    error_message = "github_subject_patterns cannot contain empty values."
  }
}

variable "tags" {
  description = "Additional tags added to prerequisite resources."
  type        = map(string)
  default     = {}
}
