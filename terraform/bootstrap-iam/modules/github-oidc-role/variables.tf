variable "github_org" {
  description = "GitHub organization or user allowed to assume the role."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository allowed to assume the role."
  type        = string
}

variable "subject_patterns" {
  description = "Allowed sub claim patterns in trust policy."
  type        = list(string)
}

variable "oidc_thumbprints" {
  description = "Thumbprints used when creating GitHub OIDC provider."
  type        = list(string)
  default     = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

variable "oidc_audience" {
  description = "OIDC audience expected from GitHub token."
  type        = string
  default     = "sts.amazonaws.com"
}

variable "allowed_managed_policy_arns" {
  description = "Managed policies attached to the role for bootstrap/deploy steps."
  type        = list(string)
  default     = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
}

variable "tags" {
  description = "Additional tags added to IAM resources."
  type        = map(string)
  default     = {}
}
