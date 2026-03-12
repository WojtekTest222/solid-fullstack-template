#!/usr/bin/env python3
"""
Local orchestrator for full prerequisite bootstrap.

Stage order:
1) Run AWS prerequisite bootstrap.
2) Run GitHub prerequisite bootstrap.
"""

from __future__ import annotations

import argparse
import configparser
import os
import re
import subprocess
import sys
from pathlib import Path

COMMON_AWS_REGION_CHOICES = [
    ("eu-central-1", "EU Central (Frankfurt)"),
    ("us-east-1", "US East (N. Virginia)"),
    ("custom", "Custom"),
]
ANSI_RED = "\033[91m"
ANSI_RESET = "\033[0m"


def red(text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"{ANSI_RED}{text}{ANSI_RESET}"


def print_step(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def run_command(command: list[str], *, cwd: Path | None = None, description: str = "") -> None:
    if description:
        print_step(description)
    result = subprocess.run(command, check=False, cwd=cwd)
    if result.returncode != 0:
        message = (
            f"{description}\n" if description else ""
        ) + f"Command failed ({result.returncode}): {' '.join(command)}"
        raise RuntimeError(message)


def run_command_capture(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False, cwd=cwd)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def aws_config_dir() -> Path:
    config_path = os.environ.get("AWS_CONFIG_FILE", "")
    credentials_path = os.environ.get("AWS_SHARED_CREDENTIALS_FILE", "")

    if config_path:
        return Path(config_path).expanduser().resolve().parent
    if credentials_path:
        return Path(credentials_path).expanduser().resolve().parent
    return Path.home() / ".aws"


def normalize_profile_name(section: str, *, from_config: bool) -> str:
    if not from_config:
        return section.strip()
    if section == "default":
        return "default"
    if section.startswith("profile "):
        return section[len("profile ") :].strip()
    return section.strip()


def list_available_aws_profiles() -> list[str]:
    profiles: set[str] = set()
    files = [
        (Path(os.environ.get("AWS_CONFIG_FILE", Path.home() / ".aws" / "config")).expanduser(), True),
        (
            Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE", Path.home() / ".aws" / "credentials")).expanduser(),
            False,
        ),
    ]

    for path, from_config in files:
        if not path.exists():
            continue

        parser = configparser.RawConfigParser()
        parser.read(path, encoding="utf-8")
        for section in parser.sections():
            profile = normalize_profile_name(section, from_config=from_config)
            if profile:
                profiles.add(profile)

    return sorted(profiles, key=str.lower)


def prompt_for_aws_profile(profiles: list[str]) -> str:
    if not sys.stdin.isatty():
        available = ", ".join(profiles) if profiles else "none found"
        raise RuntimeError(
            "Missing AWS profile. Set AWS_PROFILE, pass --aws-profile, or run interactively. "
            f"Available profiles in {aws_config_dir()}: {available}."
        )

    print(f"AWS profile is not set. Available profiles in {aws_config_dir()}:")
    if not profiles:
        print("  No profiles found in config files.")
        while True:
            answer = input("AWS profile: ").strip()
            if answer:
                return answer
            print("Value is required.")

    selected_index = select_with_arrows("Select AWS profile", profiles)
    return profiles[selected_index]


def resolve_aws_profile(profile_arg: str) -> str:
    explicit_profile = profile_arg.strip()
    if explicit_profile:
        return explicit_profile

    env_profile = os.environ.get("AWS_PROFILE", "").strip()
    if env_profile:
        return env_profile

    profiles = list_available_aws_profiles()
    return prompt_for_aws_profile(profiles)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap AWS + GitHub prerequisites in one run.")
    parser.add_argument("--org", default="", help="GitHub owner (organization or user)")
    parser.add_argument("--repo", default="", help="Repository name receiving bootstrap variables and secrets")
    parser.add_argument("--aws-region", default="", help="AWS region for prerequisite resources")
    parser.add_argument("--aws-profile", default="", help="AWS profile to use")

    parser.add_argument(
        "--scope",
        choices=["org", "repo"],
        default="org",
        help="Deprecated. GH_APP_* bootstrap secrets are always written to repository environment 'bootstrap'.",
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


def prompt_if_missing(value: str, prompt_text: str) -> str:
    normalized = value.strip()
    if normalized:
        return normalized

    if not sys.stdin.isatty():
        raise RuntimeError(f"Missing required value: {prompt_text}")

    while True:
        answer = input(f"{prompt_text}: ").strip()
        if answer:
            return answer
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


def prompt_for_aws_region(value: str) -> str:
    normalized = value.strip()
    if normalized:
        return normalized

    option_labels = [f"{label} [{region}]" if region != "custom" else label for region, label in COMMON_AWS_REGION_CHOICES]
    selected_index = select_with_arrows("Select AWS region", option_labels)
    selected_region = COMMON_AWS_REGION_CHOICES[selected_index][0]
    if selected_region != "custom":
        return selected_region
    return prompt_if_missing("", "Custom AWS region")


def parse_github_remote(remote_url: str) -> tuple[str, str] | None:
    remote = remote_url.strip()
    if not remote:
        return None

    scp_match = re.match(r"^[^@]+@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if scp_match:
        return scp_match.group(1), scp_match.group(2)

    https_match = re.match(r"^(?:https|ssh)://[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$", remote)
    if https_match:
        return https_match.group(1), https_match.group(2)

    return None


def discover_github_context_from_git(start_dir: Path) -> tuple[str, str] | None:
    remote_url = run_command_capture(["git", "config", "--get", "remote.origin.url"], cwd=start_dir)
    return parse_github_remote(remote_url)


def main() -> int:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    print_step("Starting full prerequisite bootstrap.")
    git_context = discover_github_context_from_git(base_dir)
    if git_context:
        git_org, git_repo = git_context
        if not args.org.strip():
            args.org = git_org
        if not args.repo.strip():
            args.repo = git_repo
        print_step(f"Detected GitHub remote context from .git: org='{git_org}', repo='{git_repo}'.")

    args.org = prompt_if_missing(args.org, "GitHub owner")
    args.repo = prompt_if_missing(args.repo, "Bootstrap repository")
    args.aws_region = prompt_for_aws_region(args.aws_region)
    args.aws_profile = resolve_aws_profile(args.aws_profile)
    os.environ["AWS_PROFILE"] = args.aws_profile
    print_step(f"Resolved bootstrap context: org='{args.org}', repo='{args.repo}', region='{args.aws_region}'.")

    aws_script = base_dir / "aws" / "bootstrap-aws.py"
    gh_script = base_dir / "gh" / "bootstrap-gh.py"

    aws_command = [
        sys.executable,
        str(aws_script),
        "--org",
        args.org,
        "--repo",
        args.repo,
        "--aws-region",
        args.aws_region,
    ]
    if args.aws_profile.strip():
        aws_command.extend(["--aws-profile", args.aws_profile.strip()])

    gh_command = [
        sys.executable,
        str(gh_script),
        "--org",
        args.org,
        "--bootstrap-repo",
        args.repo,
        "--scope",
        args.scope,
        "--aws-region",
        args.aws_region,
        "--app-description",
        args.app_description,
        "--output-dir",
        args.output_dir,
        "--team-name",
        args.team_name,
        "--team-description",
        args.team_description,
    ]

    if args.app_name.strip():
        gh_command.extend(["--app-name", args.app_name.strip()])
    if args.aws_profile.strip():
        gh_command.extend(["--aws-profile", args.aws_profile.strip()])
    if args.homepage_url.strip():
        gh_command.extend(["--homepage-url", args.homepage_url.strip()])
    if args.open_browser:
        gh_command.append("--open-browser")
    if args.force_create_app:
        gh_command.append("--force-create-app")
    if args.team_maintainers.strip():
        gh_command.extend(["--team-maintainers", args.team_maintainers.strip()])
    if args.team_members.strip():
        gh_command.extend(["--team-members", args.team_members.strip()])
    if args.skip_team_repo_admin_grant:
        gh_command.append("--skip-team-repo-admin-grant")

    print("== AWS prerequisite ==")
    run_command(aws_command, cwd=base_dir, description="Running AWS prerequisite bootstrap...")

    print("\n== GitHub prerequisite ==")
    run_command(gh_command, cwd=base_dir, description="Running GitHub prerequisite bootstrap...")

    print("\nFull prerequisite bootstrap finished.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(red(f"[ERROR] {exc}"), file=sys.stderr)
        raise SystemExit(1)
