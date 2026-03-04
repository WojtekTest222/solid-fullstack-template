locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"

  effective_subjects   = var.subject_patterns
  effective_provider_arn = aws_iam_openid_connect_provider.github.arn
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = local.github_oidc_url
  client_id_list  = [var.oidc_audience]
  thumbprint_list = var.oidc_thumbprints

  tags = merge(
    {
      ManagedBy = "Terraform"
      Purpose   = "github-oidc-provider"
    },
    var.tags
  )
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "GitHubActionsAssumeRole"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.effective_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [var.oidc_audience]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.effective_subjects
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "gha-environment-deploy"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = merge(
    {
      ManagedBy = "Terraform"
      Purpose   = "github-actions-oidc"
    },
    var.tags
  )
}

resource "aws_iam_role_policy_attachment" "managed" {
  for_each = toset(var.allowed_managed_policy_arns)

  role       = aws_iam_role.github_actions.name
  policy_arn = each.value
}
