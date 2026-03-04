output "role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "role_name" {
  value = aws_iam_role.github_actions.name
}

output "oidc_provider_arn" {
  value = local.effective_provider_arn
}

output "subject_patterns" {
  value = local.effective_subjects
}
