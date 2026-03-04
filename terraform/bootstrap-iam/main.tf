data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

module "github_oidc_role" {
  source = "./modules/github-oidc-role"

  github_org                  = var.github_org
  github_repo                 = var.github_repo
  subject_patterns            = length(var.github_subject_patterns) > 0 ? var.github_subject_patterns : [local.default_subject_pattern]
  oidc_thumbprints            = var.github_oidc_thumbprints
  oidc_audience               = var.github_oidc_audience
  allowed_managed_policy_arns = var.iam_managed_policy_arns

  tags = merge(
    {
      App         = var.app_slug
      Environment = local.normalized_environment_name
      ManagedBy   = "Terraform"
    },
    var.tags
  )
}
