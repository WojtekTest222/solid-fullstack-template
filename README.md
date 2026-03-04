# solid-fullstack-template

## Bootstrap Flow

1. Utwórz nowe repozytorium na podstawie szablonu `SOLID-FULLSTACK-TEMPLATE`.

1. Jeśli to pierwsze repo na tym koncie AWS:
    - sklonuj repo lokalnie,
    - skonfiguruj `aws-cli` / Identity Federation (SSO),
    - uruchom lokalnie Terraform `terraform/bootstrap-prerequisite`, który tworzy:
      - rolę OIDC dla GitHub Actions (np. `gha-bootstrap-org`),
      - bucket S3 dla backendów Terraform,
      - tabelę DynamoDB dla locków Terraform.

1. W GitHub (repo lub org) ustaw zmienne z outputów `bootstrap-prerequisite`:
    - `AWS_REGION`
    - `AWS_ROLE_TO_ASSUME`
    - `TF_LOCK_TABLE`
    - `TF_STATE_BUCKET`

1. Uruchom workflow `bootstrap-org`:
    - workflow pobiera token OIDC (`id-token: write`),
    - AWS trust policy pozwala temu tokenowi przyjąć rolę z `AWS_ROLE_TO_ASSUME`,
    - workflow uruchamia Terraform i tworzy OU + konta zgodnie z presetem.

1. Docelowo będzie jeden workflow orchestratora `bootstrap-all`, który uruchomi:
    - `bootstrap-org` (OU + konta),
    - `bootstrap-iam` (OIDC + role w kontach member),
    - `bootstrap-gh-core` (utworzenie environments/branches/rulesets),
    - `bootstrap-gh-bind` (powiązanie outputów AWS z GitHub env vars/secrets).
