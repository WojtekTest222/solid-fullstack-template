variable "aws_region" {
  description = "AWS region used by the provider."
  type        = string
  default     = "eu-central-1"
}

variable "github_org" {
  description = "GitHub organization that will host repositories created from the template."
  type        = string
  default     = ""

  validation {
    condition     = trim(var.github_org, " ") != ""
    error_message = "github_org is required and cannot be empty."
  }
}

variable "github_repo" {
  description = "Optional repository name to scope the trust policy to a single repo. Leave empty to trust the whole org."
  type        = string
  default     = ""

  validation {
    condition     = var.github_repo == "" || can(regex("^[A-Za-z0-9_.-]+$", var.github_repo))
    error_message = "github_repo may contain only letters, numbers, underscore, dot, and hyphen."
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

variable "tf_state_bucket_name" {
  description = "S3 bucket name used for Terraform remote state."
  type        = string
  default     = ""
}

variable "tf_lock_table_name" {
  description = "DynamoDB table name used for Terraform state locking."
  type        = string
  default     = ""
}

variable "tf_state_key_prefix" {
  description = "Optional key prefix in S3 bucket that the bootstrap role may access (for Terraform states)."
  type        = string
  default     = ""
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
  description = "Optional list of sub claim patterns allowed in trust policy. If empty, defaults to org or repo scope."
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
