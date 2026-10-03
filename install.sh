#!/usr/bin/env bash
# Re-install `vslc` (and `vsls`) when needed.
# (`remote-code` is an alias of `vslc`; both are installed together.)
#
# Rules:
#   - uv missing  -> install uv (via mise if present, else curl)
#   - vslc miss   -> force install (uv tool install --force)
#   - vslc >= 7 days old -> force install
#   - --force given     -> force install immediately
#
# Usage:
#   ./install.sh [--force|-f] [--help|-h]
#
# Idempotent: exits 0 whether it installed or skipped.

set -euo pipefail

FORCE=0
STALE_DAYS=7
REPO="git+https://github.com/tayaee/vscode-launcher.git"
PKG="vscode-launcher"

log() { echo "[install.sh] $*" >&2; }

usage() {
    echo "Usage: ./install.sh [--force|-f] [--help|-h]"
}

for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=1 ;;
        --help|-h) usage; exit 0 ;;
        *) log "unknown argument: $arg"; usage >&2; exit 2 ;;
    esac
done

add_to_path() {
    case ":$PATH:" in
        *":$1:"*) ;;
        *) PATH="$1:$PATH" ;;
    esac
}

ensure_local_path() {
    add_to_path "$HOME/.local/share/mise/shims"
    add_to_path "$HOME/.local/bin"
    add_to_path "$HOME/.cargo/bin"
}

ensure_uv() {
    ensure_local_path
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    if command -v mise >/dev/null 2>&1; then
        log "uv not found; installing via mise..."
        echo "+ mise use -g uv"
        mise use -g uv
        ensure_local_path
    else
        log "uv not found; installing via curl..."
        if ! command -v curl >/dev/null 2>&1; then
            log "error: curl not found; install curl or mise first."
            exit 1
        fi
        echo "+ curl -LsSf https://astral.sh/uv/install.sh | sh"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        ensure_local_path
    fi
    if ! command -v uv >/dev/null 2>&1; then
        log "error: uv install finished but 'uv' is still not on PATH."
        log "hint: open a new shell (or export PATH=\"\$HOME/.local/bin:\$PATH\")."
        exit 1
    fi
    log "uv ready: $(uv --version)"
}

# 0 = needs install, 1 = fresh (skip).
vslc_needs_install() {
    if [ "$FORCE" -eq 1 ]; then
        return 0
    fi
    local bin
    bin="$(command -v vslc 2>/dev/null || true)"
    if [ -z "${bin:-}" ] || [ ! -e "$bin" ]; then
        log "vslc not found; will install."
        return 0
    fi
    local mtime now age limit
    if mtime="$(stat -c %Y "$bin" 2>/dev/null)" || mtime="$(stat -f %m "$bin" 2>/dev/null)"; then
        now="$(date +%s)"
        age=$((now - mtime))
        limit=$((STALE_DAYS * 86400))
        if [ "$age" -ge "$limit" ]; then
            log "vslc is $((age / 86400)) days old (>= ${STALE_DAYS}d); will reinstall."
            return 0
        fi
        log "vslc is fresh ($((age / 3600))h old); skipping (use --force to reinstall)."
        return 1
    fi
    log "cannot stat vslc; will reinstall to be safe."
    return 0
}

do_install() {
    log "installing ${PKG} (uv tool install --force)..."
    echo + uv tool install --from "$REPO" --force "$PKG"
    uv tool install --from "$REPO" --force "$PKG"
    ensure_local_path
    hash -r 2>/dev/null || true
    if command -v vslc >/dev/null 2>&1; then
        log "done: $(vslc --version 2>&1 || echo 'vslc installed')"
    else
        log "warning: install finished but 'vslc' is not on PATH."
        log "hint: export PATH=\"\$HOME/.local/bin:\$PATH\" (or reopen the shell)."
    fi
    if command -v remote-code >/dev/null 2>&1; then
        log "alias ok: $(remote-code --version 2>&1 || echo 'remote-code installed')"
    else
        log "warning: alias 'remote-code' is not on PATH."
    fi
}

main() {
    ensure_uv
    if vslc_needs_install; then
        do_install
    fi
}

main
(set -x; vslc --version)
(set -x; remote-code --version)
