"""Linux-side trigger: tell your Windows box to open VS Code here.

Run inside an active SSH session on the remote Linux machine:

    launch-code
    launch-code --server 192.168.1.10 --ssh-host myserver
    launch-code --path /home/user/project --token s3cret

The server address defaults (in order) to:
  1. ``--server``
  2. ``$CODE_SERVER_HOST``
  3. client IP from ``$SSH_CLIENT`` / ``$SSH_CONNECTION``
  4. ``127.0.0.1`` (works with ``ssh -R 8259:localhost:8259`` reverse tunnel)

Payload sent: ``POST http://<server>:<port>/launch``
``{"path": "<cwd>", "host": "<ssh-alias>", "hostname": ..., "user": ...}``
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

import click

from . import __version__
from .common import (
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    ENV_PORT,
    ENV_TOKEN,
    build_folder_uri,
    detect_client_ip,
    local_hostname,
    normalize_token,
    resolve_ssh_host,
)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("path", required=False, default=None)
@click.option("--path", "path_opt", default=None,
              help="Same as positional PATH (explicit flag).")
@click.option("--server", "--host", "server", default=None, envvar="CODE_SERVER_HOST",
              help="Windows machine address (default: auto-detect from $SSH_CONNECTION / "
                   "$SSH_CLIENT, else 127.0.0.1 for SSH -R tunnels; env CODE_SERVER_HOST).")
@click.option("--port", type=int, default=DEFAULT_PORT, envvar=ENV_PORT, show_default=True,
              help=f"code-server port (env {ENV_PORT}).")
@click.option("--token", default=None, envvar=ENV_TOKEN,
              help=f"Optional shared secret, only needed when the server was started "
                   f"with one (env {ENV_TOKEN}). Omit to send no token.")
@click.option("--ssh-host", default=None,
              help="Remote-SSH Host alias as configured on Windows "
                   "(default: $CODE_SSH_HOST or local hostname).")
@click.option("--timeout", type=float, default=DEFAULT_TIMEOUT, show_default=True,
              help="HTTP timeout in seconds.")
@click.option("--dry-run", is_flag=True,
              help="Print the request without sending it.")
@click.option("--verbose", is_flag=True, help="Verbose output.")
@click.version_option(__version__, "-v", "--version", message="%(version)s")
def cli(path, path_opt, server, port, token, ssh_host, timeout, dry_run, verbose) -> int:
    """Trigger the Windows code-server listener to open VS Code here."""
    return _run(path, path_opt, server, port, token, ssh_host, timeout, dry_run, verbose)


def resolve_target_dir(path_arg: str | None, path_opt: str | None) -> str:
    raw = path_opt or path_arg or os.getcwd()
    # Keep it absolute; do not require existence (dir may be transient).
    p = Path(raw)
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    return os.path.normpath(str(p))


def main(argv: list[str] | None = None) -> int:
    """Entry point (keeps ``main(argv) -> int`` for tests/embedders)."""
    try:
        rc = cli.main(args=list(argv) if argv is not None else None,
                      prog_name="launch-code", standalone_mode=False)
        return rc if isinstance(rc, int) else 0
    except click.exceptions.Exit as e:
        return e.exit_code
    except (click.ClickException, click.Abort) as e:
        e.show()
        return getattr(e, "exit_code", 1)


def _run(path, path_opt, server, port, token, ssh_host, timeout, dry_run, verbose) -> int:
    target_dir = resolve_target_dir(path, path_opt)

    server = (server or "").strip()
    auto_ip = detect_client_ip()
    if not server:
        if auto_ip:
            server = auto_ip
            if verbose:
                print(f"[launch-code] auto-detected Windows host {server} from SSH env", file=sys.stderr)
        else:
            server = "127.0.0.1"
            print("[launch-code] warning: not in an SSH session and --server not given; "
                   "trying 127.0.0.1 (works with `ssh -R 8259:localhost:8259`).",
                  file=sys.stderr)

    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = ""
    hostname = local_hostname()
    ssh_host = resolve_ssh_host(ssh_host, hostname)
    if not ssh_host:
        print("[launch-code] error: cannot determine SSH host alias. "
              "Pass --ssh-host <Remote-SSH Host> or set $CODE_SSH_HOST.", file=sys.stderr)
        return 2

    try:
        preview_uri = build_folder_uri(ssh_host, target_dir)
    except ValueError as e:
        print(f"[launch-code] error: {e}", file=sys.stderr)
        return 2

    url = f"http://{server}:{port}/launch"
    payload = {"path": target_dir, "host": ssh_host, "hostname": hostname, "user": user}

    if verbose or dry_run:
        print(f"[launch-code] POST {url}", file=sys.stderr)
        print(f"[launch-code] payload: {json.dumps(payload)}", file=sys.stderr)
        print(f"[launch-code] will open: {preview_uri}", file=sys.stderr)
    if dry_run:
        return 0

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    token = normalize_token(token)
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            detail = ""
        print(f"[launch-code] server rejected request: HTTP {e.code} {detail}", file=sys.stderr)
        if e.code == 401:
            print("[launch-code] hint: token mismatch. Match --token with the server's --token.",
                  file=sys.stderr)
        elif e.code == 400:
            print("[launch-code] hint: try --ssh-host <Remote-SSH Host alias from Windows ssh config>.",
                  file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        print(f"[launch-code] cannot reach code-server at {url}: {reason}", file=sys.stderr)
        print("[launch-code] hints:", file=sys.stderr)
        print("  1. Is `code-server` running on Windows? (code-server --host 0.0.0.0)", file=sys.stderr)
        print("  2. Windows firewall allowing inbound TCP on the port?", file=sys.stderr)
        print(f"     PowerShell (admin): New-NetFirewallRule -DisplayName code-server "
              f"-Direction Inbound -LocalPort {port} -Protocol TCP -Action Allow", file=sys.stderr)
        print("  3. No direct LAN route? Use a reverse tunnel from Windows:", file=sys.stderr)
        print(f"     ssh -R {port}:localhost:{port} user@remote", file=sys.stderr)
        print("     then: launch-code --server 127.0.0.1", file=sys.stderr)
        if not auto_ip:
            print("  4. $SSH_CLIENT/$SSH_CONNECTION empty: you may be in tmux/screen; "
                  "pass --server explicitly.", file=sys.stderr)
        return 1
    except (socket.timeout, TimeoutError, OSError) as e:
        print(f"[launch-code] connection failed: {e}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {"raw": raw}
    uri = data.get("uri", preview_uri) if isinstance(data, dict) else preview_uri
    if status == 200:
        print(f"Triggered VS Code -> {uri}")
        if isinstance(data, dict):
            if data.get("ssh_config") == "added":
                print(f"[launch-code] ssh config updated: log in as '{data.get('ssh_user')}'.",
                      file=sys.stderr)
            elif data.get("warning"):
                print(f"[launch-code] warning: {data['warning']}", file=sys.stderr)
        return 0
    print(f"[launch-code] unexpected status HTTP {status}: {raw}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
