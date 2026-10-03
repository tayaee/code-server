@echo off
REM Dev install: assumes `uv` is already available. Installs the local checkout editable.
echo + uv tool install --force --editable .
uv tool install --force --editable .
echo + vsls --version
vsls --version
echo + vslc --version
vslc --version
echo + remote-code --version
remote-code --version
