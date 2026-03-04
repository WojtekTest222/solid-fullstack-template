# 1. Bootstrap Prerequisite

Ten katalog przygotowuje fundament pod automatyzacje GitHub Actions dla nowego repo:
- rola OIDC dla GitHub Actions (IAM),
- remote state backend Terraform (S3 + DynamoDB).

Stack tworzy backend remote state (S3 + DynamoDB) oraz role OIDC dla GitHub Actions.

## 1.1. Uruchomienie lokalne (SSO)

1. Przejdź do katalogu:
    ```ps
    Set-Location terraform/bootstrap-prerequisite
    ```
1. Ustaw profil:
    ```ps
    $env:AWS_PROFILE = "mafi-general-sso"
    ```
1. Zaloguj się:
    ```ps
    aws sso login --profile $env:AWS_PROFILE
    ```
1. Przygotuj plik zmiennych:
    ```ps
    Copy-Item terraform.tfvars.example terraform.tfvars
    ```
1. Uruchom Terraform:
    ```ps
    terraform init
    terraform plan -var-file="terraform.tfvars"
    terraform apply -var-file="terraform.tfvars"
    ```

## 1.2. Co jest tworzone

1. S3 bucket na Terraform state:
   - nazwa z `tf_state_bucket_name`, albo domyslnie `tfstate-<ACCOUNT_ID>-<REGION>`
   - versioning wlaczony
   - server-side encryption (AES256)
   - public access blocked
1. DynamoDB table do lockowania:
   - nazwa z `tf_lock_table_name`, albo domyslnie `terraform-locks`
   - `PAY_PER_REQUEST`
   - hash key `LockID`
1. IAM OIDC:
   - OIDC provider `token.actions.githubusercontent.com` (lub reuse przez `github_oidc_provider_arn`)
   - rola `github_oidc_role_name` z trust policy oparta o:
     - `github_org` + opcjonalnie `github_repo`
     - opcjonalne `github_subject_patterns`
   - permissions roli:
     - Terraform state (S3 + DynamoDB)
     - bootstrap organizacji (`organizations:*` wymagane przez `bootstrap-org`)
     - `sts:AssumeRole` do `OrganizationAccountAccessRole` w kontach member (wymagane przez `bootstrap-iam`)
1. Outputy:
   - `bootstrap_role_arn`
   - `bootstrap_role_name`
   - `github_oidc_provider_arn`
   - `github_subject_patterns`
   - `tf_state_bucket`
   - `tf_lock_table`
   - `aws_account_id`, `aws_partition`, `aws_region`

## 1.3. Następny zakres implementacji

1. Uruchomić workflow `.github/workflows/bootstrap-org.yml` przez `workflow_dispatch`.
1. Po zmianie uprawnień roli bootstrapowej uruchomić ponownie `terraform apply` w `bootstrap-prerequisite`, aby policy została zaktualizowana.
1. Ustawić wymagane Repo/Org Variables dla workflow:
   - `AWS_REGION` (np. `eu-central-1`)
   - `TF_STATE_BUCKET` (output `tf_state_bucket`)
   - `TF_LOCK_TABLE` (output `tf_lock_table`)
   - `TF_STATE_KEY_PREFIX` (np. `bootstrap-org`, opcjonalne)
   - jedna z opcji roli:
     - `AWS_ROLE_TO_ASSUME` (pełny ARN roli), albo
     - `AWS_ACCOUNT_ID` + `BOOTSTRAP_ROLE_NAME` (output `bootstrap_role_name`)
