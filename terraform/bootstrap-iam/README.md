# 1. Bootstrap IAM

Ten katalog przygotowuje warstwe IAM dla kont utworzonych przez `bootstrap-org`.
Stack dziala w modelu single-account: jeden run konfiguruje IAM w jednym koncie docelowym.
Tworzy role OIDC dla GitHub Actions (provider + role + attachment policy) w koncie docelowym.
Docelowo ten stack bedzie uruchamiany w petli (matrix) dla kont wynikajacych z wybranego presetu.
Nazwa tworzonej roli jest stala: `gha-environment-deploy`.
Domyslny trust policy jest zawezony do GitHub Environment zgodnego z `environment_name`.

Na tym etapie dodany jest szkielet stacka. Kolejnym krokiem bedzie implementacja zasobow IAM.

## 1.1. Uruchomienie lokalne (SSO)

1. Przejdź do katalogu:
    ```ps
    Set-Location terraform/bootstrap-iam
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
1. Uzupełnij wymagane zmienne w `terraform.tfvars`:
    - `app_slug`
    - `environment_name`
    - `target_account_id`
    - `github_org`
    - `github_repo`
    - (opcjonalnie) `github_subject_patterns` gdy chcesz jawnie nadpisać domyślne wzorce `sub`
    - `iam_managed_policy_arns` (lista policy przypinanych do roli OIDC)
1. Uwaga dot. uprawnień roli:
    - `iam_managed_policy_arns` jest obecnie mechanizmem przejściowym.
    - Domyślnie przypinane jest `ReadOnlyAccess`, co zwykle nie wystarczy do pełnych deployów.
    - Docelowy kierunek: policy-as-code w tym stacku (`aws_iam_policy_document` + `aws_iam_policy`) z minimalnym zakresem per środowisko.
1. Uruchom Terraform:
    ```ps
    terraform init
    terraform plan -var-file="terraform.tfvars"
    terraform apply -var-file="terraform.tfvars"
    ```

## 1.2. Następny zakres implementacji

1. Dodać workflow matrix, ktory uruchomi ten stack dla kazdego konta z outputow `bootstrap-org`.
1. Doprecyzować minimalne policy IAM per typ konta (`prod/dev/preview/shared/logging`).
