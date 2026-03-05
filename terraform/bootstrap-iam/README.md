# 1. Bootstrap IAM

Ten katalog przygotowuje warstwe IAM dla kont utworzonych przez `bootstrap-org`.
Stack dziala w modelu single-account: jeden run konfiguruje IAM w jednym koncie docelowym.
Tworzy role OIDC dla GitHub Actions (provider + role + attachment policy) w koncie docelowym.
Docelowo ten stack bedzie uruchamiany w petli (matrix) dla kont wynikajacych z wybranego presetu.
Nazwa tworzonej roli jest stala: `gha-environment-deploy`.
Domyslny trust policy jest zawezony do GitHub Environment zgodnego z `environment_name`.
Na tym etapie zasoby IAM sa juz zaimplementowane dla modelu single-account.
Kolejne kroki to uruchamianie matrix/orchestrator oraz dalszy hardening policy.

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
1. Uwaga dot. uprawnień roli:
    - Docelowo i domyślnie stosowane jest policy-as-code (`aws_iam_policy_document` + `aws_iam_policy`) z profilem zaleznym od `environment_name`.
    - Profile:
      - `prod`: runtime/deploy bez pelnego `iam:*`
      - `dev` i `preview`: najszerszy zakres (w tym `iam:*`) do szybkiej iteracji
      - `shared`: zakres pod wspolne zasoby platformowe
      - `logging`: zakres pod pipeline/logging stack
1. Uruchom Terraform:
    ```ps
    terraform init
    terraform plan -var-file="terraform.tfvars"
    terraform apply -var-file="terraform.tfvars"
    ```

## 1.2. Następny zakres implementacji

1. Spiac workflow matrix z orchestratorem `bootstrap-all`, aby uruchamial sie automatycznie po `bootstrap-org`.
1. Dalszy hardening policy-as-code do faktycznie uzywanych serwisow runtime.

## 1.3. Workflow manualny

Workflow `bootstrap-iam.yml` jest workflow wewnętrznym (`workflow_call`), uruchamianym przez `bootstrap-iam-matrix.yml`.

`bootstrap-iam.yml` wykonuje zawsze:
1. `terraform plan`
1. `terraform apply`

Workflow używa:
- roli bootstrapowej z `AWS_ROLE_TO_ASSUME` (management account),
- backendu z `TF_STATE_BUCKET` i `TF_LOCK_TABLE`,
- `OrganizationAccountAccessRole` do wejścia na konto docelowe i utworzenia roli `gha-environment-deploy`.

## 1.4. Workflow matrix

Dostępny jest także workflow `bootstrap-iam-matrix.yml` (workflow_dispatch), który:
- czyta `account_ids` ze state `bootstrap-org` dla podanego `app_slug`,
- buduje matrix `environment_name -> target_account_id`,
- uruchamia `bootstrap-iam.yml` dla każdego konta.

Inputy:
- `app_slug` (wymagane),
- `environments` (opcjonalny filtr, np. `prod,dev,preview`),
- `aws_region` (opcjonalny override).
