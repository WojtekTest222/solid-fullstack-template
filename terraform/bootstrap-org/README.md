# bootstrap-org

Tworzy OU i konta AWS Organizations dla aplikacji.

Zalecane uruchomienie: przez `bootstrap-all`.

## 1. Co tworzy

1. Organizational Unit: `APP-<APP_SLUG>`
1. Konta z listy `environment_accounts` (w workflow wyliczane z `preset`)
1. Outputy state:
   - `ou_id`, `ou_arn`, `ou_name`
   - `account_ids`, `account_arns`, `account_emails`

## 2. Tryby bootstrapu

- `bootstrap_mode = "safe"`
  - `prevent_destroy = true` na kontach
  - `terraform destroy` nie zamknie kont
- `bootstrap_mode = "debug"`
  - brak `prevent_destroy`
  - `close_on_deletion = true`
  - `terraform destroy` moze zamknac konta (operacja asynchroniczna)

`debug_suffix` dodaje suffix do nazwy OU/kont i aliasu email.

## 3. Workflow inputs (bootstrap-org.yml)

- `app_slug`
- `root_email_base`
- `bootstrap_mode`
- `debug_suffix` (opcjonalny)
- `debug_confirmation` (`YES` wymagane dla `debug`)
- `preset`
- `aws_region` (opcjonalny override)

Presety i ich kontrakt:
- [config/README.md](../../config/README.md)

## 4. Lokalny run (fallback)

1. Przejdz do katalogu:
   ```ps
   Set-Location terraform/bootstrap-org
   ```
1. Ustaw profil i login:
   ```ps
   $env:AWS_PROFILE = "mafi-general-sso"
   aws sso login --profile $env:AWS_PROFILE
   ```
1. Przygotuj zmienne:
   ```ps
   Copy-Item terraform.tfvars.example terraform.tfvars
   ```
1. Uruchom:
   ```ps
   terraform init
   terraform plan -var-file="terraform.tfvars"
   terraform apply -var-file="terraform.tfvars"
   ```
