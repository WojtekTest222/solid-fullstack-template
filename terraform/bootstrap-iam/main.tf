module "github_oidc_role" {
  source = "./modules/github-oidc-role"

  environment_name = local.normalized_environment_name
  subject_patterns = [local.default_subject_pattern]

  tags = (
    {
      App         = var.app_slug
      Environment = local.normalized_environment_name
      ManagedBy   = "Terraform"
    }
  )
}
