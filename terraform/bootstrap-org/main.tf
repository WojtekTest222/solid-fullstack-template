provider "aws" {
  region = "eu-central-1"
}

data "aws_organizations_organization" "current" {}

resource "aws_organizations_organizational_unit" "app_todo_list" {
  name      = "APP-TODO-LIST"
  parent_id = data.aws_organizations_organization.current.roots[0].id

  tags = {
    ManagedBy = "Terraform"
    App       = "todo-list"
  }
}
