# AWS prerequisite

Ten stack wykonujesz raz na management account. Tworzy fundament pod wszystkie kolejne bootstrapy repo.

## 1. Co tworzy

1. S3 bucket na Terraform state
1. DynamoDB table do lockowania state
1. OIDC provider `token.actions.githubusercontent.com` (lub reuse)
1. Rola bootstrapowa dla GitHub Actions (domyslnie `gha-bootstrap-org`)

## 2. Uruchomienie lokalne (SSO)

1. Przejdz do katalogu:
   ```ps
   Set-Location terraform/prerequisite/aws
   ```
1. Ustaw profil:
   ```ps
   $env:AWS_PROFILE = "mafi-general-sso"
   ```
1. Zaloguj sie:
   ```ps
   aws sso login --profile $env:AWS_PROFILE
   ```
1. Przygotuj plik zmiennych:
   ```ps
   Copy-Item terraform.tfvars.example terraform.tfvars
   ```
1. Uruchom:
   ```ps
   terraform init
   terraform plan -var-file="terraform.tfvars"
   terraform apply -var-file="terraform.tfvars"
   ```

## 3. Co ustawic po apply w GitHub

Ustaw Variables (repo albo org):
- `AWS_REGION` (output `aws_region`)
- `AWS_ROLE_TO_ASSUME` (output `bootstrap_role_arn`)
- `TF_STATE_BUCKET` (output `tf_state_bucket`)
- `TF_LOCK_TABLE` (output `tf_lock_table`)
- opcjonalnie `TF_STATE_KEY_PREFIX` (jesli chcesz inny prefix niz `bootstrap-org`)

Alternatywa dla `AWS_ROLE_TO_ASSUME`:
- `AWS_ACCOUNT_ID` + `BOOTSTRAP_ROLE_NAME`

## 4. Najwazniejsze inputy

- `github_org` - wymagany
- `github_repo` - opcjonalny (zawaza trust policy do jednego repo)
- `github_subject_patterns` - opcjonalne wzorce `sub` dla OIDC
