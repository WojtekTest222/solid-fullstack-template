#!/usr/bin/env python3
"""
Ensure a GitHub organization team exists with expected members and repo access.

This script is idempotent:
- creates the team if missing,
- updates team metadata if already present,
- upserts memberships,
- upserts repository permission bindings.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Iterable

ANSI_RED = "\033[91m"
ANSI_RESET = "\033[0m"


def red(text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"{ANSI_RED}{text}{ANSI_RESET}"


def split_csv(raw_value: str) -> list[str]:
    parts = [part.strip() for part in raw_value.split(",")]
    return [part for part in parts if part]


def slugify_team_name(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("Team name resolves to empty slug.")
    return slug


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return result


def run_command_checked(command: list[str]) -> str:
    result = run_command(command)
    if result.returncode != 0:
        message = (
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
        raise RuntimeError(message)
    return result.stdout.strip()


def gh_api_json(
    endpoint: str,
    *,
    method: str = "GET",
    fields: dict[str, str] | None = None,
    allow_not_found: bool = False,
) -> dict:
    command = [
        "gh",
        "api",
        endpoint,
        "-X",
        method,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
    ]
    if fields:
        for key, value in fields.items():
            command.extend(["-f", f"{key}={value}"])

    result = run_command(command)
    if result.returncode != 0:
        stderr = result.stderr or ""
        if allow_not_found and "HTTP 404" in stderr:
            return {}
        message = (
            f"GitHub API call failed: {' '.join(command)}\n"
            f"STDERR:\n{stderr}\nSTDOUT:\n{result.stdout}"
        )
        raise RuntimeError(message)

    output = result.stdout.strip()
    if not output:
        return {}
    return json.loads(output)


def ensure_team(org: str, team_name: str, team_slug: str, description: str, privacy: str) -> str:
    existing = gh_api_json(f"/orgs/{org}/teams/{team_slug}", allow_not_found=True)
    if not existing:
        created = gh_api_json(
            f"/orgs/{org}/teams",
            method="POST",
            fields={
                "name": team_name,
                "description": description,
                "privacy": privacy,
            },
        )
        return f"create team: {created.get('slug', team_slug)}"

    gh_api_json(
        f"/orgs/{org}/teams/{team_slug}",
        method="PATCH",
        fields={
            "name": team_name,
            "description": description,
            "privacy": privacy,
        },
    )
    return f"update team: {team_slug}"


def ensure_team_memberships(org: str, team_slug: str, users: Iterable[str], role: str) -> list[str]:
    actions: list[str] = []
    for login in users:
        gh_api_json(
            f"/orgs/{org}/teams/{team_slug}/memberships/{login}",
            method="PUT",
            fields={"role": role},
        )
        actions.append(f"ensure {role}: {login}")
    return actions


def ensure_team_repo_admin(org: str, team_slug: str, repos: Iterable[str]) -> list[str]:
    actions: list[str] = []
    for repo in repos:
        gh_api_json(
            f"/orgs/{org}/teams/{team_slug}/repos/{org}/{repo}",
            method="PUT",
            fields={"permission": "admin"},
        )
        actions.append(f"ensure repo admin: {org}/{repo}")
    return actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure GitHub team baseline for bootstrap governance.")
    parser.add_argument("--org", required=True, help="GitHub organization")
    parser.add_argument("--team-name", default="administrators", help="Team display name")
    parser.add_argument(
        "--team-description",
        default="Template bootstrap administrators",
        help="Team description",
    )
    parser.add_argument(
        "--team-privacy",
        choices=["closed", "secret"],
        default="closed",
        help="Team privacy mode",
    )
    parser.add_argument(
        "--maintainers",
        default="",
        help="Comma-separated maintainers. Default: current gh auth user.",
    )
    parser.add_argument("--members", default="", help="Comma-separated team members")
    parser.add_argument(
        "--admin-repos",
        default="",
        help="Comma-separated repos that should grant admin permission to this team",
    )
    return parser.parse_args()


def resolve_default_maintainer() -> str:
    return run_command_checked(["gh", "api", "/user", "--jq", ".login"])


def main() -> int:
    args = parse_args()
    org = args.org.strip()
    team_name = args.team_name.strip()
    team_slug = slugify_team_name(team_name)

    maintainers = split_csv(args.maintainers)
    if not maintainers:
        maintainers = [resolve_default_maintainer()]

    members = split_csv(args.members)
    admin_repos = split_csv(args.admin_repos)

    actions: list[str] = []
    actions.append(ensure_team(org, team_name, team_slug, args.team_description, args.team_privacy))
    actions.extend(ensure_team_memberships(org, team_slug, maintainers, "maintainer"))

    member_only = [member for member in members if member not in maintainers]
    actions.extend(ensure_team_memberships(org, team_slug, member_only, "member"))
    actions.extend(ensure_team_repo_admin(org, team_slug, admin_repos))

    print("bootstrap-gh-team summary:")
    for action in actions:
        print(f"- {action}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(red(f"[ERROR] {exc}"), file=sys.stderr)
        raise SystemExit(1)
