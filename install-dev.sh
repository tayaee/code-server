#!/usr/bin/env bash
echo + uv tool install --force --editable .
uv tool install --force --editable .
echo + vsls --version
vsls --version
echo + vslc --version
vslc --version
echo + remote-code --version
remote-code --version
