@echo off
REM Dev install: assumes `uv` is already available. Installs the local checkout editable.
echo + uv tool install --force --editable .
uv tool install --force --editable .
echo + remote-code --version
remote-code --version
