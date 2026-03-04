locals {
  github_oidc_url = "https://token.actions.githubusercontent.com"

  default_github_subject              = var.github_repo != "" ? "repo:${var.github_org}/${var.github_repo}:*" : "repo:${var.github_org}/*"
  effective_github_subject_patterns   = length(var.github_subject_patterns) > 0 ? var.github_subject_patterns : [local.default_github_subject]
  effective_github_oidc_provider_arn  = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
  tf_state_key_prefix_trimmed         = trim(var.tf_state_key_prefix, "/")
  effective_tf_state_object_arn_scope = local.tf_state_key_prefix_trimmed == "" ? "${aws_s3_bucket.tf_state.arn}/*" : "${aws_s3_bucket.tf_state.arn}/${local.tf_state_key_prefix_trimmed}/*"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.github_oidc_provider_arn == "" ? 1 : 0

  url             = local.github_oidc_url
  client_id_list  = [var.github_oidc_audience]
  thumbprint_list = var.github_oidc_thumbprints

  tags = merge(
    {
      ManagedBy = "Terraform"
      Purpose   = "github-oidc-provider"
    },
    var.tags
  )
}

data "aws_iam_policy_document" "github_oidc_assume_role" {
  statement {
    sid     = "GitHubActionsAssumeRole"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.effective_github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [var.github_oidc_audience]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.effective_github_subject_patterns
    }
  }
}

resource "aws_iam_role" "github_actions_bootstrap" {
  name               = var.github_oidc_role_name
  assume_role_policy = data.aws_iam_policy_document.github_oidc_assume_role.json

  tags = merge(
    {
      ManagedBy = "Terraform"
      Purpose   = "github-actions-bootstrap"
    },
    var.tags
  )
}

data "aws_iam_policy_document" "github_actions_bootstrap_permissions" {
  statement {
    sid = "OrganizationsBootstrap"
    actions = [
      "organizations:CloseAccount",
      "organizations:CreateAccount",
      "organizations:CreateOrganizationalUnit",
      "organizations:DeleteOrganizationalUnit",
      "organizations:Describe*",
      "organizations:List*",
      "organizations:MoveAccount",
      "organizations:TagResource",
      "organizations:UntagResource",
      "organizations:UpdateOrganizationalUnit",
    ]
    resources = ["*"]
  }

  statement {
    sid = "StateBucketList"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.tf_state.arn]
  }

  statement {
    sid = "StateObjectsReadWrite"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [local.effective_tf_state_object_arn_scope]
  }

  statement {
    sid = "DynamoDbStateLocking"
    actions = [
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.tf_lock.arn]
  }

  statement {
    sid = "AssumeOrganizationAccountAccessRole"
    actions = [
      "sts:AssumeRole",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:iam::*:role/${var.organization_account_access_role_name}",
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_bootstrap_permissions" {
  name   = "${var.github_oidc_role_name}-bootstrap-org"
  role   = aws_iam_role.github_actions_bootstrap.id
  policy = data.aws_iam_policy_document.github_actions_bootstrap_permissions.json
}
