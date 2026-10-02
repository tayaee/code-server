"""Shared constants and helpers for vscode-server (listener) and launch-vscode (trigger)."""

from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path

DEFAULT_PORT = 8259
DEFAULT_HOST = "0.0.0.0"
DEFAULT_TIMEOUT = 10

ENV_PORT = "CODE_SERVER_PORT"
ENV_HOST = "CODE_SERVER_HOST"  # client: Windows machine address; server: bind address override
ENV_TOKEN = "CODE_SERVER_TOKEN"
ENV_SSH_HOST = "CODE_SSH_HOST"  # Remote-SSH Host alias as known on the Windows side
ENV_SSH_HOST_ALT = "CODE_SERVER_SSH_HOST"
ENV_CODE_BIN = "CODE_SERVER_BINARY"
ENV_SSH_CONFIG = "CODE_SSH_CONFIG"  # override path to ssh config (default: ~/.ssh/config)

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


def ssh_config_path() -> Path:
    """Path to the ssh client config (override via $CODE_SSH_CONFIG)."""
    override = os.environ.get(ENV_SSH_CONFIG, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".ssh" / "config"


def _is_plain_hostname(s: str) -> bool:
    """True if *s* looks like a directly connectable hostname (no patterns).

    e.g. ``spark1.local`` or ``192.168.1.10`` qualify; bare nicknames
    (``myserver``) and anything with wildcards do not.
    """
    if not s or any(c in s for c in (" ", "*", "?", "!", "/", "\\", "@", ":")):
        return False
    return "." in s or _looks_like_ip(s)


def _split_directive(line: str) -> tuple[str, str] | None:
    """Split an ssh-config line into (keyword, args); None for blank/comment."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "=" in s:
        key, _, rest = s.partition("=")
        return key.strip(), rest.strip()
    parts = s.split(None, 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1].strip()


def ensure_ssh_user(host_alias: str, login_user: str,
                    config_path: Path | None = None) -> tuple[str, str]:
    """Ensure ssh config logs into *host_alias* as *login_user*.

    A ``vscode-remote://`` folder URI cannot carry a username, so the Linux
    login id must come from the Windows ssh config's ``User`` directive.
    This inserts ``User <login_user>`` into the first matching ``Host`` block
    (with a ``.bak`` backup) when no ``User`` (and no global ``Host *`` user)
    already covers the alias.

    Returns (status, message); status is one of:
      "ok"      - a User directive already covers the alias (untouched)
      "added"   - User directive was inserted (or a minimal Host block created)
      "missing" - no Host block for the alias and it is not itself a
                  connectable hostname; user must create one manually
      "error"   - config could not be read/written (see message)
    Only top-level ``Host`` blocks are examined (``Match``/``Include``d
    files are out of scope).

    When the alias is itself a hostname (e.g. ``spark1.local`` — the same
    name a working ``ssh user@host`` uses), a minimal block reproducing
    exactly that command is appended automatically, so no manual
    registration is needed.
    """
    host_alias = host_alias.strip()
    login_user = login_user.strip()
    if not host_alias or not login_user:
        return "error", "empty host alias or login user"
    path = config_path or ssh_config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "missing", f"ssh config not found: {path}"
    except OSError as e:
        return "error", f"cannot read ssh config {path}: {e}"

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    # Locate blocks: list of (host_line_index, [patterns]).
    blocks: list[tuple[int, list[str]]] = []
    for i, raw in enumerate(lines):
        d = _split_directive(raw.split("#", 1)[0] if "#" in raw else raw)
        # NOTE: strip inline comments naively; '#' never appears in Host patterns.
        if d and d[0].lower() == "host":
            blocks.append((i, d[1].split()))

    def block_user(start: int) -> str | None:
        end = next((b[0] for b in blocks if b[0] > start), len(lines))
        for raw in lines[start + 1:end]:
            d = _split_directive(raw)
            if d and d[0].lower() == "user":
                return d[1].split()[0] if d[1].split() else ""
        return None

    alias_lc = host_alias.lower()
    exact = [b for b in blocks if any(p.lower() == alias_lc for p in b[1])]
    star_user = next((u for b in blocks if b[1] == ["*"] for u in [block_user(b[0])] if u), None)

    for b in exact:
        if block_user(b[0]):
            return "ok", f"Host {host_alias} already sets User"
    if star_user:
        return "ok", "global 'Host *' already sets User"

    if not exact:
        if _is_plain_hostname(host_alias):
            # The alias is itself a connectable hostname (the same name a
            # working `ssh user@host` uses). Append a minimal block that
            # reproduces exactly that command -- no manual registration needed.
            if not text.endswith(("\n", "\r")):
                text += newline
            block = (f"{newline}Host {host_alias}{newline}"
                     f"    HostName {host_alias}{newline}"
                     f"    User {login_user}{newline}")
            try:
                shutil.copy2(path, path.with_name(path.name + ".bak"))
                path.write_text(text + block, encoding="utf-8")
            except OSError as e:
                return "error", f"cannot update ssh config {path}: {e}"
            return "added", (f"Created 'Host {host_alias}' in {path} "
                             f"(HostName {host_alias}, User {login_user})")
        return ("missing",
                f"No 'Host {host_alias}' block in {path}; add one with "
                f"'HostName <real-host>' and 'User {login_user}' so VS Code "
                "logs in as the Linux id.")

    # Insert into the first matching block, mirroring its indent style.
    idx = exact[0][0]
    end = next((b[0] for b in blocks if b[0] > idx), len(lines))
    indent = "    "
    for raw in lines[idx + 1:end]:
        stripped = raw.lstrip()
        if stripped and not stripped.startswith("#") and raw[:len(raw) - len(stripped)]:
            indent = raw[:len(raw) - len(stripped)]
            break
    lines.insert(idx + 1, f"{indent}User {login_user}{newline}")
    try:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
        path.write_text("".join(lines), encoding="utf-8")
    except OSError as e:
        return "error", f"cannot update ssh config {path}: {e}"
    return "added", f"Set 'User {login_user}' for Host {host_alias} in {path}"
