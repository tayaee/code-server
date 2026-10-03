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

VS Code Remote-SSH connects by **<linux-hostname>**, not by raw IP. Register the alias once in `%USERPROFILE%\.ssh\config`:

```
Host <linux-hostname>
    HostName <linux-ip>
    User <linux-login-id>
    IdentityFile "<path-to-private-key-file>"
    RemoteForward 8259 127.0.0.1:8259
```

See the [OpenBSD ssh_config manual](https://man.openbsd.org/ssh_config) and [VS Code Remote-SSH documentation](https://code.visualstudio.com/docs/remote/ssh) for syntax.

## Use case 1: Local LAN (port 8259 directly reachable)

Same office / home LAN, where the Linux box can reach `http://<Windows IP>:8259` directly. No reverse tunnel needed.

### Happy case

```
# Windows:
Windows % vscode-server

# Then, from the Linux SSH session:
Linux $ remote-code
```

Not working? See [1], [2], [3], [5] below.

## Use case 2: Home -> Cloud (port 8259 unreachable, reverse tunnel required)

Cloud VM (OCI / AWS / etc.) cannot dial back to your home Windows PC (NAT / firewall). Open a reverse tunnel from Windows so the cloud box can reach `vscode-server` via localhost.

### Happy case

```
# Windows:
Windows % vscode-server

# Windows (another terminal, requires RemoteForward in ssh config above):
Windows % ssh <linux-hostname>

# Linux (cloud, inside the tunneled SSH session):
Linux $ remote-code
```

Not working? See [2], [3], [4], [5] below.
`remote-code` tries `<vscode-server-ip>:8259` first and falls back to `127.0.0.1:8259` when it is listening.

## Troubleshooting

### [1] Linux -> Windows: is vscode-server reachable?

```bash
Linux $ nc -zv -w 3 <Windows-IP> 8259
# expect: Connection to <Windows-IP> 8259 port [tcp/*] succeeded!
# fail -> vscode-server not running / Windows firewall / wrong IP
```

### [2] Windows -> Linux: does SSH work without a password?

```powershell
Windows % ssh <linux-hostname> "echo ssh-ok"
# expect: ssh-ok (no password prompt)
# fail -> HostName / User / IdentityFile / key registration wrong
```

For scripting / BatchMode check (fails instead of prompting):

```powershell
Windows % ssh -o BatchMode=yes <linux-hostname> "echo ssh-ok"
```

### [3] Windows -> Linux: does VS Code Remote-SSH open?

```powershell
Windows % code --folder-uri "vscode-remote://ssh-remote+<linux-hostname>/home/user1/src/demo"
# expect: a VS Code window opens on that folder (close it after the test)
# fail -> Host alias / User / Remote-SSH extension wrong
```

### [4] Linux (cloud): is the reverse tunnel bound?

```bash
Linux $ ss -tnlp4 | grep 8259
# expect: LISTEN 0 ... 127.0.0.1:8259 ...
# empty -> tunnel not up (check the `ssh` session on Windows for RemoteForward)
```

### [5] SSH host alias mismatch?

`remote-code` picks the alias in this order: `--ssh-host` > `$CODE_SSH_HOST` > local hostname. If the Linux hostname is not the alias, pass it explicitly:

```
Linux $ remote-code --ssh-host <linux-hostname>
```
