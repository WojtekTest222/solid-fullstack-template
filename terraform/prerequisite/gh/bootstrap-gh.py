#!/usr/bin/env python3
"""
Local orchestrator for GitHub prerequisite bootstrap.

Stage order:
1) Ensure GitHub App credentials (create once, then reuse from app/out).
2) Ensure administrators team baseline.
3) Upsert required GitHub App secrets via gh CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_APP_PREFIX = "gha"
MAX_GITHUB_APP_NAME_LENGTH = 34
DEFAULT_ORG_SEGMENT_LENGTH = 20
DEFAULT_APP_SUFFIX_LENGTH = 6
GH_WRITE_MAX_ATTEMPTS = 4
SHARED_CREDENTIALS_DIR_NAME = "gh-app-credentials"
SSM_APP_CREDENTIALS_ROOT = "/solid-fullstack-template/bootstrap/github-apps"
APP_INSTALL_WAIT_TIMEOUT_SECONDS = 600
APP_INSTALL_WAIT_POLL_SECONDS = 5
ANSI_RED = "\033[91m"
ANSI_RESET = "\033[0m"


def red(text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"{ANSI_RED}{text}{ANSI_RESET}"


def print_step(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def format_local_time(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M:%S")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def run_command_live_checked(command: list[str], *, description: str = "") -> None:
    if description:
        print_step(description)
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        message = (
            f"{description}\n" if description else ""
        ) + f"Command failed ({result.returncode}): {' '.join(command)}"
        raise RuntimeError(message)


def run_command_checked(command: list[str], *, description: str = "") -> str:
    if description:
        print_step(description)
    result = run_command(command)
    if result.returncode != 0:
        message = (
            f"{description}\n" if description else ""
        ) + (
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
        raise RuntimeError(message)
    return result.stdout.strip()


def is_retryable_gh_write_failure(result: subprocess.CompletedProcess[str]) -> bool:
    error_text = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).lower()
    retryable_patterns = [
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "bad gateway",
        "gateway timeout",
        "temporarily unavailable",
        "connection reset",
        "connection timed out",
    ]
    return any(pattern in error_text for pattern in retryable_patterns)


def run_command_checked_with_retry(
    command: list[str],
    *,
    description: str = "",
    max_attempts: int = GH_WRITE_MAX_ATTEMPTS,
) -> str:
    if description:
        print_step(description)

    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, max_attempts + 1):
        result = run_command(command)
        last_result = result
        if result.returncode == 0:
            return result.stdout.strip()

        if attempt < max_attempts and is_retryable_gh_write_failure(result):
            delay_seconds = attempt
            print_step(
                f"GitHub API returned a transient error. Retrying in {delay_seconds}s "
                f"({attempt}/{max_attempts - 1} retries used)..."
            )
            time.sleep(delay_seconds)
            continue

        message = (
            f"{description}\n" if description else ""
        ) + (
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
        raise RuntimeError(message)

    if last_result is None:
        raise RuntimeError(f"Command failed before execution: {' '.join(command)}")
    raise RuntimeError(f"Command failed ({last_result.returncode}): {' '.join(command)}")


def slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def build_default_app_name(org: str) -> str:
    org_slug = slugify(org)
    org_segment = org_slug[:DEFAULT_ORG_SEGMENT_LENGTH].strip("-") or "org"
    suffix = hashlib.sha1(org.strip().lower().encode("utf-8")).hexdigest()[:DEFAULT_APP_SUFFIX_LENGTH]
    app_name = f"{DEFAULT_APP_PREFIX}-{org_segment}-{suffix}"
    return app_name[:MAX_GITHUB_APP_NAME_LENGTH].strip("-")


def shared_credentials_root() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data) / "solid-fullstack-template" / SHARED_CREDENTIALS_DIR_NAME

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache_home:
        return Path(xdg_cache_home) / "solid-fullstack-template" / SHARED_CREDENTIALS_DIR_NAME
    return Path.home() / ".cache" / "solid-fullstack-template" / SHARED_CREDENTIALS_DIR_NAME


def shared_credentials_dir(owner: str) -> Path:
    return shared_credentials_root() / slugify(owner or "default-org")


def credential_search_dirs(output_dir: Path, *, owner: str) -> list[Path]:
    seen: set[str] = set()
    search_dirs: list[Path] = []
    for candidate in [output_dir, shared_credentials_dir(owner)]:
        resolved = candidate.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        search_dirs.append(resolved)
    return search_dirs


def resolve_aws_region(region_arg: str) -> str:
    return (
        region_arg.strip()
        or os.environ.get("AWS_REGION", "").strip()
        or os.environ.get("AWS_DEFAULT_REGION", "").strip()
    )


def ssm_parameter_path(*, owner: str, app_id: str) -> str:
    return f"{SSM_APP_CREDENTIALS_ROOT}/{slugify(owner or 'default-org')}/{app_id}"


def ssm_storage_enabled(*, aws_region: str) -> bool:
    return bool(aws_region.strip())


def ssm_payload_from_credentials(*, owner: str, payload: dict, private_key_pem: str) -> dict[str, str]:
    return {
        "app_id": str(payload["id"]),
        "app_name": str(payload.get("name", "")).strip(),
        "app_slug": str(payload.get("slug", "")).strip(),
        "owner_login": owner,
        "private_key_pem": private_key_pem,
    }


def credentials_files_from_ssm_payload(ssm_payload: dict[str, str], *, target_dir: Path) -> tuple[Path, Path]:
    app_id = str(ssm_payload.get("app_id", "")).strip()
    if not app_id:
        raise RuntimeError("SSM GitHub App payload is missing app_id.")

    private_key_pem = str(ssm_payload.get("private_key_pem", "")).strip()
    if not private_key_pem:
        raise RuntimeError(f"SSM GitHub App payload for app '{app_id}' is missing private_key_pem.")

    owner_login = str(ssm_payload.get("owner_login", "")).strip()
    credentials_payload = {
        "id": int(app_id) if app_id.isdigit() else app_id,
        "name": str(ssm_payload.get("app_name", "")).strip(),
        "slug": str(ssm_payload.get("app_slug", "")).strip(),
        "owner": {
            "login": owner_login,
        },
    }

    target_dir.mkdir(parents=True, exist_ok=True)
    credentials_file = target_dir / f"github-app-{app_id}.credentials.json"
    private_key_file = target_dir / f"github-app-{app_id}.private-key.pem"
    credentials_file.write_text(json.dumps(credentials_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    private_key_file.write_text(private_key_pem, encoding="utf-8")
    return credentials_file, private_key_file


def prompt_with_default(value: str, prompt_text: str, *, default: str = "") -> str:
    normalized = value.strip()
    if normalized:
        return normalized

    if not sys.stdin.isatty():
        if default:
            return default
        raise RuntimeError(f"Missing required value: {prompt_text}")

    suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{prompt_text}{suffix}: ").strip()
        if answer:
            return answer
        if default:
            return default
        print("Value is required.")


def read_menu_key() -> str:
    if os.name == "nt":
        import msvcrt

        while True:
            char = msvcrt.getwch()
            if char in ("\x00", "\xe0"):
                extended = msvcrt.getwch()
                if extended == "H":
                    return "up"
                if extended == "P":
                    return "down"
                continue
            if char == "\r":
                return "enter"
            if char == "\x03":
                raise KeyboardInterrupt
            continue

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char in ("\r", "\n"):
            return "enter"
        if char == "\x03":
            raise KeyboardInterrupt
        if char == "\x1b":
            next_char = sys.stdin.read(1)
            if next_char == "[":
                final_char = sys.stdin.read(1)
                if final_char == "A":
                    return "up"
                if final_char == "B":
                    return "down"
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def render_arrow_menu(options: list[str], selected_index: int, *, redraw: bool) -> None:
    if redraw:
        sys.stdout.write(f"\x1b[{len(options)}A")
    for index, option in enumerate(options):
        prefix = "> " if index == selected_index else "  "
        sys.stdout.write(f"\r{prefix}{option}\x1b[K\n")
    sys.stdout.flush()


def select_with_arrows(prompt_text: str, options: list[str]) -> int:
    if not sys.stdin.isatty():
        raise RuntimeError(f"Missing required value: {prompt_text}")

    print(f"{prompt_text} (use arrow keys and Enter):")
    selected_index = 0
    render_arrow_menu(options, selected_index, redraw=False)

    while True:
        key = read_menu_key()
        if key == "up":
            selected_index = (selected_index - 1) % len(options)
            render_arrow_menu(options, selected_index, redraw=True)
            continue
        if key == "down":
            selected_index = (selected_index + 1) % len(options)
            render_arrow_menu(options, selected_index, redraw=True)
            continue
        if key == "enter":
            print()
            return selected_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap GitHub prerequisite (app + team + app secrets).")
    parser.add_argument("--org", required=True, help="GitHub organization")
    parser.add_argument("--bootstrap-repo", required=True, help="Repository name that receives app secrets")
    parser.add_argument(
        "--scope",
        choices=["org", "repo"],
        default="org",
        help="Where to write GH_APP_* secrets",
    )
    parser.add_argument(
        "--app-name",
        default="",
        help="GitHub App name override; if omitted, generated as gha-<org20>-<hash6>",
    )
    parser.add_argument(
        "--app-description",
        default="Bootstrap app for template governance",
        help="GitHub App description",
    )
    parser.add_argument("--aws-region", default="", help="AWS region used for SSM SecureString app credential storage")
    parser.add_argument("--aws-profile", default="", help="AWS profile used for SSM SecureString app credential storage")
    parser.add_argument("--homepage-url", default="", help="Optional app homepage URL")
    parser.add_argument("--output-dir", default="app/out", help="Directory for app credentials output")
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        help="Open browser for manifest flow (default)",
    )
    browser_group.add_argument(
        "--no-open-browser",
        dest="open_browser",
        action="store_false",
        help="Do not open browser automatically for manifest flow",
    )
    parser.set_defaults(open_browser=True)
    parser.add_argument("--force-create-app", action="store_true", help="Force creating a new app")

    parser.add_argument("--team-name", default="administrators", help="Administrators team name")
    parser.add_argument(
        "--team-description",
        default="Template bootstrap administrators",
        help="Administrators team description",
    )
    parser.add_argument("--team-maintainers", default="", help="Comma-separated maintainer logins")
    parser.add_argument("--team-members", default="", help="Comma-separated member logins")
    parser.add_argument(
        "--skip-team-repo-admin-grant",
        action="store_true",
        help="Skip granting admin permission on bootstrap repo to administrators team",
    )

    return parser.parse_args()


def get_gh_auth_status_text() -> str:
    print_step("Checking GitHub CLI authentication status...")
    result = run_command(["gh", "auth", "status"])
    if result.returncode != 0:
        message = (
            f"Command failed ({result.returncode}): gh auth status\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
        raise RuntimeError(message)
    return "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()


def extract_gh_scopes(status_text: str) -> set[str]:
    scopes: set[str] = set()
    for line in status_text.splitlines():
        if "Token scopes:" not in line:
            continue
        _, raw_scopes = line.split("Token scopes:", 1)
        for scope in raw_scopes.replace("'", "").replace('"', "").split(","):
            normalized = scope.strip()
            if normalized:
                scopes.add(normalized)
    return scopes


def ensure_gh_scope(required_scope: str) -> None:
    status_text = get_gh_auth_status_text()
    scopes = extract_gh_scopes(status_text)
    if scopes and required_scope in scopes:
        print_step(f"GitHub CLI scope '{required_scope}' is available.")
        return
    if sys.stdin.isatty():
        print_step(f"GitHub CLI is missing scope '{required_scope}'. Starting `gh auth refresh`...")
        run_command_live_checked(
            ["gh", "auth", "refresh", "-h", "github.com", "-s", required_scope],
            description=f"Refreshing GitHub CLI authentication to add scope '{required_scope}'...",
        )
        refreshed_status = get_gh_auth_status_text()
        refreshed_scopes = extract_gh_scopes(refreshed_status)
        if refreshed_scopes and required_scope in refreshed_scopes:
            print_step(f"GitHub CLI scope '{required_scope}' is available after refresh.")
            return
        available_after_refresh = ", ".join(sorted(refreshed_scopes)) if refreshed_scopes else "unknown"
        raise RuntimeError(
            f"GitHub CLI still does not expose required scope '{required_scope}' after refresh. "
            f"Available scopes: {available_after_refresh}."
        )
    if scopes:
        available = ", ".join(sorted(scopes))
        raise RuntimeError(
            f"GitHub CLI is missing required scope '{required_scope}'. Available scopes: {available}. "
            f"Run: gh auth refresh -h github.com -s {required_scope}"
        )
    print_step(
        f"Could not confirm GitHub CLI scopes from `gh auth status`. "
        f"If org administration calls fail, run: gh auth refresh -h github.com -s {required_scope}"
    )


def collect_credentials_bundles(search_dirs: list[Path]) -> list[tuple[float, Path, Path, dict]]:
    candidates_by_app_id: dict[str, tuple[float, Path, Path, dict]] = {}

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for credentials_file in search_dir.glob("github-app-*.credentials.json"):
            try:
                data = json.loads(credentials_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue

            app_id = str(data.get("id", "")).strip()
            if not app_id:
                continue

            private_key_file = search_dir / f"github-app-{app_id}.private-key.pem"
            if not private_key_file.exists():
                continue

            candidate = (credentials_file.stat().st_mtime, credentials_file, private_key_file, data)
            existing = candidates_by_app_id.get(app_id)
            if existing is None or candidate[0] > existing[0]:
                candidates_by_app_id[app_id] = candidate

    candidates = list(candidates_by_app_id.values())
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def snapshot_credentials_state(search_dirs: list[Path]) -> dict[str, float]:
    return {
        str(credentials_file.resolve()): credentials_file.stat().st_mtime
        for _, credentials_file, _, _ in collect_credentials_bundles(search_dirs)
    }


def find_existing_credentials(
    search_dirs: list[Path],
    app_name: str,
    *,
    owner: str = "",
) -> tuple[Path, Path, dict] | None:
    expected_slug = slugify(app_name)
    expected_owner = owner.strip().lower()

    for _, credentials_file, private_key_file, data in collect_credentials_bundles(search_dirs):
        app_slug = str(data.get("slug", "")).strip().lower()
        app_display_name = str(data.get("name", "")).strip()
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()

        if expected_owner and owner_login != expected_owner:
            continue
        if app_display_name != app_name and app_slug != expected_slug:
            continue
        return credentials_file, private_key_file, data

    return None


def find_recent_credentials(
    search_dirs: list[Path],
    *,
    owner: str = "",
    previous_state: dict[str, float] | None = None,
) -> tuple[Path, Path, dict] | None:
    expected_owner = owner.strip().lower()
    previous_state = previous_state or {}

    for modified_at, credentials_file, private_key_file, data in collect_credentials_bundles(search_dirs):
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()
        current_key = str(credentials_file.resolve())
        previous_mtime = previous_state.get(current_key)

        if expected_owner and owner_login != expected_owner:
            continue
        if previous_mtime is not None and modified_at <= previous_mtime:
            continue
        return credentials_file, private_key_file, data

    return None


def list_known_credentials(search_dirs: list[Path], *, owner: str = "") -> list[tuple[Path, Path, dict]]:
    expected_owner = owner.strip().lower()
    bundles: list[tuple[Path, Path, dict]] = []

    for _, credentials_file, private_key_file, data in collect_credentials_bundles(search_dirs):
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()
        if expected_owner and owner_login != expected_owner:
            continue
        bundles.append((credentials_file, private_key_file, data))

    return bundles


def validate_reusable_app_payload(
    payload: dict,
    *,
    owner: str,
    validation_cache: dict[str, dict | None],
) -> tuple[bool, str | None]:
    app_slug = str(payload.get("slug", "")).strip().lower()
    if not app_slug:
        return True, None

    if app_slug not in validation_cache:
        result = run_command(["gh", "api", f"/apps/{app_slug}"])
        if result.returncode != 0:
            error_text = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).lower()
            if "http 404" in error_text or '"status":"404"' in error_text or "not found" in error_text:
                validation_cache[app_slug] = None
            else:
                print_step(
                    f"Could not verify cached GitHub App slug '{app_slug}' against GitHub. "
                    "Keeping it as a reuse candidate."
                )
                validation_cache[app_slug] = {}
        else:
            try:
                validation_cache[app_slug] = json.loads(result.stdout or "{}")
            except json.JSONDecodeError:
                print_step(
                    f"GitHub returned invalid JSON while verifying cached GitHub App slug '{app_slug}'. "
                    "Keeping it as a reuse candidate."
                )
                validation_cache[app_slug] = {}

    response = validation_cache[app_slug]
    if response is None:
        return False, f"GitHub App slug '{app_slug}' no longer exists in GitHub."
    if not response:
        return True, None

    live_app_id = str(response.get("id", "")).strip()
    cached_app_id = str(payload.get("id", "")).strip()
    if live_app_id and cached_app_id and live_app_id != cached_app_id:
        return False, f"Cached app id '{cached_app_id}' does not match live app id '{live_app_id}'."

    expected_owner = owner.strip().lower()
    live_owner = str(response.get("owner", {}).get("login", "")).strip().lower()
    if expected_owner and live_owner and live_owner != expected_owner:
        return False, f"Live owner '{live_owner}' does not match expected owner '{expected_owner}'."

    return True, None


def list_reusable_credentials(
    search_dirs: list[Path],
    *,
    owner: str = "",
) -> tuple[list[tuple[Path, Path, dict]], list[str], list[dict]]:
    validation_cache: dict[str, dict | None] = {}
    reusable_bundles: list[tuple[Path, Path, dict]] = []
    ignored_messages: list[str] = []
    stale_payloads: list[dict] = []

    for bundle in list_known_credentials(search_dirs, owner=owner):
        credentials_file, _, payload = bundle
        is_reusable, reason = validate_reusable_app_payload(
            payload,
            owner=owner,
            validation_cache=validation_cache,
        )
        if is_reusable:
            reusable_bundles.append(bundle)
            continue

        ignored_messages.append(
            f"Ignoring stale GitHub App credentials from '{credentials_file}': "
            f"{format_app_option(payload)}. {reason}"
        )
        stale_payloads.append(payload)

    return reusable_bundles, ignored_messages, stale_payloads


def cleanup_stale_credentials(
    *,
    stale_payloads: list[dict],
    search_dirs: list[Path],
    owner: str,
    aws_region: str,
    aws_profile: str,
) -> None:
    stale_app_ids = sorted({str(payload.get("id", "")).strip() for payload in stale_payloads if str(payload.get("id", "")).strip()})
    if not stale_app_ids:
        return

    print_step(f"Cleaning up stale GitHub App credentials for app ids: {', '.join(stale_app_ids)}.")

    removed_files: list[Path] = []
    for app_id in stale_app_ids:
        for search_dir in search_dirs:
            credentials_file = search_dir / f"github-app-{app_id}.credentials.json"
            private_key_file = search_dir / f"github-app-{app_id}.private-key.pem"
            for candidate in [credentials_file, private_key_file]:
                if not candidate.exists():
                    continue
                try:
                    candidate.unlink()
                    removed_files.append(candidate)
                except OSError as exc:
                    print_step(f"Could not delete stale GitHub App credential file '{candidate}': {exc}")

    if removed_files:
        print_step(f"Removed {len(removed_files)} stale GitHub App credential file(s) from disk.")

    if not ssm_storage_enabled(aws_region=aws_region):
        return

    for app_id in stale_app_ids:
        parameter_name = ssm_parameter_path(owner=owner, app_id=app_id)
        command = aws_command_base(aws_region=aws_region, aws_profile=aws_profile) + [
            "ssm",
            "delete-parameter",
            "--name",
            parameter_name,
        ]
        result = run_command(command)
        if result.returncode == 0:
            print_step(f"Deleted stale AWS SSM GitHub App credential parameter '{parameter_name}'.")
            continue

        error_text = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).lower()
        if "parameternotfound" in error_text:
            continue

        print_step(
            f"Could not delete stale AWS SSM GitHub App credential parameter '{parameter_name}'. "
            "Leaving it as-is."
        )


def find_existing_credentials_in_bundles(
    bundles: list[tuple[Path, Path, dict]],
    app_name: str,
    *,
    owner: str = "",
) -> tuple[Path, Path, dict] | None:
    expected_slug = slugify(app_name)
    expected_owner = owner.strip().lower()

    for credentials_file, private_key_file, data in bundles:
        app_slug = str(data.get("slug", "")).strip().lower()
        app_display_name = str(data.get("name", "")).strip()
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()

        if expected_owner and owner_login != expected_owner:
            continue
        if app_display_name != app_name and app_slug != expected_slug:
            continue
        return credentials_file, private_key_file, data

    return None


def mirror_bundle_to_directory(credentials_file: Path, private_key_file: Path, target_dir: Path) -> tuple[Path, Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_credentials_file = target_dir / credentials_file.name
    target_private_key_file = target_dir / private_key_file.name

    if credentials_file.resolve() != target_credentials_file.resolve():
        shutil.copy2(credentials_file, target_credentials_file)
    if private_key_file.resolve() != target_private_key_file.resolve():
        shutil.copy2(private_key_file, target_private_key_file)

    return target_credentials_file, target_private_key_file


def sync_local_credentials_to_shared_cache(output_dir: Path, *, owner: str) -> None:
    cache_dir = shared_credentials_dir(owner)
    for _, credentials_file, private_key_file, _ in collect_credentials_bundles([output_dir]):
        mirror_bundle_to_directory(credentials_file, private_key_file, cache_dir)


def aws_command_base(*, aws_region: str, aws_profile: str) -> list[str]:
    command = ["aws"]
    if aws_profile.strip():
        command.extend(["--profile", aws_profile.strip()])
    if aws_region.strip():
        command.extend(["--region", aws_region.strip()])
    return command


def sync_ssm_credentials_to_shared_cache(*, owner: str, aws_region: str, aws_profile: str) -> None:
    if not ssm_storage_enabled(aws_region=aws_region):
        return

    path = f"{SSM_APP_CREDENTIALS_ROOT}/{slugify(owner or 'default-org')}"
    command = aws_command_base(aws_region=aws_region, aws_profile=aws_profile) + [
        "ssm",
        "get-parameters-by-path",
        "--path",
        path,
        "--with-decryption",
        "--recursive",
        "--output",
        "json",
    ]

    print_step("Checking AWS SSM for stored GitHub App credentials...")
    result = run_command(command)
    if result.returncode != 0:
        error_text = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).strip().lower()
        if any(pattern in error_text for pattern in ["parameternotfound", "accessdenied", "unrecognizedclient", "expiredtoken"]):
            print_step("Skipping AWS SSM GitHub App credential sync because stored credentials are unavailable.")
            return
        raise RuntimeError(
            "Failed to read GitHub App credentials from AWS SSM.\n"
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )

    try:
        response = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS SSM returned invalid JSON for GitHub App credential sync.") from exc

    parameters = response.get("Parameters", [])
    if not parameters:
        print_step("No GitHub App credentials found in AWS SSM for this organization.")
        return

    cache_dir = shared_credentials_dir(owner)
    for parameter in parameters:
        raw_value = str(parameter.get("Value", "")).strip()
        if not raw_value:
            continue
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            continue
        credentials_files_from_ssm_payload(payload, target_dir=cache_dir)


def store_credentials_in_ssm(*, owner: str, payload: dict, private_key_pem: str, aws_region: str, aws_profile: str) -> None:
    if not ssm_storage_enabled(aws_region=aws_region):
        print_step("Skipping AWS SSM GitHub App credential upload because AWS region is not configured for this step.")
        return

    app_id = str(payload["id"])
    parameter_name = ssm_parameter_path(owner=owner, app_id=app_id)
    parameter_value = json.dumps(
        ssm_payload_from_credentials(owner=owner, payload=payload, private_key_pem=private_key_pem),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    command = aws_command_base(aws_region=aws_region, aws_profile=aws_profile) + [
        "ssm",
        "put-parameter",
        "--name",
        parameter_name,
        "--type",
        "SecureString",
        "--value",
        parameter_value,
        "--overwrite",
    ]

    run_command_checked(command, description=f"Uploading GitHub App credentials to AWS SSM '{parameter_name}'...")


def build_app_install_url(app_slug: str) -> str:
    return f"https://github.com/apps/{app_slug}/installations/new"


def fetch_installations_for_owner(owner: str, *, strict: bool) -> dict[str, dict] | None:
    org = owner.strip()
    if not org:
        return None

    result = run_command(["gh", "api", f"/orgs/{org}/installations"])
    if result.returncode != 0:
        if strict:
            raise RuntimeError(
                f"Could not read GitHub App installations for org '{org}'.\n"
                f"Command failed ({result.returncode}): gh api /orgs/{org}/installations\n"
                f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
            )
        print_step(f"Could not read GitHub App installations for org '{org}'. Continuing without installation status in the menu.")
        return None

    try:
        response = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        if strict:
            raise RuntimeError(f"GitHub returned invalid JSON for org installation lookup '{org}'.")
        print_step(f"GitHub returned invalid JSON for org installation lookup '{org}'. Continuing without installation status in the menu.")
        return None

    installations: dict[str, dict] = {}
    for installation in response.get("installations", []):
        app_id = str(installation.get("app_id", "")).strip()
        if app_id:
            installations[app_id] = installation

    return installations


def fetch_installed_app_ids_for_owner(owner: str) -> set[str] | None:
    installations = fetch_installations_for_owner(owner, strict=False)
    if installations is None:
        return None
    return set(installations.keys())


def fetch_repo_names_for_installation(installation_id: str) -> set[str]:
    ensure_gh_scope("read:user")
    repo_names: set[str] = set()
    page = 1
    per_page = 100

    while True:
        command = [
            "gh",
            "api",
            "--method",
            "GET",
            f"/user/installations/{installation_id}/repositories",
            "--field",
            f"per_page={per_page}",
            "--field",
            f"page={page}",
        ]
        result = run_command(command)
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not read repositories for GitHub App installation '{installation_id}'.\n"
                f"Command failed ({result.returncode}): {' '.join(command)}\n"
                f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
            )

        try:
            response = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"GitHub returned invalid JSON while reading repositories for installation '{installation_id}'."
            ) from exc

        repositories = response.get("repositories", [])
        for repository in repositories:
            full_name = str(repository.get("full_name", "")).strip().lower()
            if full_name:
                repo_names.add(full_name)

        total_count = int(response.get("total_count", 0) or 0)
        if not repositories or len(repo_names) >= total_count or len(repositories) < per_page:
            break
        page += 1

    return repo_names


def get_repo_installation_status_for_app(*, owner: str, repo: str, payload: dict) -> dict[str, str | bool]:
    app_id = str(payload.get("id", "")).strip()
    app_slug = str(payload.get("slug", "")).strip()
    app_name = str(payload.get("name", "")).strip() or app_slug or app_id or "GitHub App"
    repo_full_name = f"{owner}/{repo}".strip().lower()
    install_url = build_app_install_url(app_slug) if app_slug else ""

    installations = fetch_installations_for_owner(owner, strict=True)
    if installations is None:
        raise RuntimeError(f"Could not read GitHub App installations for org '{owner}'.")

    installation = installations.get(app_id)
    if installation is None:
        return {
            "available": False,
            "status": "not installed on org",
            "action_url": install_url,
            "message": (
                f"GitHub App '{app_name}' is not installed on organization '{owner}'. "
                f"Install it for repo '{owner}/{repo}'."
            ),
        }

    repository_selection = str(installation.get("repository_selection", "")).strip().lower()
    installation_url = str(installation.get("html_url", "")).strip() or install_url
    if repository_selection == "all":
        return {
            "available": True,
            "status": "available for repo",
            "action_url": installation_url,
            "message": f"GitHub App '{app_name}' is installed for repo '{owner}/{repo}'.",
        }

    installation_id = str(installation.get("id", "")).strip()
    repo_names = fetch_repo_names_for_installation(installation_id)
    if repo_full_name in repo_names:
        return {
            "available": True,
            "status": "available for repo",
            "action_url": installation_url,
            "message": f"GitHub App '{app_name}' is installed for repo '{owner}/{repo}'.",
        }

    return {
        "available": False,
        "status": "org installed, repo not selected",
        "action_url": installation_url,
        "message": (
            f"GitHub App '{app_name}' is installed on organization '{owner}', "
            f"but repo '{owner}/{repo}' is not included in the installation."
        ),
    }


def ensure_app_available_for_repo(*, owner: str, repo: str, payload: dict, open_browser: bool) -> None:
    status = get_repo_installation_status_for_app(owner=owner, repo=repo, payload=payload)
    if status["available"]:
        print_step(str(status["message"]))
        return

    action_url = str(status.get("action_url", "")).strip()
    if not action_url:
        raise RuntimeError(str(status["message"]))

    print_step(str(status["message"]))
    print("GitHub App installation/configuration URL:")
    print(action_url)
    if open_browser:
        opened = webbrowser.open(action_url, new=1, autoraise=True)
        if not opened:
            print_step("Failed to open browser automatically. Open the installation/configuration URL manually.")

    if not sys.stdin.isatty():
        raise RuntimeError(
            f"GitHub App is not yet available for repo '{owner}/{repo}'. "
            f"Open: {action_url}"
        )

    started_at = datetime.now().astimezone()
    timeout_at = started_at + timedelta(seconds=APP_INSTALL_WAIT_TIMEOUT_SECONDS)
    print(
        f"Waiting for GitHub App access on {owner}/{repo} "
        f"(now: {format_local_time(started_at)}, timeout at: {format_local_time(timeout_at)})..."
    )
    print("Press Ctrl+C to cancel.")

    deadline_monotonic = time.monotonic() + APP_INSTALL_WAIT_TIMEOUT_SECONDS
    while True:
        time.sleep(APP_INSTALL_WAIT_POLL_SECONDS)
        status = get_repo_installation_status_for_app(owner=owner, repo=repo, payload=payload)
        if status["available"]:
            print_step(str(status["message"]))
            return
        if time.monotonic() >= deadline_monotonic:
            raise RuntimeError(
                f"Timed out waiting for GitHub App access on repo '{owner}/{repo}'. "
                f"Finish installation/configuration here: {action_url}"
            )


def format_app_option(payload: dict, *, installed_app_ids: set[str] | None = None) -> str:
    name = str(payload.get("name", "")).strip() or "(unnamed)"
    slug = str(payload.get("slug", "")).strip() or "n/a"
    app_id = str(payload.get("id", "")).strip() or "n/a"
    if installed_app_ids is None:
        installation_status = "installation unknown"
    elif app_id in installed_app_ids:
        installation_status = "installed on org"
    else:
        installation_status = "not installed on org"
    return f"{name} [id {app_id}, slug {slug}, {installation_status}]"


def resolve_app_target(
    *,
    search_dirs: list[Path],
    owner: str,
    requested_app_name: str,
    force_create_app: bool,
    aws_region: str,
    aws_profile: str,
) -> tuple[str, tuple[Path, Path, dict] | None]:
    target_app_name = requested_app_name.strip() or build_default_app_name(owner)
    known_credentials, ignored_messages, stale_payloads = list_reusable_credentials(search_dirs, owner=owner)
    installed_app_ids = fetch_installed_app_ids_for_owner(owner)

    for message in ignored_messages:
        print_step(message)
    cleanup_stale_credentials(
        stale_payloads=stale_payloads,
        search_dirs=search_dirs,
        owner=owner,
        aws_region=aws_region,
        aws_profile=aws_profile,
    )

    if force_create_app:
        app_name = prompt_with_default(target_app_name, "New GitHub App name", default=target_app_name)
        return app_name, None

    if requested_app_name.strip():
        explicit_bundle = find_existing_credentials_in_bundles(known_credentials, target_app_name, owner=owner)
        if explicit_bundle:
            print_step(f"Reusing GitHub App matching requested name: {target_app_name}.")
            return target_app_name, explicit_bundle
        return target_app_name, None

    if not sys.stdin.isatty():
        conventional_bundle = find_existing_credentials_in_bundles(known_credentials, target_app_name, owner=owner)
        if conventional_bundle:
            print_step(f"Reusing GitHub App matching expected name: {target_app_name}.")
            return target_app_name, conventional_bundle
        if len(known_credentials) == 1:
            _, _, payload = known_credentials[0]
            actual_name = str(payload.get("name", "")).strip() or target_app_name
            print_step(f"Reusing the only known GitHub App credentials for this org: {actual_name}.")
            return actual_name, known_credentials[0]
        if len(known_credentials) > 1:
            raise RuntimeError(
                "Multiple local GitHub App credentials exist for this org. "
                "Pass --app-name to select one explicitly."
            )
        return target_app_name, None

    if known_credentials:
        option_labels = [
            format_app_option(payload, installed_app_ids=installed_app_ids)
            for _, _, payload in known_credentials
        ]
        option_labels.append(f"Create new GitHub App [{target_app_name}]")
        selected_index = select_with_arrows("Select GitHub App", option_labels)
        if selected_index < len(known_credentials):
            _, _, payload = known_credentials[selected_index]
            actual_name = str(payload.get("name", "")).strip() or target_app_name
            print_step(f"Selected existing GitHub App: {actual_name}.")
            selected_app_id = str(payload.get("id", "")).strip()
            if installed_app_ids is not None and selected_app_id and selected_app_id not in installed_app_ids:
                print_step(
                    f"Selected GitHub App is not installed on organization '{owner}' yet."
                )
            return actual_name, known_credentials[selected_index]

    app_name = prompt_with_default(target_app_name, "New GitHub App name", default=target_app_name)
    return app_name, None


def run_app_bootstrap(
    script_path: Path,
    org: str,
    app_name: str,
    app_description: str,
    homepage_url: str,
    output_dir: Path,
    open_browser: bool,
) -> None:
    command = [
        sys.executable,
        str(script_path),
        "--org",
        org,
        "--app-name",
        app_name,
        "--description",
        app_description,
        "--output-dir",
        str(output_dir),
    ]
    if homepage_url.strip():
        command.extend(["--homepage-url", homepage_url.strip()])
    if open_browser:
        command.append("--open-browser")
    run_command_live_checked(command, description="Creating GitHub App via manifest flow...")


def split_csv(raw_value: str) -> list[str]:
    parts = [part.strip() for part in raw_value.split(",")]
    return [part for part in parts if part]


def ensure_team(
    team_script_path: Path,
    org: str,
    team_name: str,
    team_description: str,
    maintainers: str,
    members: str,
    admin_repo: str | None,
) -> None:
    command = [
        sys.executable,
        str(team_script_path),
        "--org",
        org,
        "--team-name",
        team_name,
        "--team-description",
        team_description,
    ]
    if maintainers.strip():
        command.extend(["--maintainers", maintainers.strip()])
    if members.strip():
        command.extend(["--members", members.strip()])
    if admin_repo:
        command.extend(["--admin-repos", admin_repo])
    run_command_checked(command, description="Ensuring administrators team baseline...")


def set_secret(name: str, value: str, *, scope: str, org: str, repo: str) -> None:
    command = ["gh", "secret", "set", name, "--body", value]
    if scope == "repo":
        command.extend(["--repo", f"{org}/{repo}"])
    else:
        command.extend(["--org", org, "--visibility", "selected", "--repos", repo])
    run_command_checked_with_retry(command, description=f"Setting GitHub secret '{name}'...")


def upsert_bootstrap_secrets(
    *,
    scope: str,
    org: str,
    repo: str,
    app_id: str,
    private_key_pem: str,
) -> list[str]:
    changes: list[str] = []

    set_secret("GH_APP_ID", app_id, scope=scope, org=org, repo=repo)
    changes.append("secret GH_APP_ID")

    set_secret("GH_APP_PRIVATE_KEY", private_key_pem, scope=scope, org=org, repo=repo)
    changes.append("secret GH_APP_PRIVATE_KEY")

    return changes


def verify_cli_prerequisites() -> None:
    run_command_checked(["gh", "--version"], description="Checking GitHub CLI...")
    ensure_gh_scope("admin:org")


def main() -> int:
    args = parse_args()
    print_step(f"Starting GitHub prerequisite bootstrap for org='{args.org}', repo='{args.bootstrap_repo}'.")
    verify_cli_prerequisites()
    aws_region = resolve_aws_region(args.aws_region)
    aws_profile = args.aws_profile.strip() or os.environ.get("AWS_PROFILE", "").strip()

    base_dir = Path(__file__).resolve().parent
    output_dir = (base_dir / args.output_dir).resolve()
    sync_local_credentials_to_shared_cache(output_dir, owner=args.org)
    sync_ssm_credentials_to_shared_cache(owner=args.org, aws_region=aws_region, aws_profile=aws_profile)
    search_dirs = credential_search_dirs(output_dir, owner=args.org)
    app_script = base_dir / "app" / "bootstrap-gh-app-manifest.py"
    team_script = base_dir / "team" / "bootstrap-gh-team.py"

    app_name, credentials_bundle = resolve_app_target(
        search_dirs=search_dirs,
        owner=args.org,
        requested_app_name=args.app_name,
        force_create_app=args.force_create_app,
        aws_region=aws_region,
        aws_profile=aws_profile,
    )

    if credentials_bundle:
        credentials_file, private_key_file, payload = credentials_bundle
        credentials_file, private_key_file = mirror_bundle_to_directory(credentials_file, private_key_file, output_dir)
        mirror_bundle_to_directory(credentials_file, private_key_file, shared_credentials_dir(args.org))
        print_step("Reusing existing GitHub App credentials from disk.")
        print(f"Reusing existing app credentials: {credentials_file}")
    else:
        previous_state = snapshot_credentials_state(search_dirs)
        run_app_bootstrap(
            script_path=app_script,
            org=args.org,
            app_name=app_name,
            app_description=args.app_description,
            homepage_url=args.homepage_url,
            output_dir=output_dir,
            open_browser=args.open_browser,
        )
        credentials_bundle = find_existing_credentials(
            search_dirs,
            app_name,
            owner=args.org,
        )
        if not credentials_bundle:
            credentials_bundle = find_recent_credentials(
                search_dirs,
                owner=args.org,
                previous_state=previous_state,
            )
            if credentials_bundle:
                _, _, recent_payload = credentials_bundle
                actual_name = str(recent_payload.get("name", "")).strip()
                actual_slug = str(recent_payload.get("slug", "")).strip()
                print_step(
                    "Detected newly created GitHub App credentials with a different name than requested: "
                    f"name='{actual_name}', slug='{actual_slug}'."
                )
        if not credentials_bundle:
            raise RuntimeError(
                "Unable to locate created credentials in output directory. "
                "Check app creation output and rerun with --force-create-app if needed."
            )
        credentials_file, private_key_file, payload = credentials_bundle
        credentials_file, private_key_file = mirror_bundle_to_directory(credentials_file, private_key_file, output_dir)
        mirror_bundle_to_directory(credentials_file, private_key_file, shared_credentials_dir(args.org))

    app_id = str(payload["id"])
    private_key_pem = private_key_file.read_text(encoding="utf-8")
    store_credentials_in_ssm(
        owner=args.org,
        payload=payload,
        private_key_pem=private_key_pem,
        aws_region=aws_region,
        aws_profile=aws_profile,
    )
    ensure_app_available_for_repo(
        owner=args.org,
        repo=args.bootstrap_repo,
        payload=payload,
        open_browser=args.open_browser,
    )

    grant_admin_repo = None if args.skip_team_repo_admin_grant else args.bootstrap_repo
    ensure_team(
        team_script_path=team_script,
        org=args.org,
        team_name=args.team_name,
        team_description=args.team_description,
        maintainers=args.team_maintainers,
        members=args.team_members,
        admin_repo=grant_admin_repo,
    )

    changes = upsert_bootstrap_secrets(
        scope=args.scope,
        org=args.org,
        repo=args.bootstrap_repo,
        app_id=app_id,
        private_key_pem=private_key_pem,
    )

    print("\nbootstrap-gh-prerequisite summary:")
    print(f"- org: {args.org}")
    print(f"- bootstrap_repo: {args.bootstrap_repo}")
    print(f"- scope: {args.scope}")
    print(f"- app_id: {app_id}")
    print(f"- app_credentials: {credentials_file}")
    print(f"- app_private_key: {private_key_file}")
    for change in changes:
        print(f"- upsert {change}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(red(f"[ERROR] {exc}"), file=sys.stderr)
        raise SystemExit(1)
