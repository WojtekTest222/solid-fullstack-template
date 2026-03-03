# 1. Bootstrap IAM

Ten katalog przygotowuje warstwe IAM dla kont utworzonych przez `bootstrap-org`.
Docelowo bedzie tworzyl role OIDC w kontach `prod/dev/preview/logging`, aby workflow deployowe mogly dzialac bez kluczy statycznych.

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
    - `github_org`
    - `github_repo`
    - `target_account_ids` (każde ID musi mieć 12 cyfr)
1. Uruchom Terraform:
    ```ps
    terraform init
    terraform plan -var-file="terraform.tfvars"
    terraform apply -var-file="terraform.tfvars"
    ```

## 1.2. Następny zakres implementacji

1. Dodać role OIDC per konto docelowe (`prod/dev/preview/logging`).
1. Dodać trust policy pod `github_org` i `github_repo`.
1. Wystawić outputy ARN rol do użycia w workflow deployowych.
