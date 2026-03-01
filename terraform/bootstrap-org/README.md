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
1. Po wykonaniu wcześniejszych kroków możesz wykonywać polecenia:
    ```ps
    terraform plan

    terraform apply

    terraform destroy
    ```

### 1.1.2. Jeśli generujesz klucze CLI

Todo: uzupełnić tą sekcję.
