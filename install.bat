@echo off
REM Re-install `remote-code` (and `vscode-server`) when needed.
REM Same rules as install.sh:
REM   - uv missing            -^> install uv (via mise if present, else the official install.ps1)
REM   - remote-code missing   -^> force install (uv tool install --force)
REM   - remote-code ^= 7 days old -^> force install
REM   - --force given         -^> force install immediately
REM Usage:
REM   install.bat [--force^|-f] [--help^|-h]

setlocal
set "FORCE=0"
set "STALE_DAYS=7"
set "REPO=git+https://github.com/tayaee/vscode-server.git"
set "PKG=vscode-server"

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--force" (
  set "FORCE=1"
) else if "%~1"=="-f" (
  set "FORCE=1"
) else if "%~1"=="--help" (
  call :usage
  exit /b 0
) else if "%~1"=="-h" (
  call :usage
  exit /b 0
) else (
  echo [install.bat] unknown argument: %~1 1>&2
  call :usage
  exit /b 2
)
shift
goto :parse_args
:args_done

call :ensure_uv
if errorlevel 1 exit /b 1

call :needs_install
if errorlevel 1 exit /b 0

call :do_install
exit /b %ERRORLEVEL%

REM ---------- subroutines below (called, never fall through) ----------

:usage
echo Usage: install.bat [--force ^| -f] [--help ^| -h]
exit /b 0

:ensure_uv
where uv >nul 2>nul
if not errorlevel 1 exit /b 0
where mise >nul 2>nul
if errorlevel 1 goto :install_uv_ps1
echo [install.bat] uv not found; installing via mise... 1>&2
mise use -g uv
where uv >nul 2>nul
if not errorlevel 1 exit /b 0
echo [install.bat] error: mise finished but 'uv' is still not on PATH. 1>&2
echo [install.bat] hint: open a new terminal. 1>&2
exit /b 1
:install_uv_ps1
echo [install.bat] uv not found; installing via install.ps1... 1>&2
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
where uv >nul 2>nul
if not errorlevel 1 exit /b 0
echo [install.bat] error: uv install finished but 'uv' is still not on PATH. 1>&2
echo [install.bat] hint: open a new terminal. 1>&2
exit /b 1

REM exit 0 = needs install, exit 1 = fresh (skip).
:needs_install
if "%FORCE%"=="1" exit /b 0
where remote-code >nul 2>nul
if errorlevel 1 (
  echo [install.bat] remote-code not found; will install. 1>&2
  exit /b 0
)
set "RC="
for /f "delims=" %%i in ('where remote-code 2^>nul') do if not defined RC set "RC=%%i"
if not defined RC (
  echo [install.bat] cannot locate remote-code; will reinstall to be safe. 1>&2
  exit /b 0
)
set "AGE="
for /f "delims=" %%a in ('powershell -NoProfile -Command "& { $p='%RC%'; try { $age=((Get-Date)-(Get-Item -LiteralPath $p).LastWriteTime).TotalDays } catch { echo STALE; exit }; if ($age -ge %STALE_DAYS%) { echo STALE } else { echo FRESH } }" 2^>nul') do set "AGE=%%a"
if "%AGE%"=="FRESH" (
  echo [install.bat] remote-code is fresh; skipping ^(use --force to reinstall^). 1>&2
  exit /b 1
)
echo [install.bat] remote-code is stale ^(^>= %STALE_DAYS%d^); will reinstall. 1>&2
exit /b 0

:do_install
echo [install.bat] installing %PKG% ^(uv tool install --force^)... 1>&2
uv tool install --from %REPO% --force %PKG%
if errorlevel 1 (
  echo [install.bat] error: install failed. 1>&2
  exit /b 1
)
where remote-code >nul 2>nul
if errorlevel 1 (
  echo [install.bat] warning: install finished but 'remote-code' is not on PATH. 1>&2
  echo [install.bat] hint: open a new terminal. 1>&2
  exit /b 0
)
set "VER="
for /f "delims=" %%v in ('remote-code --version 2^>^&1') do if not defined VER set "VER=%%v"
if defined VER (
  echo [install.bat] done: %VER% 1>&2
) else (
  echo [install.bat] done: remote-code installed. 1>&2
)
echo + vscode-server --version
vscode-server --version
exit /b 0
