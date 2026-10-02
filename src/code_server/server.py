"""Windows-side daemon: listens for HTTP triggers and opens local VS Code.

Run on your Windows machine:

    code-server --port 8765 --token s3cret

Then from the remote Linux box (inside SSH):

    launch-code --server <windows-ip>

Protocol (JSON over HTTP):
    POST /launch  {"path": "/home/user/proj", "host": "myserver", ...}
    -> launches ``code --folder-uri vscode-remote://ssh-remote+myserver/home/user/proj``

Auth: if the server was started with a token, the client must send
``Authorization: Bearer <token>`` or ``X-Code-Server-Token: <token>``.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import secrets
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .common import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENV_CODE_BIN,
    ENV_HOST,
    ENV_PORT,
    ENV_TOKEN,
    LAUNCH_PATHS,
    build_folder_uri,
    find_code_binary,
    normalize_token,
)

log = logging.getLogger("code-server")

MAX_BODY_BYTES = 64 * 1024


class ServerConfig:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        token: str | None = None,
        code_binary: str | None = None,
        default_host: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.code_binary = code_binary
        self.default_host = default_host
        self.dry_run = dry_run


def _check_auth(handler: BaseHTTPRequestHandler, token: str | None) -> bool:
    # Token auth is optional: no server token -> accept everything.
    token = normalize_token(token)
    if token is None:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        presented = auth[len("Bearer "):].strip()
        if secrets.compare_digest(presented, token):
            return True
    presented = handler.headers.get("X-Code-Server-Token", "").strip()
    if presented and secrets.compare_digest(presented, token):
        return True
    return False


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(config: ServerConfig):
    class LaunchHandler(BaseHTTPRequestHandler):
        server_version = "code-server/0.1.0"

        def log_message(self, fmt, *args):  # noqa: N802 - stdlib signature
            log.info("%s - %s", self.address_string(), fmt % args)

        def _route(self) -> str:
            return urlparse(self.path).path.rstrip("/") or "/"

        def do_GET(self):  # noqa: N802
            route = self._route()
            if route == "/health":
                _send_json(self, 200, {"status": "ok", "service": "code-server"})
            elif route in ("/", "/launch", "/open"):
                _send_json(
                    self,
                    200,
                    {
                        "service": "code-server",
                        "usage": "POST /launch with JSON {path, host}",
                        "example": {
                            "path": "/home/user/project",
                            "host": "myserver (Remote-SSH Host alias)",
                        },
                    },
                )
            else:
                _send_json(self, 404, {"error": f"unknown path: {route}"})

        def do_POST(self):  # noqa: N802
            route = self._route()
            if route not in LAUNCH_PATHS:
                _send_json(self, 404, {"error": f"unknown path: {route}"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > MAX_BODY_BYTES:
                _send_json(self, 413, {"error": "request body too large"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                _send_json(self, 400, {"error": "invalid JSON body"})
                return
            if not isinstance(data, dict):
                _send_json(self, 400, {"error": "JSON body must be an object"})
                return

            if not _check_auth(self, config.token):
                _send_json(self, 401, {"error": "unauthorized: bad or missing token"})
                return

            remote_path = str(data.get("path") or data.get("cwd") or "").strip()
            ssh_host = str(
                data.get("host") or data.get("ssh_host") or data.get("hostname") or ""
            ).strip() or (config.default_host or "")
            if not remote_path:
                _send_json(self, 400, {"error": "missing required field: 'path'"})
                return
            if not ssh_host:
                _send_json(
                    self,
                    400,
                    {"error": "missing SSH host alias: send {'host': '<Remote-SSH Host>'} "
                              "or start server with --default-host"},
                )
                return
            try:
                uri = build_folder_uri(ssh_host, remote_path)
            except ValueError as e:
                _send_json(self, 400, {"error": str(e)})
                return

            log.info("Launch request from %s: host=%s path=%s", self.client_address[0], ssh_host, remote_path)

            if config.dry_run:
                _send_json(self, 200, {"status": "dry-run", "uri": uri})
                return

            try:
                code_bin = config.code_binary or find_code_binary()
            except FileNotFoundError as e:
                _send_json(self, 500, {"error": str(e)})
                return

            try:
                # Detached so the HTTP response returns immediately and the
                # VS Code process outlives the handler thread.
                kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
                if os.name == "nt":
                    kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)  # type: ignore[attr-defined]
                else:
                    kwargs["start_new_session"] = True
                subprocess.Popen([code_bin, "--folder-uri", uri], **kwargs)  # noqa: S603
            except Exception as e:  # noqa: BLE001
                log.exception("Failed to launch VS Code")
                _send_json(self, 500, {"error": f"failed to launch VS Code: {e}"})
                return

            _send_json(self, 200, {"status": "launched", "uri": uri})

    return LaunchHandler


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="code-server",
        description="Listen for HTTP triggers and open local VS Code on the remote directory "
                    "(via Remote-SSH folder URI). Run this on Windows.",
    )
    p.add_argument("--host", default=os.environ.get(ENV_HOST, DEFAULT_HOST),
                   help=f"Bind address (default: {DEFAULT_HOST}; env {ENV_HOST})")
    p.add_argument("--port", type=int, default=int(os.environ.get(ENV_PORT, DEFAULT_PORT)),
                   help=f"Listen port (default: {DEFAULT_PORT}; env {ENV_PORT})")
    p.add_argument("--token", default=os.environ.get(ENV_TOKEN),
                   help=f"Optional shared secret (env {ENV_TOKEN}). "
                        "If set, client must present it; if omitted, all requests are accepted.")
    p.add_argument("--generate-token", action="store_true",
                   help="Print a random token and exit (use it for --token).")
    p.add_argument("--code-binary", default=os.environ.get(ENV_CODE_BIN),
                   help=f"Path to VS Code CLI (default: auto-detect; env {ENV_CODE_BIN})")
    p.add_argument("--default-host", default=None,
                   help="Default Remote-SSH Host alias when the trigger omits 'host'.")
    p.add_argument("--dry-run", action="store_true",
                   help="Accept requests but only log the URI instead of launching VS Code.")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.generate_token:
        print(secrets.token_urlsafe(32))
        return 0

    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "?"

    config = ServerConfig(
        host=args.host,
        port=args.port,
        token=normalize_token(args.token),
        code_binary=args.code_binary,
        default_host=args.default_host,
        dry_run=args.dry_run,
    )

    try:
        handler = make_handler(config)
        httpd = ThreadingHTTPServer((config.host, config.port), handler)
    except OSError as e:
        log.error("Cannot bind %s:%d: %s", config.host, config.port, e)
        return 1

    bind = f"{config.host}:{httpd.server_port}"
    log.info("code-server listening on %s (user=%s, dry_run=%s)", bind, user, config.dry_run)
    if config.token:
        log.info("Token auth enabled.")
    else:
        log.warning("No --token set: anyone on the network can open VS Code on this machine. "
                    "Use --generate-token + --token for LAN use.")
    if config.host in ("127.0.0.1", "localhost"):
        log.warning("Bound to loopback only; remote Linux hosts cannot reach it. "
                    "Use --host 0.0.0.0 (and a Windows firewall rule) or an SSH -R tunnel.")
    log.info("Health: GET http://%s/health | Trigger: POST http://%s/launch", bind, bind)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
