import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from code_server.client import build_parser as client_parser
from code_server.client import main as client_main
from code_server.common import (
    build_folder_uri,
    detect_client_ip,
    ensure_ssh_user,
    normalize_token,
)
from code_server.server import make_handler, ServerConfig


def _post(port, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/launch",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())


def test_build_folder_uri():
    assert build_folder_uri("myserver", "/home/u/proj") == \
        "vscode-remote://ssh-remote+myserver/home/u/proj"
    assert build_folder_uri("h", "a/b") == "vscode-remote://ssh-remote+h/a/b"


def test_client_parser_defaults():
    args = client_parser().parse_args([])
    assert args.port == 8765
    assert args.server is None or isinstance(args.server, str)


def test_normalize_token_optional():
    assert normalize_token(None) is None
    assert normalize_token("") is None
    assert normalize_token("   ") is None
    assert normalize_token("  s3cret  ") == "s3cret"


def test_server_no_token_accepts_all():
    # Token omitted -> accept everything (no token, or any spurious token).
    config = ServerConfig(host="127.0.0.1", port=0, token=None, dry_run=True)
    httpd = ThreadingHTTPServer((config.host, config.port), make_handler(config))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        status, data = _post(port, {"path": "/tmp", "host": "h"})
        assert status == 200
        assert data["uri"] == "vscode-remote://ssh-remote+h/tmp"
        # Spurious token is also accepted when server has none.
        status, _ = _post(port, {"path": "/tmp", "host": "h"}, token="whatever")
        assert status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_empty_string_token_is_no_token():
    config = ServerConfig(host="127.0.0.1", port=0, token="  ", dry_run=True)
    httpd = ThreadingHTTPServer((config.host, config.port), make_handler(config))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        status, _ = _post(port, {"path": "/tmp", "host": "h"})
        assert status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_launch_dry_run():
    config = ServerConfig(host="127.0.0.1", port=0, token="s3cret", dry_run=True)
    httpd = ThreadingHTTPServer((config.host, config.port), make_handler(config))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # No token -> 401
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/launch",
            data=json.dumps({"path": "/tmp", "host": "h"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected 401")
        except urllib.error.HTTPError as e:
            assert e.code == 401

        # With token -> 200 dry-run
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/launch",
            data=json.dumps({"path": "/tmp", "host": "h"}).encode(),
            headers={"Content-Type": "application/json",
                      "Authorization": "Bearer s3cret"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        assert data["status"] == "dry-run"
        assert data["uri"] == "vscode-remote://ssh-remote+h/tmp"

        # Health
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            assert json.loads(r.read())["status"] == "ok"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_detect_client_ip_no_env(monkeypatch):
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    assert detect_client_ip() is None


def test_detect_client_ip_ssh_client(monkeypatch):
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setenv("SSH_CLIENT", "192.168.1.5 52341 22")
    assert detect_client_ip() == "192.168.1.5"


def test_detect_client_ip_prefers_ssh_connection(monkeypatch):
    # SSH_CONNECTION wins when both are present but disagree.
    monkeypatch.setenv("SSH_CONNECTION", "10.0.0.9 52341 10.0.0.1 22")
    monkeypatch.setenv("SSH_CLIENT", "192.168.1.5 52341 22")
    assert detect_client_ip() == "10.0.0.9"


def test_detect_client_ip_ssh_connection_only(monkeypatch):
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.setenv("SSH_CONNECTION", "10.0.0.9 52341 10.0.0.1 22")
    assert detect_client_ip() == "10.0.0.9"


def test_detect_client_ip_ipv6(monkeypatch):
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.setenv("SSH_CONNECTION", "fd00::1 52341 fd00::2 22")
    assert detect_client_ip() == "fd00::1"


def test_code_server_host_env_is_used(monkeypatch, capsys):
    # Nested SSH scenario: explicit origin propagated via SendEnv/AcceptEnv.
    monkeypatch.setenv("CODE_SERVER_HOST", "10.9.9.9")
    monkeypatch.setenv("CODE_SSH_HOST", "h")
    assert client_main(["--dry-run"]) == 0
    assert "http://10.9.9.9:8765/launch" in capsys.readouterr().err


def test_explicit_server_beats_env(monkeypatch, capsys):
    monkeypatch.setenv("CODE_SERVER_HOST", "10.9.9.9")
    monkeypatch.setenv("CODE_SSH_HOST", "h")
    assert client_main(["--dry-run", "--server", "192.168.0.1"]) == 0
    err = capsys.readouterr().err
    assert "http://192.168.0.1:8765/launch" in err
    assert "10.9.9.9" not in err


def test_ensure_ssh_user_adds_directive(tmp_path):
    cfg = tmp_path / "config"
    cfg.write_text("Host myserver\n    HostName 10.0.0.1\n", encoding="utf-8")
    status, _ = ensure_ssh_user("myserver", "linuxid", cfg)
    assert status == "added"
    text = cfg.read_text(encoding="utf-8")
    assert "User linuxid" in text
    assert "HostName 10.0.0.1" in text  # rest untouched
    assert (tmp_path / "config.bak").exists()  # backup kept


def test_ensure_ssh_user_leaves_existing(tmp_path):
    cfg = tmp_path / "config"
    original = "Host myserver\n    HostName 10.0.0.1\n    User other\n"
    cfg.write_text(original, encoding="utf-8")
    status, _ = ensure_ssh_user("myserver", "linuxid", cfg)
    assert status == "ok"
    assert cfg.read_text(encoding="utf-8") == original


def test_ensure_ssh_user_missing_block(tmp_path):
    cfg = tmp_path / "config"
    cfg.write_text("Host other\n    HostName 10.0.0.2\n", encoding="utf-8")
    status, msg = ensure_ssh_user("myserver", "linuxid", cfg)
    assert status == "missing"
    assert "linuxid" in msg


def test_ensure_ssh_user_missing_file(tmp_path):
    status, _ = ensure_ssh_user("myserver", "linuxid", tmp_path / "nope")
    assert status == "missing"


def test_server_reports_ssh_user_handling(monkeypatch, tmp_path):
    # Linux id differs -> server inserts User into Windows ssh config.
    cfg = tmp_path / "config"
    cfg.write_text("Host h\n    HostName 10.0.0.1\n", encoding="utf-8")
    monkeypatch.setenv("CODE_SSH_CONFIG", str(cfg))
    config = ServerConfig(host="127.0.0.1", port=0, token=None, dry_run=True)
    httpd = ThreadingHTTPServer((config.host, config.port), make_handler(config))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        status, data = _post(port, {"path": "/tmp", "host": "h", "user": "linuxid"})
        assert status == 200
        assert data["ssh_user"] == "linuxid"
        assert data["ssh_config"] == "added"
        assert "User linuxid" in cfg.read_text(encoding="utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
