# 1. Bootstrap

Po sklonowaniu repozytorium, musisz utworzyć odpowiedną strukturę na swoim koncie AWS.
Wymagane jest połącznie z kontem AWS, które jest kontem Organization Managment Account.

## 1.1. Konfiguracja AWS-CLI

### 1.1.1. Jeśli korzystasz z Identity Federation (zalecana metoda)

Todo: Tu można bylo by dodać cały opis zakładania federacji.

1. Przejdź do katalogu bootstrap:
    ```ps
    Set-Location terraform/bootstrap-org
    ```
1. Ustaw profil:
    ```ps
    $env:AWS_PROFILE = "mafi-general-sso"
    ```
1. Skonfiguruj sso login:
    ```ps
    aws configure sso --profile $env:AWS_PROFILE
    ```
1. Zaloguj się:
    ```ps
    aws sso login --profile $env:AWS_PROFILE
    ```
1. Zobacz jako kto jesteś zalogowany:
    ```ps
    aws sts get-caller-identity --profile $env:AWS_PROFILE
    ```
1. Przygotuj plik zmiennych:
    ```ps
    Copy-Item terraform.tfvars.example terraform.tfvars
    ```
1. Po wykonaniu wcześniejszych kroków możesz wykonywać polecenia:
    ```ps
    terraform plan -var-file="terraform.tfvars"

    terraform apply -var-file="terraform.tfvars"

    terraform destroy -var-file="terraform.tfvars"
    ```
1. Jak włączyć i wyłączyć tryb:
    - `bootstrap_mode = "safe"`: konta mają `prevent_destroy = true`, więc `terraform destroy` nie zamknie kont.
    - `bootstrap_mode = "debug"`: konta są tworzone bez `prevent_destroy` i z `close_on_deletion = true`, więc `terraform destroy` może je zamknąć.
    - Używaj tego samego trybu dla `apply` i `destroy` w tym samym state.
    - Nie przełączaj istniejącego state między `safe` i `debug`; do innego trybu użyj nowego workspace/state.
    - `debug_suffix` (np. `dbg01`) dodaje suffix do nazwy i emaila konta, co ułatwia wielokrotne testowe uruchomienia.
1. Root email dla kont jest generowany z aliasem `+`, np.:
    - `mateusz+aws-todo-list-logging@outlook.com`
    - `mateusz+aws-todo-list-prod@outlook.com`
    - Gdy `app_slug` już kończy się na `-<debug_suffix>`, suffix nie jest dopinany drugi raz do nazwy konta i emaila.

### 1.1.2. Jeśli generujesz klucze CLI

Todo: uzupełnić tą sekcję.

## 1.2. Presety dla workflow `bootstrap-org.yml`

Workflow ma input `preset` typu `choice`. GitHub nie wspiera opisu per opcja w UI, dlatego legenda jest tutaj:

1. `minimal`
    - Konta: `prod`
    - Branche repo: `main`
    - Preview PR: `false`
1. `dev-lite`
    - Konta: `prod`, `dev`, `shared`
    - Branche repo: `main`, `dev`
    - Preview PR: `false`
1. `dev-standard` (domyślny)
    - Konta: `prod`, `dev`, `preview`, `shared`
    - Branche repo: `main`, `dev`
    - Preview PR: `true`
1. `release`
    - Konta: `prod`, `dev`, `stage`, `preview`, `shared`, `logging`
    - Branche repo: `main`, `dev`, `stage`
    - Preview PR: `true`
1. `full-qa`
    - Konta: `prod`, `dev`, `stage`, `test`, `preview`, `shared`, `logging`
    - Branche repo: `main`, `dev`, `stage`, `test`
    - Preview PR: `true`

Źródło prawdy presetów: `config/presets.json`.
