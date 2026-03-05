locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"
  oidc_audience   = "sts.amazonaws.com"
  oidc_thumbprints = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
  ]

  normalized_environment_name = lower(var.environment_name)
  effective_subjects          = var.subject_patterns
  effective_provider_arn      = aws_iam_openid_connect_provider.github.arn

  environment_policy_profile = contains(["dev", "preview"], local.normalized_environment_name) ? "dev_preview" : (
    contains(["prod"], local.normalized_environment_name) ? "prod" : (
      contains(["shared"], local.normalized_environment_name) ? "shared" : (
        contains(["logging"], local.normalized_environment_name) ? "logging" : "default"
      )
    )
  )

  prod_actions = [
    "acm:*",
    "apigateway:*",
    "application-autoscaling:*",
    "autoscaling:*",
    "cloudfront:*",
    "cloudwatch:*",
    "dynamodb:*",
    "ec2:*",
    "ecr:*",
    "ecs:*",
    "elasticloadbalancing:*",
    "events:*",
    "iam:CreateServiceLinkedRole",
    "iam:GetRole",
    "iam:ListRoles",
    "iam:PassRole",
    "kms:*",
    "lambda:*",
    "logs:*",
    "rds:*",
    "route53:*",
    "s3:*",
    "secretsmanager:*",
    "sns:*",
    "sqs:*",
    "ssm:*",
    "tag:*",
    "wafv2:*",
  ]

  dev_preview_actions = concat(
    local.prod_actions,
    ["iam:*"]
  )

  shared_actions = [
    "backup:*",
    "cloudwatch:*",
    "dynamodb:*",
    "events:*",
    "iam:CreateServiceLinkedRole",
    "iam:PassRole",
    "kms:*",
    "logs:*",
    "rds:*",
    "s3:*",
    "secretsmanager:*",
    "ssm:*",
    "tag:*",
  ]

  logging_actions = [
    "cloudwatch:*",
    "events:*",
    "firehose:*",
    "iam:CreateServiceLinkedRole",
    "iam:PassRole",
    "kinesis:*",
    "logs:*",
    "opensearch:*",
    "s3:*",
    "sns:*",
    "sqs:*",
    "tag:*",
  ]

  default_actions = local.dev_preview_actions

  policy_actions_by_profile = {
    prod        = local.prod_actions
    dev_preview = local.dev_preview_actions
    shared      = local.shared_actions
    logging     = local.logging_actions
    default     = local.default_actions
  }

  effective_policy_actions = lookup(local.policy_actions_by_profile, local.environment_policy_profile, local.default_actions)
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = local.github_oidc_url
  client_id_list  = [local.oidc_audience]
  thumbprint_list = local.oidc_thumbprints

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
      values   = [local.oidc_audience]
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

data "aws_iam_policy_document" "runtime_access" {
  statement {
    sid       = "EnvironmentRuntimeAccess"
    actions   = local.effective_policy_actions
    resources = ["*"]
  }
}

resource "aws_iam_policy" "runtime_access" {
  name   = "gha-environment-deploy-policy"
  policy = data.aws_iam_policy_document.runtime_access.json

  tags = merge(
    {
      ManagedBy = "Terraform"
      Purpose   = "github-actions-runtime-policy"
      Profile   = local.environment_policy_profile
    },
    var.tags
  )
}

resource "aws_iam_role_policy_attachment" "runtime_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.runtime_access.arn
}
