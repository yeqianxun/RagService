#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$APP_DIR/.venv"

cd "$APP_DIR"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r requirements.txt

cp -n .env.example .env || true
mkdir -p uploads

exec gunicorn app.main:app -c gunicorn_conf.py
