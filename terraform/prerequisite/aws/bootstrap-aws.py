#!/usr/bin/env python3
"""
Local orchestrator for AWS prerequisite bootstrap.

Stage order:
1) Apply prerequisite Terraform with minimal inputs.
2) Read the generated state bucket name from Terraform output.
3) Upsert required GitHub variables via gh CLI using repository-scoped org variables.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote

DEFAULT_BOOTSTRAP_ROLE_NAME = "gha-bootstrap-org"
DEFAULT_LOCK_TABLE_NAME = "terraform-locks"
GH_WRITE_MAX_ATTEMPTS = 4
GH_AUTH_REFRESH_MAX_ATTEMPTS = 3
GH_AUTH_REFRESH_RETRY_DELAY_SECONDS = 3
ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_RESET = "\033[0m"


def green(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{ANSI_GREEN}{text}{ANSI_RESET}"


def red(text: str) -> str:
    if not sys.stderr.isatty():
        return text
    return f"{ANSI_RED}{text}{ANSI_RESET}"


def print_step(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def run_command(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False, cwd=cwd)


def run_command_live_checked(command: list[str], *, cwd: Path | None = None, description: str = "") -> None:
    if description:
        print_step(description)
    result = subprocess.run(command, check=False, cwd=cwd)
    if result.returncode != 0:
        message = (
            f"{description}\n" if description else ""
        ) + f"Command failed ({result.returncode}): {' '.join(command)}"
        raise RuntimeError(message)


def run_command_checked(command: list[str], *, cwd: Path | None = None, description: str = "") -> str:
    if description:
        print_step(description)
    result = run_command(command, cwd=cwd)
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
    cwd: Path | None = None,
    description: str = "",
    max_attempts: int = GH_WRITE_MAX_ATTEMPTS,
) -> str:
    if description:
        print_step(description)

    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, max_attempts + 1):
        result = run_command(command, cwd=cwd)
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


def build_tf_state_bucket_name(*, aws_account_id: str, aws_region: str) -> str:
    return f"tfstate-{aws_account_id}-{aws_region}"


def build_github_main_subject(*, org: str, repo: str) -> str:
    return f"repo:{org}/{repo}:ref:refs/heads/main"


def normalize_github_subject_pattern(pattern: str) -> str:
    normalized = pattern.strip()
    legacy_repo_match = re.fullmatch(r"repo:([^/]+)/([^:]+):\*", normalized)
    if not legacy_repo_match:
        return normalized
    return build_github_main_subject(org=legacy_repo_match.group(1), repo=legacy_repo_match.group(2))


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_aws_cli_error(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).strip()


def is_missing_resource_error(result: subprocess.CompletedProcess[str], *, patterns: list[str]) -> bool:
    error_text = normalize_aws_cli_error(result).lower()
    return any(pattern in error_text for pattern in patterns)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap AWS prerequisite Terraform and publish required GitHub variables."
    )
    parser.add_argument("--org", required=True, help="GitHub organization")
    parser.add_argument("--repo", required=True, help="Repository name that receives bootstrap variables")
    parser.add_argument("--aws-region", required=True, help="AWS region for prerequisite resources")
    parser.add_argument("--aws-profile", default="", help="AWS profile to use")
    return parser.parse_args()


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
        refreshed_scopes: set[str] = set()
        for attempt in range(1, GH_AUTH_REFRESH_MAX_ATTEMPTS + 1):
            result = subprocess.run(
                ["gh", "auth", "refresh", "-h", "github.com", "-s", required_scope],
                check=False,
            )
            refreshed_status = get_gh_auth_status_text()
            refreshed_scopes = extract_gh_scopes(refreshed_status)
            if refreshed_scopes and required_scope in refreshed_scopes:
                print_step(f"GitHub CLI scope '{required_scope}' is available after refresh.")
                return
            if result.returncode == 0:
                break
            if attempt < GH_AUTH_REFRESH_MAX_ATTEMPTS:
                print_step(
                    f"`gh auth refresh` did not complete successfully. "
                    f"Retrying in {GH_AUTH_REFRESH_RETRY_DELAY_SECONDS}s "
                    f"({attempt}/{GH_AUTH_REFRESH_MAX_ATTEMPTS - 1} retries used)..."
                )
                time.sleep(GH_AUTH_REFRESH_RETRY_DELAY_SECONDS)
                continue

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
        f"If org variable updates fail, run: gh auth refresh -h github.com -s {required_scope}"
    )


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


def verify_cli_prerequisites(*, aws_profile: str) -> None:
    os.environ["AWS_PROFILE"] = aws_profile
    print_step(f"Using AWS profile '{aws_profile}'.")
    run_command_checked(["terraform", "version"], description="Checking Terraform CLI...")
    run_command_checked(["aws", "--version"], description="Checking AWS CLI...")
    try:
        run_command_checked(
            ["aws", "sts", "get-caller-identity"],
            description="Validating AWS credentials with STS GetCallerIdentity...",
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"AWS authentication failed for profile '{aws_profile}'. "
            f"Refresh credentials first (for SSO usually: aws sso login --profile {aws_profile}).\n{exc}"
        ) from exc
    run_command_checked(["gh", "--version"], description="Checking GitHub CLI...")
    ensure_gh_scope("admin:org")


def check_s3_bucket_exists(*, bucket_name: str, aws_region: str) -> bool:
    result = run_command(
        [
            "aws",
            "s3api",
            "get-bucket-location",
            "--bucket",
            bucket_name,
            "--query",
            "LocationConstraint",
            "--output",
            "text",
        ]
    )
    if result.returncode != 0:
        if is_missing_resource_error(result, patterns=["nosuchbucket", "not found", "404"]):
            return False
        raise RuntimeError(
            f"Failed to verify S3 bucket '{bucket_name}'.\n{normalize_aws_cli_error(result)}"
        )

    raw_location = result.stdout.strip()
    actual_region = "us-east-1" if raw_location in {"", "None", "null"} else raw_location
    if actual_region != aws_region:
        raise RuntimeError(
            f"S3 bucket '{bucket_name}' already exists but is in region '{actual_region}', expected '{aws_region}'."
        )
    return True


def check_dynamodb_table_exists(*, table_name: str, aws_region: str) -> bool:
    result = run_command(
        [
            "aws",
            "dynamodb",
            "describe-table",
            "--table-name",
            table_name,
            "--region",
            aws_region,
            "--query",
            "Table.TableArn",
            "--output",
            "text",
        ]
    )
    if result.returncode != 0:
        if is_missing_resource_error(result, patterns=["resourcenotfoundexception", "not found"]):
            return False
        raise RuntimeError(
            f"Failed to verify DynamoDB table '{table_name}'.\n{normalize_aws_cli_error(result)}"
        )
    return True


def check_iam_role_exists(*, role_name: str) -> bool:
    result = run_command(
        [
            "aws",
            "iam",
            "get-role",
            "--role-name",
            role_name,
            "--query",
            "Role.Arn",
            "--output",
            "text",
        ]
    )
    if result.returncode != 0:
        if is_missing_resource_error(result, patterns=["nosuchentity", "cannot find"]):
            return False
        raise RuntimeError(
            f"Failed to verify IAM role '{role_name}'.\n{normalize_aws_cli_error(result)}"
        )
    return True


def load_assume_role_policy_document(*, role_name: str) -> dict[str, object]:
    output_raw = run_command_checked(
        [
            "aws",
            "iam",
            "get-role",
            "--role-name",
            role_name,
            "--query",
            "Role.AssumeRolePolicyDocument",
            "--output",
            "json",
        ],
        description=f"Reading IAM trust policy for role '{role_name}'...",
    )

    parsed_output = json.loads(output_raw)
    if isinstance(parsed_output, dict):
        return parsed_output
    if not isinstance(parsed_output, str):
        raise RuntimeError(f"Unsupported IAM trust policy payload type for role '{role_name}'.")

    decoded_policy = unquote(parsed_output)
    try:
        policy_document = json.loads(decoded_policy)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse IAM trust policy for role '{role_name}'.") from exc

    if not isinstance(policy_document, dict):
        raise RuntimeError(f"Unexpected IAM trust policy shape for role '{role_name}'.")
    return policy_document


def list_policy_statements(policy_document: dict[str, object]) -> list[dict[str, object]]:
    raw_statements = policy_document.get("Statement", [])
    if isinstance(raw_statements, dict):
        return [raw_statements]
    if isinstance(raw_statements, list):
        return [statement for statement in raw_statements if isinstance(statement, dict)]
    raise RuntimeError("IAM trust policy does not contain a valid Statement list.")


def is_github_oidc_statement(statement: dict[str, object]) -> bool:
    raw_action = statement.get("Action", [])
    if isinstance(raw_action, str):
        actions = [raw_action]
    elif isinstance(raw_action, list):
        actions = [str(action).strip() for action in raw_action]
    else:
        return False

    if "sts:AssumeRoleWithWebIdentity" not in actions:
        return False

    principal = statement.get("Principal", {})
    if not isinstance(principal, dict):
        return True

    federated = principal.get("Federated", [])
    if isinstance(federated, str):
        federated_values = [federated]
    elif isinstance(federated, list):
        federated_values = [str(value).strip() for value in federated]
    else:
        federated_values = []

    return not federated_values or any(
        "token.actions.githubusercontent.com" in value for value in federated_values
    )


def extract_subject_patterns_from_statement(statement: dict[str, object]) -> list[str]:
    condition = statement.get("Condition", {})
    if not isinstance(condition, dict):
        return []

    patterns: list[str] = []
    for operator_value in condition.values():
        if not isinstance(operator_value, dict):
            continue
        raw_patterns = operator_value.get("token.actions.githubusercontent.com:sub")
        if isinstance(raw_patterns, str):
            patterns.append(raw_patterns)
            continue
        if isinstance(raw_patterns, list):
            patterns.extend(str(value) for value in raw_patterns)
    return dedupe_preserve_order(patterns)


def update_subject_patterns_in_policy(
    policy_document: dict[str, object],
    *,
    subject_patterns: list[str],
) -> dict[str, object]:
    updated = False

    for statement in list_policy_statements(policy_document):
        if not is_github_oidc_statement(statement):
            continue

        condition = statement.get("Condition")
        if condition is None:
            condition = {}
            statement["Condition"] = condition
        if not isinstance(condition, dict):
            raise RuntimeError("IAM trust policy contains an invalid Condition block.")

        for operator_name, operator_values in list(condition.items()):
            if not isinstance(operator_values, dict):
                continue
            if operator_name == "StringLike":
                continue
            operator_values.pop("token.actions.githubusercontent.com:sub", None)

        string_like = condition.get("StringLike")
        if string_like is None:
            string_like = {}
            condition["StringLike"] = string_like
        if not isinstance(string_like, dict):
            raise RuntimeError("IAM trust policy contains an invalid StringLike block.")

        string_like["token.actions.githubusercontent.com:sub"] = subject_patterns
        updated = True

    if not updated:
        raise RuntimeError(
            f"IAM role '{DEFAULT_BOOTSTRAP_ROLE_NAME}' does not contain a GitHub OIDC web identity statement."
        )

    return policy_document


def ensure_bootstrap_role_trust_policy(*, org: str, repo: str) -> bool:
    policy_document = load_assume_role_policy_document(role_name=DEFAULT_BOOTSTRAP_ROLE_NAME)
    current_subject_patterns: list[str] = []

    for statement in list_policy_statements(policy_document):
        if not is_github_oidc_statement(statement):
            continue
        current_subject_patterns.extend(extract_subject_patterns_from_statement(statement))

    current_subject_patterns = dedupe_preserve_order(current_subject_patterns)
    desired_subject_patterns = dedupe_preserve_order(
        [normalize_github_subject_pattern(pattern) for pattern in current_subject_patterns]
        + [build_github_main_subject(org=org, repo=repo)]
    )

    if (
        len(current_subject_patterns) == len(desired_subject_patterns)
        and set(current_subject_patterns) == set(desired_subject_patterns)
    ):
        print_step(
            f"IAM role '{DEFAULT_BOOTSTRAP_ROLE_NAME}' already allows the required GitHub repos from branch 'main'."
        )
        return False

    updated_policy = update_subject_patterns_in_policy(
        policy_document,
        subject_patterns=desired_subject_patterns,
    )
    policy_document_json = json.dumps(updated_policy, separators=(",", ":"))
    run_command_checked(
        [
            "aws",
            "iam",
            "update-assume-role-policy",
            "--role-name",
            DEFAULT_BOOTSTRAP_ROLE_NAME,
            "--policy-document",
            policy_document_json,
        ],
        description=(
            f"Updating IAM trust policy for role '{DEFAULT_BOOTSTRAP_ROLE_NAME}' "
            f"to allow repo '{org}/{repo}' from branch 'main'..."
        ),
    )
    return True


def inspect_existing_aws_prerequisites(*, aws_account_id: str, aws_region: str) -> tuple[str, dict[str, bool]]:
    tf_state_bucket = build_tf_state_bucket_name(aws_account_id=aws_account_id, aws_region=aws_region)
    print_step("Checking whether AWS prerequisite resources already exist on this account...")
    resource_state = {
        f"S3 bucket '{tf_state_bucket}'": check_s3_bucket_exists(bucket_name=tf_state_bucket, aws_region=aws_region),
        f"DynamoDB table '{DEFAULT_LOCK_TABLE_NAME}'": check_dynamodb_table_exists(
            table_name=DEFAULT_LOCK_TABLE_NAME,
            aws_region=aws_region,
        ),
        f"IAM role '{DEFAULT_BOOTSTRAP_ROLE_NAME}'": check_iam_role_exists(role_name=DEFAULT_BOOTSTRAP_ROLE_NAME),
    }
    return tf_state_bucket, resource_state


def write_runtime_tfvars(*, org: str, repo: str, aws_region: str) -> str:
    print_step("Preparing temporary Terraform variables for AWS prerequisite...")
    content = "\n".join(
        [
            f'aws_region = "{aws_region}"',
            f'github_org = "{org}"',
            f'github_repo = "{repo}"',
            "",
        ]
    )

    with tempfile.NamedTemporaryFile("w", suffix=".auto.tfvars", encoding="utf-8", delete=False) as handle:
        handle.write(content)
        return handle.name


def run_terraform(terraform_dir: Path, *, tfvars_path: str) -> dict[str, object]:
    run_command_checked(
        ["terraform", "init"],
        cwd=terraform_dir,
        description="Initializing Terraform for AWS prerequisite...",
    )
    run_command_checked(
        ["terraform", "apply", "-auto-approve", f"-var-file={tfvars_path}"],
        cwd=terraform_dir,
        description="Applying Terraform for AWS prerequisite...",
    )
    output_raw = run_command_checked(
        ["terraform", "output", "-json"],
        cwd=terraform_dir,
        description="Reading Terraform outputs for AWS prerequisite...",
    )
    return json.loads(output_raw)


def get_aws_account_id() -> str:
    return run_command_checked(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        description="Reading AWS account ID...",
    ).strip()


def set_variable(name: str, value: str, *, org: str, repo: str) -> None:
    command = [
        "gh",
        "variable",
        "set",
        name,
        "--body",
        value,
        "--org",
        org,
        "--visibility",
        "selected",
        "--repos",
        repo,
    ]
    run_command_checked_with_retry(
        command,
        description=f"Setting GitHub org variable '{name}' for repo '{org}/{repo}'...",
    )


def upsert_github_variables(*, org: str, repo: str, aws_region: str, aws_account_id: str, tf_state_bucket: str) -> list[str]:
    changes: list[str] = []
    variables = {
        "AWS_REGION": aws_region,
        "AWS_ACCOUNT_ID": aws_account_id,
        "BOOTSTRAP_ROLE_NAME": DEFAULT_BOOTSTRAP_ROLE_NAME,
        "TF_STATE_BUCKET": tf_state_bucket,
    }

    for name, value in variables.items():
        set_variable(name, value, org=org, repo=repo)
        changes.append(f"variable {name}")

    return changes


def main() -> int:
    args = parse_args()
    print_step(
        f"Starting AWS prerequisite bootstrap for org='{args.org}', repo='{args.repo}', region='{args.aws_region}'."
    )
    aws_profile = resolve_aws_profile(args.aws_profile)
    verify_cli_prerequisites(aws_profile=aws_profile)
    aws_account_id = get_aws_account_id()
    tf_state_bucket, resource_state = inspect_existing_aws_prerequisites(
        aws_account_id=aws_account_id,
        aws_region=args.aws_region,
    )

    existing_resources = [name for name, exists in resource_state.items() if exists]
    missing_resources = [name for name, exists in resource_state.items() if not exists]
    bootstrap_mode = ""
    bootstrap_changes: list[str] = []

    base_dir = Path(__file__).resolve().parent
    if len(existing_resources) == len(resource_state):
        bootstrap_mode = "reused-existing"
        print(green("[OK] All required AWS prerequisite resources already exist. Skipping Terraform apply."))
        for resource_name in existing_resources:
            print(green(f"  - {resource_name}"))
        if ensure_bootstrap_role_trust_policy(org=args.org, repo=args.repo):
            bootstrap_changes.append(f"IAM trust policy for role {DEFAULT_BOOTSTRAP_ROLE_NAME}")
    elif len(existing_resources) == 0:
        bootstrap_mode = "created"
        tfvars_path = write_runtime_tfvars(org=args.org, repo=args.repo, aws_region=args.aws_region)
        try:
            outputs = run_terraform(base_dir, tfvars_path=tfvars_path)
        finally:
            Path(tfvars_path).unlink(missing_ok=True)

        tf_state_bucket_output = str(outputs["tf_state_bucket"]["value"]).strip()
        if not tf_state_bucket_output:
            raise RuntimeError("Missing tf_state_bucket output after Terraform apply.")
        if tf_state_bucket_output != tf_state_bucket:
            raise RuntimeError(
                f"Terraform output tf_state_bucket='{tf_state_bucket_output}' does not match expected '{tf_state_bucket}'."
            )
    else:
        existing_text = ", ".join(existing_resources)
        missing_text = ", ".join(missing_resources)
        raise RuntimeError(
            "AWS prerequisite resources are only partially present on this account. "
            "The script can continue only when all three already exist or none of them exist.\n"
            f"Existing: {existing_text}\n"
            f"Missing: {missing_text}"
        )

    variable_changes = upsert_github_variables(
        org=args.org,
        repo=args.repo,
        aws_region=args.aws_region,
        aws_account_id=aws_account_id,
        tf_state_bucket=tf_state_bucket,
    )

    print("\nbootstrap-aws-prerequisite summary:")
    print(f"- org: {args.org}")
    print(f"- repo: {args.repo}")
    print(f"- aws_region: {args.aws_region}")
    print(f"- aws_profile: {aws_profile}")
    print(f"- bootstrap_mode: {bootstrap_mode}")
    print(f"- aws_account_id: {aws_account_id}")
    print(f"- bootstrap_role_name: {DEFAULT_BOOTSTRAP_ROLE_NAME}")
    print(f"- tf_state_bucket: {tf_state_bucket}")
    print(f"- tf_lock_table: {DEFAULT_LOCK_TABLE_NAME}")
    for change in bootstrap_changes + variable_changes:
        print(f"- upsert {change}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(red(f"[ERROR] {exc}"), file=sys.stderr)
        raise SystemExit(1)
