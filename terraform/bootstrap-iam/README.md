# bootstrap-iam

Tworzy IAM OIDC role `gha-environment-deploy` w kontach utworzonych przez `bootstrap-org`.

## 1. Jak to dziala

1. `bootstrap-iam-matrix.yml` czyta `account_ids` ze state `bootstrap-org`
1. Buduje matrix: `environment_name -> target_account_id`
1. Dla kazdego konta uruchamia `bootstrap-iam.yml` (workflow wewnetrzny)
1. `bootstrap-iam.yml` tworzy OIDC provider + role IAM w koncie docelowym

## 2. Co jest tworzone

- OIDC provider: `token.actions.githubusercontent.com` (w koncie docelowym)
- Rola: `gha-environment-deploy`
- Trust policy zawezona do:
  - `repo:<github_org>/<github_repo>:environment:<environment_name>`
- Policy-as-code zalezne od `environment_name` (`prod`, `dev`, `preview`, `shared`, `logging`)

## 3. Workflow matrix (manualny run)

Inputy `bootstrap-iam-matrix.yml`:
- `app_slug` (wymagane)
- `environments` (opcjonalny filtr, np. `prod,dev,preview`)
- `aws_region` (opcjonalny override)

Zalecane uruchomienie: przez `bootstrap-all`.

## 4. Lokalny run (fallback)

1. Przejdz do katalogu:
   ```ps
   Set-Location terraform/bootstrap-iam
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
1. Uzupelnij `terraform.tfvars`:
   - `app_slug`
   - `environment_name`
   - `target_account_id`
   - `github_org`
   - `github_repo`
1. Uruchom:
   ```ps
   terraform init
   terraform plan -var-file="terraform.tfvars"
   terraform apply -var-file="terraform.tfvars"
   ```
