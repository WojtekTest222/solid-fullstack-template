# Preset Contract

`presets.json` is the single source of truth for bootstrap presets.

Each preset defines:
- `aws_accounts`: accounts that should be created/configured for the app
- `repo_branches`: branches that should exist in the app repository
- `default_branch`: repository default branch
- `enable_preview_pr`: whether preview-per-PR flow should be enabled

Current global rules:
- `prod` is always required.
- `preview` requires `dev`.
- `shared` is required when any account beyond `prod` is enabled.
- `logging` is required when `stage` or `test` is enabled.

Validate contract:

```ps
python scripts/validate-presets.py
```
