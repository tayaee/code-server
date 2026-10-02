# code-server

Windows VS Code로 원격 Linux 디렉토리를 여는 도구 (Linux에 VS Code 불필요).

## Windows
설치
```
Windows% uv tool install --from git+https://github.com/tayaee/code-server.git code-server
Windows% code-server --help
```

업그레이드 (선택)
```
Windows% uv tool upgrade code-server
```

실행
```
Windows% code-server
```

## Linux
ssh 로그인 하여 설치
```
Linux $ uv tool install --from git+https://github.com/tayaee/code-server.git code-server
Linux $ launch-code --help
```

업그레이드 (선택)
```
Linux $ uv tool upgrade code-server
```

실행
```
Linux $ cd /path/to/git-repo
# 환경변수 CODE_SERVER_HOST 또는 SSH_CONNECTION 또는 SSH_CLIENT에서 Windows IP를 추출하여 자동 접속
Linux $ launch-code   
# VS Code가 설치된 Windows IP를 바로지정하여 VS Code 실행
Linux $ launch-code --server <Windows IP>
```
