# solid-fullstack-template

Template do szybkiego startu aplikacji z bootstrapem AWS Organizations + IAM + governance GitHub.

## 1. One-time prerequisite (na AWS management account + GitHub org)

1. Wykonaj AWS prerequisite:
   - [terraform/prerequisite/aws/README.md](terraform/prerequisite/aws/README.md)
1. Wykonaj GitHub prerequisite (GitHub App):
   - [terraform/prerequisite/gh/README.md](terraform/prerequisite/gh/README.md)
1. Ustaw GitHub Variables (repo lub org):
   - `AWS_REGION`
   - `AWS_ROLE_TO_ASSUME`
   - `TF_STATE_BUCKET`
   - `TF_LOCK_TABLE`
   - opcjonalnie `TF_STATE_KEY_PREFIX` (domyslnie workflow uzywa `bootstrap-org`)
1. Ustaw GitHub Secrets (repo lub org):
   - `GH_APP_ID`
   - `GH_APP_PRIVATE_KEY`

## 2. Per nowe repo utworzone z template (zalecany flow)

Uruchom workflow `bootstrap-all` i podaj:
- `app_slug` (np. `todo-list`)
- `root_email_base` (np. `owner@example.com`)
- `bootstrap_mode` (`safe` albo `debug`)
- `debug_suffix` (opcjonalnie, glownie dla `debug`)
- `preset` (`minimal`, `dev-lite`, `dev-standard`, `release`, `full-qa`)
- `aws_region` (opcjonalnie; puste = `AWS_REGION` z Variables)

`bootstrap-all` uruchamia automatycznie:
1. `bootstrap-org` (OU + konta AWS z presetu)
1. `bootstrap-iam-matrix` (rola `gha-environment-deploy` w kazdym koncie)
1. `bootstrap-gh-core` (branche, default branch, GitHub Environments)
1. `bootstrap-gh-bind` (AWS role vars per GitHub Environment)

Szczegoly workflow:
- [.github/workflows/README.md](.github/workflows/README.md)

## 3. Manualny fallback (gdy nie uzywasz orchestratora)

1. `bootstrap-org`
1. `bootstrap-iam-matrix`
1. `bootstrap-gh-core`
1. `bootstrap-gh-bind`

## 4. Presety

Kontrakt presetow jest w:
- [config/README.md](config/README.md)
- [config/presets.json](config/presets.json)
