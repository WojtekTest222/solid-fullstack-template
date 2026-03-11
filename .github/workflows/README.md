# Workflow bootstrap

## Zalecony workflow: `bootstrap-all.yml`

Uruchamiasz jeden workflow `workflow_dispatch`, a on wykonuje pelny lancuch:

1. `bootstrap-org`
1. `bootstrap-iam-matrix`
1. `bootstrap-gh-core`
1. `bootstrap-gh-bind`

### Inputy `bootstrap-all`

- `app_slug` - slug aplikacji, np. `todo-list`
- `root_email_base` - bazowy email bez aliasu `+`, np. `owner@example.com`
- `bootstrap_mode` - `safe` albo `debug`
- `debug_suffix` - opcjonalny suffix dla debug, np. `dbg01`
- `preset` - `minimal`, `dev-lite`, `dev-standard`, `release`, `full-qa`
- `aws_region` - opcjonalny override regionu

### Wymagane Variables

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `BOOTSTRAP_ROLE_NAME`
- `TF_STATE_BUCKET`

Alternatywnie zamiast `AWS_ACCOUNT_ID` + `BOOTSTRAP_ROLE_NAME` mozesz ustawic `AWS_ROLE_TO_ASSUME`.

### Wymagane Secrets

- `GH_APP_ID`
- `GH_APP_PRIVATE_KEY`

## Manualny fallback

Jesli nie uzywasz orchestratora, odpal workflowy recznie w kolejnosci:
1. `bootstrap-org.yml`
1. `bootstrap-iam-matrix.yml`
1. `bootstrap-gh-core.yml`
1. `bootstrap-gh-bind.yml`
