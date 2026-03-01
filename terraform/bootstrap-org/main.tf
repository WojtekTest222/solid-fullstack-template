locals {
  ou_name = "APP-${upper(var.app_slug)}"
}

data "aws_organizations_organization" "current" {}

resource "aws_organizations_organizational_unit" "app" {
  name      = local.ou_name
  parent_id = data.aws_organizations_organization.current.roots[0].id

  tags = merge(
    {
      ManagedBy = "Terraform"
      App       = var.app_slug
    },
    var.tags
  )
}
