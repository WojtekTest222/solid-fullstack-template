locals {
  ou_name       = "APP-${upper(var.app_slug)}"
  is_debug_mode = var.bootstrap_mode == "debug"

  root_email_parts  = split("@", var.root_email_base)
  root_email_local  = local.root_email_parts[0]
  root_email_domain = local.root_email_parts[1]

  debug_suffix_segment       = var.debug_suffix == "" ? "" : "-${var.debug_suffix}"
  slug_has_debug_suffix      = var.debug_suffix != "" && endswith(var.app_slug, local.debug_suffix_segment)
  account_debug_suffix_value = local.slug_has_debug_suffix ? "" : local.debug_suffix_segment
  environment_accounts       = [for key in var.environment_accounts : lower(key)]

  accounts = {
    for key in local.environment_accounts : key => {
      name  = "APP-${upper(var.app_slug)}-${upper(key)}${upper(local.account_debug_suffix_value)}"
      email = "${local.root_email_local}+aws-${var.app_slug}-${key}${local.account_debug_suffix_value}@${local.root_email_domain}"
      tags = merge(
        {
          ManagedBy = "Terraform"
          App       = var.app_slug
          Account   = key
          Mode      = var.bootstrap_mode
        },
        var.tags
      )
    }
  }
}

