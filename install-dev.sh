#!/usr/bin/env bash
echo + uv tool install --force --editable .
uv tool install --force --editable .
echo + rvl-server --version
rvl-server --version
echo + rvl --version
rvl --version
