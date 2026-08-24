#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV="$ROOT/.venv"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --disable-pip-version-check -e "$ROOT"
(cd "$ROOT" && "$VENV/bin/python" -m compileall -q gbcforge tests && "$VENV/bin/python" -m unittest discover -s tests -v)
echo "AIGameAssets installation verified"
