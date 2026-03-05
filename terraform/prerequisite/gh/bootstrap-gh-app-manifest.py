#!/usr/bin/env python3
"""
Semi-automated GitHub App bootstrap using manifest flow.

Flow:
1. Builds app manifest.
2. Opens GitHub "new app from manifest" page in browser.
3. Waits on local callback URL for temporary manifest code.
4. Exchanges code for GitHub App credentials.
5. Writes credentials to local files.
"""

from __future__ import annotations

import argparse
import html
import json
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


GITHUB_API_BASE = "https://api.github.com"
GITHUB_WEB_BASE = "https://github.com"
ANSI_GREEN = "\033[92m"
ANSI_RESET = "\033[0m"


def supports_color() -> bool:
    return sys.stdout.isatty()


def green(text: str) -> str:
    if not supports_color():
        return text
    return f"{ANSI_GREEN}{text}{ANSI_RESET}"


class CallbackServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        state: str,
        callback_path: str,
        start_path: str,
        registration_url: str,
        manifest_json: str,
    ) -> None:
        super().__init__(server_address, CallbackHandler)
        self.state = state
        self.callback_path = callback_path
        self.start_path = start_path
        self.registration_url = registration_url
        self.manifest_json = manifest_json
        self.event = threading.Event()
        self.code: str | None = None
        self.error: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    server: CallbackServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == self.server.start_path:
            registration_html = html.escape(self.server.registration_url, quote=True)
            manifest_html = html.escape(self.server.manifest_json, quote=True)
            page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>GitHub App Manifest Bootstrap</title>
</head>
<body>
  <p>Submitting GitHub App manifest...</p>
  <form id="manifest-form" method="post" action="{registration_html}">
    <input type="hidden" name="manifest" value="{manifest_html}" />
  </form>
  <script>
    document.getElementById("manifest-form").submit();
  </script>
</body>
</html>
"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return

        if parsed.path != self.server.callback_path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        query = urllib.parse.parse_qs(parsed.query)
        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]

        if state != self.server.state:
            self.server.error = "State mismatch in callback."
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch.")
            self.server.event.set()
            return

        if not code:
            self.server.error = "Missing manifest code in callback."
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code.")
            self.server.event.set()
            return

        self.server.code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h3>GitHub App bootstrap complete.</h3>"
            b"<p>You can close this tab and return to terminal.</p></body></html>"
        )
        self.server.event.set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap GitHub App via manifest flow.")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--org", help="GitHub organization where the app is created")
    target_group.add_argument("--user", help="Create app under personal account settings")

    parser.add_argument("--app-name", required=True, help="GitHub App name")
    parser.add_argument("--description", default="Template bootstrap governance app", help="App description")
    parser.add_argument("--homepage-url", default="", help="App homepage URL")
    parser.add_argument("--port", type=int, default=8787, help="Local callback port")
    parser.add_argument("--callback-path", default="/callback", help="Local callback path")
    parser.add_argument("--timeout-seconds", type=int, default=600, help="Callback wait timeout")
    parser.add_argument("--output-dir", default=".", help="Directory to write output files")
    parser.add_argument("--open-browser", action="store_true", help="Open browser automatically")
    return parser.parse_args()


def build_manifest(args: argparse.Namespace, redirect_url: str) -> dict[str, Any]:
    homepage = args.homepage_url.strip()
    if not homepage:
        if args.org:
            homepage = f"https://github.com/{args.org}"
        else:
            homepage = f"https://github.com/{args.user}"

    return {
        "name": args.app_name,
        "url": homepage,
        "description": args.description,
        "redirect_url": redirect_url,
        "public": False,
        "default_permissions": {
            "administration": "write",
            "actions": "write",
            "contents": "write",
            "deployments": "write",
            "environments": "write",
            "metadata": "read",
        },
        "default_events": [],
    }


def build_registration_url(args: argparse.Namespace, state: str) -> str:
    query = urllib.parse.urlencode({"state": state})
    if args.org:
        return f"{GITHUB_WEB_BASE}/organizations/{args.org}/settings/apps/new?{query}"
    return f"{GITHUB_WEB_BASE}/settings/apps/new?{query}"


def exchange_manifest_code(code: str) -> dict[str, Any]:
    url = f"{GITHUB_API_BASE}/app-manifests/{urllib.parse.quote(code)}/conversions"
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "bootstrap-gh-app-manifest",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Code exchange failed ({exc.code}): {body}") from exc


def write_output_files(output_dir: Path, response: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key = response.get("pem", "")
    if not private_key:
        raise RuntimeError("GitHub response does not include private key (pem).")

    app_id = response.get("id")
    if app_id is None:
        raise RuntimeError("GitHub response does not include app id.")

    key_file = output_dir / f"github-app-{app_id}.private-key.pem"
    json_file = output_dir / f"github-app-{app_id}.credentials.json"

    key_file.write_text(private_key, encoding="utf-8")
    json_file.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")

    return key_file, json_file


def run() -> int:
    args = parse_args()
    callback_path = args.callback_path if args.callback_path.startswith("/") else f"/{args.callback_path}"
    start_path = "/start"
    redirect_url = f"http://127.0.0.1:{args.port}{callback_path}"
    start_url = f"http://127.0.0.1:{args.port}{start_path}"
    state = secrets.token_urlsafe(24)

    manifest = build_manifest(args, redirect_url)
    registration_url = build_registration_url(args, state)
    manifest_json = json.dumps(manifest, separators=(",", ":"))

    server = CallbackServer(
        ("127.0.0.1", args.port),
        state,
        callback_path,
        start_path,
        registration_url,
        manifest_json,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("GitHub target URL (form POST target):")
    print(green(registration_url))
    print()
    print("Local auto-submit URL:")
    print(green(start_url))
    print()

    if args.open_browser:
        opened = webbrowser.open(start_url, new=1, autoraise=True)
        if not opened:
            print("[WARN] Failed to open browser automatically. Open the URL manually.")
    else:
        print("Open the local auto-submit URL in your browser.")

    print(f"Waiting for callback on {redirect_url} (timeout: {args.timeout_seconds}s)...")
    if not server.event.wait(timeout=args.timeout_seconds):
        server.shutdown()
        raise RuntimeError("Timed out waiting for callback.")

    server.shutdown()
    thread.join(timeout=2)

    if server.error:
        raise RuntimeError(server.error)

    if not server.code:
        raise RuntimeError("Callback did not provide manifest code.")

    response = exchange_manifest_code(server.code)
    output_dir = Path(args.output_dir).resolve()
    key_file, json_file = write_output_files(output_dir, response)

    app_slug = response.get("slug", "")
    app_id = response.get("id", "")
    html_url = response.get("html_url", "")
    install_url = f"{GITHUB_WEB_BASE}/apps/{app_slug}/installations/new" if app_slug else ""

    print()
    print("GitHub App bootstrap completed.")
    print(f"App ID: {app_id}")
    print(f"App Slug: {app_slug}")
    print(f"App URL: {green(html_url)}")
    if install_url:
        print(f"Install URL: {green(install_url)}")
    print(f"Private key saved: {key_file}")
    print(f"Full response saved: {json_file}")
    print()
    print("Next steps:")
    print("1) Install the app on target repositories in GitHub UI.")
    print("2) Add secrets GH_APP_ID and GH_APP_PRIVATE_KEY to organization/repository.")
    return 0


def main() -> int:
    try:
        return run()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
