# vscode-server

Want to run VS Code for a repository right from your terminal SSH session? Yes, you can do it with `vscode-server` and `launch-vscode`.

A tool to open remote Linux directories in your local Windows VS Code (no VS Code required on Linux).

## Windows

Install / Upgrade (same command):
```
Windows % uv tool install --from git+https://github.com/tayaee/vscode-server.git --force vscode-server
Windows % vscode-server --version
```

Run:
```
# Server listening on port 8259 to receive triggers from launch-vscode and initiate VS Code Remote SSH sessions
Windows % vscode-server
```

Note: If your Windows username differs from your Linux username, you need to register `User <Linux ID>` under the corresponding `Host` in `%USERPROFILE%\.ssh\config` (if missing, `vscode-server` automatically generates the `Host` / `HostName` / `User` block). For details, see the [OpenBSD ssh_config manual](https://man.openbsd.org/ssh_config) and [VS Code Remote-SSH documentation](https://code.visualstudio.com/docs/remote/ssh).

## Linux

Log in via SSH to install / upgrade (same command):
```
Linux $ uv tool install --from git+https://github.com/tayaee/vscode-server.git --force vscode-server
Linux $ launch-vscode --version
```

Run:
```
Linux $ cd /path/to/git-repo

# Method 1: Automatically connect by extracting the Windows IP from CODE_SERVER_HOST, SSH_CONNECTION, or SSH_CLIENT
Linux $ launch-vscode

# Method 2: Launch VS Code by explicitly specifying the Windows IP where VS Code is installed
Linux $ launch-vscode --server <Windows IP>
```
