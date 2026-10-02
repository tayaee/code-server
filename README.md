# code-server

Windows VS Code로 원격 Linux 디렉토리를 여는 도구 (Linux에 VS Code 불필요).

## Windows
설치
```
uv tool install --from git+https://github.com/tayaee/code-server.git code-server
code-server --help
```
실행
```
code-server
```

## Linux
ssh 로그인
```
uv tool install --from git+https://github.com/tayaee/code-server.git code-server
launch-code --help
```

실행
```
cd /path/to/git-repo
launch-code   # 환경변수 CODE_SERVER_HOST 또는 SSH_CONNECTION 또는 SSH_CLIENT에서 Windows IP를 추출하여 자동 접속
launch-code --server <Windows IP>
```
