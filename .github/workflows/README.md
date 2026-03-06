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
- `AWS_ROLE_TO_ASSUME`
- `TF_STATE_BUCKET`
- `TF_LOCK_TABLE`
- opcjonalnie `TF_STATE_KEY_PREFIX`

### Wymagane Secrets

- `GH_APP_ID`
- `GH_APP_PRIVATE_KEY`

## Manualny fallback

Jesli nie uzywasz orchestratora, odpal workflowy recznie w kolejnosci:
1. `bootstrap-org.yml`
1. `bootstrap-iam-matrix.yml`
1. `bootstrap-gh-core.yml`
1. `bootstrap-gh-bind.yml`
