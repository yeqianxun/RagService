#!/usr/bin/env bash
set -euo pipefail

# 检测操作系统并设置适当的命令
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows 环境
    SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
    APP_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
    VENV_DIR="$APP_DIR/.venv"
    
    cd "$APP_DIR"
    
    python -m venv "$VENV_DIR"
    source "$VENV_DIR/Scripts/activate"
else
    # Unix/Linux 环境
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    VENV_DIR="$APP_DIR/.venv"
    
    cd "$APP_DIR"
    
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
fi

pip install --upgrade pip
pip install -r requirements.txt

# 复制环境变量文件（如果不存在）
if [ ! -f .env ]; then
    cp .env.example .env
    echo "已创建 .env 文件，请根据需要编辑配置"
fi

mkdir -p uploads

echo "启动应用..."
exec gunicorn app.main:app -c gunicorn_conf.py
