variable "environment_name" {
  description = "Environment name used to select policy profile (prod/dev/preview/shared/logging)."
  type        = string
}

variable "subject_patterns" {
  description = "Allowed sub claim patterns in trust policy."
  type        = list(string)
}

variable "tags" {
  description = "Additional tags added to IAM resources."
  type        = map(string)
  default     = {}
}
