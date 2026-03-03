variable "aws_region" {
  description = "AWS region used by the provider."
  type        = string
  default     = "eu-central-1"
}

variable "app_slug" {
  description = "Application slug used to identify IAM bootstrap scope."
  type        = string
  default     = ""
}

variable "target_account_ids" {
  description = "Map of environment account names to account IDs, e.g. { prod = \"123...\", dev = \"456...\" }."
  type        = map(string)
  default     = {}
}

variable "organization_account_access_role_name" {
  description = "Role name used to access member accounts after they are created by Organizations."
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "github_org" {
  description = "GitHub organization name used later for trust policy scoping."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name used later for trust policy scoping."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags added to resources created by bootstrap-iam."
  type        = map(string)
  default     = {}
}
