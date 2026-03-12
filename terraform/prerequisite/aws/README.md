# AWS prerequisite

Ten stack wykonujesz raz na management account. Tworzy fundament pod wszystkie kolejne bootstrapy repo.

## 1. Co tworzy

1. S3 bucket na Terraform state
1. DynamoDB table do lockowania state
1. OIDC provider `token.actions.githubusercontent.com` (lub reuse)
1. Rola bootstrapowa dla GitHub Actions (domyslnie `gha-bootstrap-org`)

Konwencje:
- bucket: `tfstate-<ACCOUNT_ID>-<REGION>`
- lock table: `terraform-locks`
- bootstrap role name: `gha-bootstrap-org`
- state prefix dla workflow: `bootstrap-org`

## 2. Szybki start (zalecane)

```ps1
Set-Location terraform/prerequisite/aws

$env:AWS_PROFILE = "mafi-general-sso"
aws sso login --profile $env:AWS_PROFILE
gh auth login

python bootstrap-aws.py `
  --org KnightRadiants `
  --repo solid-fullstack-template-manual `
  --aws-region eu-central-1
```

Jesli nie ustawisz `AWS_PROFILE` i nie podasz `--aws-profile`, skrypt wyswietli profile znalezione w `~/.aws` i poprosi o wybor strzalkami.
Do ustawiania org-level GitHub Variables potrzebny jest `gh` z zakresem `admin:org`.
Jesli go brakuje, skrypt sprobuje uruchomic `gh auth refresh -h github.com -s admin:org`.
Skrypt najpierw sprawdza stan trzech zasobow bootstrapowych:
- S3 bucket
- DynamoDB table
- IAM role
Jesli istnieja wszystkie trzy, pominie `terraform apply`.
Jesli nie istnieje zaden, utworzy je przez Terraform.
Jesli istnieje tylko czesc z nich, przerwie sie z bledem i lista brakujacych/istniejacych zasobow.

Co zrobi skrypt:
1. Sprawdzi, czy wymagane zasoby bootstrapowe juz istnieja na koncie.
1. Wykona `terraform init` i `terraform apply` tylko wtedy, gdy nie istnieje zaden z nich.
1. Odczyta output `tf_state_bucket`.
1. Ustawi org-level GitHub Variables ograniczone do wskazanego repo:
   - `AWS_REGION`
   - `AWS_ACCOUNT_ID`
   - `BOOTSTRAP_ROLE_NAME`
   - `TF_STATE_BUCKET`

## 3. Manualny fallback (SSO)

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

Po manualnym `apply` ustaw w GitHub Variables (repo albo org):
- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `BOOTSTRAP_ROLE_NAME`
- `TF_STATE_BUCKET` (output `tf_state_bucket`)

## 4. Najwazniejsze inputy

- `github_org` - wymagany
- `github_repo` - wymagany w zalecanym flow; zawaza trust policy do jednego repo na branch `main`
- `github_subject_patterns` - opcjonalne wzorce `sub` dla OIDC

Przy ponownym uruchomieniu `bootstrap-aws.py` dla kolejnego repo, jesli zasoby AWS juz istnieja, skrypt nie tworzy ich od nowa. Zamiast tego dopisuje nowe `repo:<org>/<repo>:ref:refs/heads/main` do trust policy roli `gha-bootstrap-org` i zachowuje juz dopuszczone repo.
