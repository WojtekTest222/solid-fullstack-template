locals {
  normalized_target_account_ids = {
    for name, id in var.target_account_ids : lower(name) => id
  }
}
