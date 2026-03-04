output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_partition" {
  value = data.aws_partition.current.partition
}

output "aws_region" {
  value = var.aws_region
}

output "environment_name" {
  value = local.normalized_environment_name
}

output "target_account_id" {
  value = var.target_account_id
}

output "account_access_role_arn" {
  value = local.account_access_role_arn
}

output "github_oidc_role_arn" {
  value = module.github_oidc_role.role_arn
}

output "github_oidc_role_name" {
  value = module.github_oidc_role.role_name
}

output "github_oidc_provider_arn" {
  value = module.github_oidc_role.oidc_provider_arn
}

output "github_subject_patterns" {
  value = module.github_oidc_role.subject_patterns
}
