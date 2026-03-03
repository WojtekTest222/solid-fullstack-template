#!/usr/bin/env python3
"""
Validate preset contract in config/presets.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRESETS_PATH = ROOT / "config" / "presets.json"

ALLOWED_ACCOUNTS = {
    "prod",
    "dev",
    "stage",
    "test",
    "preview",
    "shared",
    "logging",
    "security",
}


def _error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def _read_presets(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _error(f"Missing presets file: {path}")
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        _error(f"Invalid JSON in {path}: {exc}")
        raise SystemExit(1)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _validate_preset(name: str, preset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    accounts_raw = preset.get("aws_accounts")
    branches_raw = preset.get("repo_branches")
    default_branch = preset.get("default_branch")
    enable_preview_pr = preset.get("enable_preview_pr")

    if not isinstance(accounts_raw, list) or len(accounts_raw) == 0:
        errors.append(f"{name}: aws_accounts must be a non-empty list")
        return errors

    if not isinstance(branches_raw, list) or len(branches_raw) == 0:
        errors.append(f"{name}: repo_branches must be a non-empty list")
        return errors

    accounts = [str(x).strip().lower() for x in accounts_raw]
    branches = [str(x).strip() for x in branches_raw]

    if len(set(accounts)) != len(accounts):
        errors.append(f"{name}: aws_accounts must be unique")
    if len(set(branches)) != len(branches):
        errors.append(f"{name}: repo_branches must be unique")

    unknown_accounts = sorted(set(accounts) - ALLOWED_ACCOUNTS)
    if unknown_accounts:
        errors.append(f"{name}: unknown aws_accounts: {', '.join(unknown_accounts)}")

    if "prod" not in accounts:
        errors.append(f"{name}: prod account is required")

    if "preview" in accounts and "dev" not in accounts:
        errors.append(f"{name}: preview requires dev")

    if any(account != "prod" for account in accounts) and "shared" not in accounts:
        errors.append(f"{name}: shared is required if there are accounts beyond prod")

    if ("stage" in accounts or "test" in accounts) and "logging" not in accounts:
        errors.append(f"{name}: logging is required when stage or test is enabled")

    if "dev" in accounts and "dev" not in branches:
        errors.append(f"{name}: dev account requires dev branch")
    if "stage" in accounts and "stage" not in branches:
        errors.append(f"{name}: stage account requires stage branch")
    if "test" in accounts and "test" not in branches:
        errors.append(f"{name}: test account requires test branch")

    if not _is_non_empty_string(default_branch):
        errors.append(f"{name}: default_branch must be a non-empty string")
    elif default_branch not in branches:
        errors.append(f"{name}: default_branch must exist in repo_branches")

    if not isinstance(enable_preview_pr, bool):
        errors.append(f"{name}: enable_preview_pr must be true/false")
    elif enable_preview_pr and "preview" not in accounts:
        errors.append(f"{name}: enable_preview_pr=true requires preview account")

    return errors


def main() -> int:
    data = _read_presets(PRESETS_PATH)
    errors: list[str] = []

    if not isinstance(data, dict):
        _error("Top-level structure must be a JSON object.")
        return 1

    version = data.get("version")
    if not isinstance(version, int) or version <= 0:
        errors.append("version must be a positive integer")

    presets = data.get("presets")
    if not isinstance(presets, dict) or len(presets) == 0:
        errors.append("presets must be a non-empty object")
    else:
        for preset_name, preset_body in presets.items():
            if not _is_non_empty_string(preset_name):
                errors.append("preset name must be a non-empty string")
                continue
            if not isinstance(preset_body, dict):
                errors.append(f"{preset_name}: preset definition must be an object")
                continue
            errors.extend(_validate_preset(preset_name, preset_body))

    if errors:
        for message in errors:
            _error(message)
        return 1

    print(f"[OK] Preset contract is valid: {PRESETS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
