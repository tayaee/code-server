#!/usr/bin/env bash
echo + uv tool install --force --editable .
uv tool install --force --editable .
echo + vscode-server --version
vscode-server --version
