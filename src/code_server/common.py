"""Shared constants and helpers for code-server (listener) and launch-code (trigger)."""

from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path

DEFAULT_PORT = 8765
DEFAULT_HOST = "0.0.0.0"
DEFAULT_TIMEOUT = 10

ENV_PORT = "CODE_SERVER_PORT"
ENV_HOST = "CODE_SERVER_HOST"  # client: Windows machine address; server: bind address override
ENV_TOKEN = "CODE_SERVER_TOKEN"
ENV_SSH_HOST = "CODE_SSH_HOST"  # Remote-SSH Host alias as known on the Windows side
ENV_SSH_HOST_ALT = "CODE_SERVER_SSH_HOST"
ENV_CODE_BIN = "CODE_SERVER_BINARY"

LAUNCH_PATHS = ("/launch", "/open", "/")


def normalize_token(value: str | None) -> str | None:
    """Normalize an auth token: empty/whitespace-only means 'no token'.

    Returns the stripped token, or None when auth is disabled (accept-all).
    Token auth is purely optional: if the server has no token it accepts
    every request; if it has one the client must present it.
    """
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_folder_uri(ssh_host: str, remote_path: str) -> str:
    """Build a ``vscode-remote://ssh-remote+<host><path>`` folder URI.

    Example:
        >>> build_folder_uri("myserver", "/home/user/proj")
        'vscode-remote://ssh-remote+myserver/home/user/proj'
    """
    ssh_host = ssh_host.strip()
    if not ssh_host:
        raise ValueError("ssh_host must not be empty")
    p = remote_path.strip().replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    # Collapse duplicate slashes (but keep leading single slash).
    while "//" in p:
        p = p.replace("//", "/")
    return f"vscode-remote://ssh-remote+{ssh_host}{p}"


def resolve_ssh_host(explicit: str | None, fallback_hostname: str | None = None) -> str | None:
    """Resolve which SSH host alias to use, or None if unknown."""
    if explicit and explicit.strip():
        return explicit.strip()
    for env in (ENV_SSH_HOST, ENV_SSH_HOST_ALT):
        v = os.environ.get(env, "").strip()
        if v:
            return v
    if fallback_hostname and fallback_hostname.strip():
        return fallback_hostname.strip()
    return None


def detect_client_ip() -> str | None:
    """Best-effort detection of the Windows/SSH-client IP from SSH env vars.

    Returns the IP of the machine you SSH'd *from* (i.e. your Windows box),
    or None when not in an SSH session.

    ``SSH_CONNECTION`` (``client_ip client_port server_ip server_port``) is
    preferred: it is the current OpenSSH standard variable. ``SSH_CLIENT``
    (``client_ip client_port server_port``) is its legacy predecessor and is
    only used as a fallback.
    """
    # SSH_CONNECTION="client_ip client_port server_ip server_port" (preferred)
    ssh_conn = os.environ.get("SSH_CONNECTION", "").strip()
    if ssh_conn:
        parts = ssh_conn.split()
        if parts and _looks_like_ip(parts[0]):
            return parts[0]
    # SSH_CLIENT="client_ip client_port server_port" (legacy fallback)
    ssh_client = os.environ.get("SSH_CLIENT", "").strip()
    if ssh_client:
        parts = ssh_client.split()
        if parts and _looks_like_ip(parts[0]):
            return parts[0]
    return None


def _looks_like_ip(s: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def find_code_binary(explicit: str | None = None) -> str:
    """Locate the VS Code CLI (``code``). Raises FileNotFoundError if missing."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env_bin = os.environ.get(ENV_CODE_BIN, "").strip()
    if env_bin:
        candidates.append(env_bin)
    candidates += ["code", "code.cmd", "code.exe"]

    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
        if Path(c).exists():
            return c

    # Well-known Windows install locations.
    if os.name == "nt":
        extra = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Microsoft VS Code" / "bin" / "code.cmd",
            Path(os.environ.get("LocalAppData", "")) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Microsoft VS Code" / "bin" / "code.cmd",
        ]
        for p in extra:
            try:
                if p.exists():
                    return str(p)
            except OSError:
                continue

    raise FileNotFoundError(
        "VS Code CLI ('code') not found. Install VS Code and tick "
        "'Add to PATH', or pass --code-binary / set CODE_SERVER_BINARY."
    )


def local_hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"
