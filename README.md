# code-server

Windows VS Code로 원격 Linux 디렉토리를 여는 도구 (Linux에 VS Code 불필요).

## Windows
설치 / 업그레이드 (같은 명령어)
```
Windows % uv tool install --from git+https://github.com/tayaee/code-server.git --force code-server
Windows % code-server --version
```

실행
```
# Port 8259에서 launch-code의 접속을 받아 VS Code 원격 접속을 시작하는 서버.
Windows % code-server
```

참고: Windows 로그인과 Linux 로그인이 다르면 `%USERPROFILE%\.ssh\config`의 해당 `Host`에 `User <Linux ID>` 등록이 필요함 (없으면 code-server가 `Host`/`HostName`/`User` 블록을 자동 생성함). 파일 스펙은 OpenBSD ssh_config 매뉴얼 https://man.openbsd.org/ssh_config , VS Code Remote-SSH 문서 https://code.visualstudio.com/docs/remote/ssh 참조.

## Linux
ssh 로그인 하여 설치 / 업그레이드 (같은 명령어)
```
Linux $ uv tool install --from git+https://github.com/tayaee/code-server.git --force code-server
Linux $ launch-code --version
```

실행
```
Linux $ cd /path/to/git-repo

# Method 1. 환경변수 CODE_SERVER_HOST 또는 SSH_CONNECTION 또는 SSH_CLIENT에서 Windows IP를 추출하여 자동 접속
Linux $ launch-code   

# Method 2. VS Code가 설치된 Windows IP를 바로지정하여 VS Code 실행
Linux $ launch-code --server <Windows IP>
```
