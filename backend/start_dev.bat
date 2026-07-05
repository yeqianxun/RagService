@echo off
REM Windows 批处理脚本，用于启动开发服务器

REM 检查是否已存在虚拟环境
if not exist .venv (
    echo 创建虚拟环境...
    python -m venv .venv
)

echo 激活虚拟环境...
call .venv\Scripts\activate.bat

echo 安装依赖...
pip install -r requirements.txt

echo 检查 .env 文件...
if not exist .env (
    echo 复制 .env.example 到 .env
    copy .env.example .env
)

echo 启动开发服务器...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause