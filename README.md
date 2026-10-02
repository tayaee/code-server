# vscode-server

Want to run VS Code for a repository right from your terminal SSH session? Yes, you can do it with `vscode-server` and `remote-code`.

A tool to open remote Linux directories in your local Windows VS Code (no VS Code required on Linux).

## Install

### Windows

```
Windows % uv tool install --from git+https://github.com/tayaee/vscode-server.git --force vscode-server
Windows % vscode-server --version
```

### Linux

Log in via SSH to install / upgrade (same command):

```
Linux $ uv tool install --from git+https://github.com/tayaee/vscode-server.git --force vscode-server
Linux $ remote-code --version
```

## SSH config (Windows side)

VS Code Remote-SSH connects by **<linux-host-alias>**, not by raw IP. Register the alias once in `%USERPROFILE%\.ssh\config`:

```
Host <linux-host-alias>
    HostName <linux-ip>
    User <linux-login-id>
    IdentityFile "<path-to-private-key-file>"
    RemoteForward 8259 127.0.0.1:8259
```

- `Host <linux-host-alias>`: the name you use in VS Code (`vscode-remote://ssh-remote+<linux-host-alias>/...`) and in `remote-code --ssh-host <linux-host-alias>`.
- `HostName` <linux-ip>: real IP / DNS of the Linux box.
- `User <linux-login-id>`: Linux login id. The `vscode-remote://` URI cannot carry a username, so this must match the Linux user.

Note: if your Windows username differs from your Linux username and the `Host` block has no `User`, `vscode-server` inserts `User <Linux ID>` automatically (with a `.bak` backup). For details, see the [OpenBSD ssh_config manual](https://man.openbsd.org/ssh_config) and [VS Code Remote-SSH documentation](https://code.visualstudio.com/docs/remote/ssh).

`remote-code` picks the alias in this order: `--ssh-host` > `$CODE_SSH_HOST` > local hostname. If the Linux hostname is not the alias, pass it explicitly:

```
Linux $ remote-code
or
Linux $ remote-code --ssh-host <linux-host-alias>
```

## Use case 1: Local LAN (port 8259 directly reachable)

Same office / home LAN, where the Linux box can reach `http://<Windows IP>:8259` directly. No reverse tunnel needed.

```
# Windows: listen on LAN
Windows % vscode-server
```

### Pre-flight (all must pass, otherwise `remote-code` fails)

```bash
# 1. Linux -> Windows: is vscode-server reachable?
Linux $ nc -zv -w 3 <Windows-IP> 8259
# expect: Connection to <Windows-IP> 8259 port [tcp/*] succeeded!
# fail -> vscode-server not running / Windows firewall / wrong IP
```

```powershell
# 2. Windows -> Linux: does SSH work without a password?
Windows % ssh <linux-host-alias> "echo ssh-ok"
# expect: ssh-ok (no password prompt)
# fail -> HostName / User / IdentityFile / key registration wrong

# 3. Windows -> Linux: does VS Code Remote-SSH open?
Windows % code --version
# expect: version output (CLI on PATH)
Windows % code --folder-uri "vscode-remote://ssh-remote+<linux-host-alias>/home/user1/src/demo"
# expect: a VS Code window opens on that folder (close it after the test)
# fail -> Host alias / User / Remote-SSH extension wrong
```

```
# Then, from the Linux SSH session:
Linux $ remote-code
or
Linux $ remote-code --ssh-host <linux-host-alias>
```

## Use case 2: Home -> Cloud (port 8259 unreachable, reverse tunnel required)

Cloud VM (OCI / AWS / etc.) cannot dial back to your home Windows PC (NAT / firewall). Open a reverse tunnel from Windows so the cloud box can reach `vscode-server` via localhost. `remote-code` tries `<vscode-server-ip>:8259` first and falls back to `127.0.0.1:8259` when it is listening.

```
# Windows terminal 1: listen on loopback; the tunnel forwards to it
Windows % vscode-server --host 127.0.0.1

# Windows terminal 2: SSH to cloud with a reverse tunnel for port 8259
Windows % ssh -R 8259:localhost:8259 <linux-host-alias>
# (equivalent to having `RemoteForward 8259 127.0.0.1:8259` in the Host block
# and running `ssh <linux-host-alias>`)
```

### Pre-flight (all must pass, otherwise `remote-code` fails)

```bash
# 1. Linux (cloud): is the reverse tunnel bound?
Linux $ ss -tnlp4 | grep 8259
# expect: LISTEN 0 ... 127.0.0.1:8259 ...
# empty -> tunnel not up (check the `ssh -R` session on Windows)
```

```powershell
# 2. Windows -> Linux: auto-login without password? (BatchMode fails instead of prompting)
Windows % ssh -o BatchMode=yes <linux-host-alias> "echo ssh-ok"
# expect: ssh-ok
# fail -> key / IdentityFile / User / HostName wrong

# 3. Windows -> Linux: does VS Code open automatically?
Windows % code --folder-uri "vscode-remote://ssh-remote+<linux-host-alias>/home/user1/src/demo"
# expect: a VS Code window opens on that folder (close it after the test)
# fail -> Host alias / User / Remote-SSH extension wrong
```

```
# Linux (cloud, inside the tunneled SSH session as user1):
Linux $ cd /home/user1/src/demo

Linux $ remote-code
or
Linux $ remote-code --ssh-host <linux-host-alias>
```
