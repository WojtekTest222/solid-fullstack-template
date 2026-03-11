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
import subprocess
import sys
from pathlib import Path

DEFAULT_APP_PREFIX = "gha"
MAX_GITHUB_APP_NAME_LENGTH = 34
DEFAULT_ORG_SEGMENT_LENGTH = 20
DEFAULT_APP_SUFFIX_LENGTH = 6
ANSI_RED = "\033[91m"
ANSI_RESET = "\033[0m"


def red(text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"{ANSI_RED}{text}{ANSI_RESET}"


def print_step(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


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


def collect_credentials_bundles(output_dir: Path) -> list[tuple[float, Path, Path, dict]]:
    candidates: list[tuple[float, Path, Path, dict]] = []
    for credentials_file in output_dir.glob("github-app-*.credentials.json"):
        try:
            data = json.loads(credentials_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        app_id = data.get("id")
        if not app_id:
            continue

        private_key_file = output_dir / f"github-app-{app_id}.private-key.pem"
        if not private_key_file.exists():
            continue

        candidates.append((credentials_file.stat().st_mtime, credentials_file, private_key_file, data))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def snapshot_credentials_state(output_dir: Path) -> dict[str, float]:
    return {
        str(credentials_file.resolve()): credentials_file.stat().st_mtime
        for _, credentials_file, _, _ in collect_credentials_bundles(output_dir)
    }


def find_existing_credentials(
    output_dir: Path,
    app_name: str,
    *,
    owner: str = "",
) -> tuple[Path, Path, dict] | None:
    expected_slug = slugify(app_name)
    expected_owner = owner.strip().lower()

    for _, credentials_file, private_key_file, data in collect_credentials_bundles(output_dir):
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
    output_dir: Path,
    *,
    owner: str = "",
    previous_state: dict[str, float] | None = None,
) -> tuple[Path, Path, dict] | None:
    expected_owner = owner.strip().lower()
    previous_state = previous_state or {}

    for modified_at, credentials_file, private_key_file, data in collect_credentials_bundles(output_dir):
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()
        current_key = str(credentials_file.resolve())
        previous_mtime = previous_state.get(current_key)

        if expected_owner and owner_login != expected_owner:
            continue
        if previous_mtime is not None and modified_at <= previous_mtime:
            continue
        return credentials_file, private_key_file, data

    return None


def list_known_credentials(output_dir: Path, *, owner: str = "") -> list[tuple[Path, Path, dict]]:
    expected_owner = owner.strip().lower()
    bundles: list[tuple[Path, Path, dict]] = []

    for _, credentials_file, private_key_file, data in collect_credentials_bundles(output_dir):
        owner_login = str(data.get("owner", {}).get("login", "")).strip().lower()
        if expected_owner and owner_login != expected_owner:
            continue
        bundles.append((credentials_file, private_key_file, data))

    return bundles


def format_app_option(payload: dict) -> str:
    name = str(payload.get("name", "")).strip() or "(unnamed)"
    slug = str(payload.get("slug", "")).strip() or "n/a"
    app_id = str(payload.get("id", "")).strip() or "n/a"
    return f"{name} [id {app_id}, slug {slug}]"


def resolve_app_target(
    *,
    output_dir: Path,
    owner: str,
    requested_app_name: str,
    force_create_app: bool,
) -> tuple[str, tuple[Path, Path, dict] | None]:
    target_app_name = requested_app_name.strip() or build_default_app_name(owner)
    known_credentials = list_known_credentials(output_dir, owner=owner)

    if not force_create_app:
        conventional_bundle = find_existing_credentials(output_dir, target_app_name, owner=owner)
        if conventional_bundle:
            print_step(f"Reusing GitHub App matching expected name: {target_app_name}.")
            return target_app_name, conventional_bundle

    if force_create_app:
        app_name = prompt_with_default(target_app_name, "New GitHub App name", default=target_app_name)
        return app_name, None

    if requested_app_name.strip():
        return target_app_name, None

    if not sys.stdin.isatty():
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
        option_labels = [format_app_option(payload) for _, _, payload in known_credentials]
        option_labels.append(f"Create new GitHub App [{target_app_name}]")
        selected_index = select_with_arrows("Select GitHub App", option_labels)
        if selected_index < len(known_credentials):
            _, _, payload = known_credentials[selected_index]
            actual_name = str(payload.get("name", "")).strip() or target_app_name
            print_step(f"Selected existing GitHub App: {actual_name}.")
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
    run_command_checked(command, description=f"Setting GitHub secret '{name}'...")


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

    base_dir = Path(__file__).resolve().parent
    output_dir = (base_dir / args.output_dir).resolve()
    app_script = base_dir / "app" / "bootstrap-gh-app-manifest.py"
    team_script = base_dir / "team" / "bootstrap-gh-team.py"

    app_name, credentials_bundle = resolve_app_target(
        output_dir=output_dir,
        owner=args.org,
        requested_app_name=args.app_name,
        force_create_app=args.force_create_app,
    )

    if credentials_bundle:
        credentials_file, private_key_file, payload = credentials_bundle
        print_step("Reusing existing GitHub App credentials from disk.")
        print(f"Reusing existing app credentials: {credentials_file}")
    else:
        previous_state = snapshot_credentials_state(output_dir)
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
            output_dir,
            app_name,
            owner=args.org,
        )
        if not credentials_bundle:
            credentials_bundle = find_recent_credentials(
                output_dir,
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

    app_id = str(payload["id"])
    private_key_pem = private_key_file.read_text(encoding="utf-8")

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
