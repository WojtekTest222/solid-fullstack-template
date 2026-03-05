locals {
  normalized_environment_name = lower(var.environment_name)
  account_access_role_arn     = "arn:aws:iam::${var.target_account_id}:role/OrganizationAccountAccessRole"
  default_subject_pattern     = "repo:${var.github_org}/${var.github_repo}:environment:${local.normalized_environment_name}"
}
