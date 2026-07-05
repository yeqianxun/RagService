#!/bin/bash
# Linux/Mac 生产环境启动脚本

# 设置环境变量
export PYTHONPATH="$(pwd)"

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
echo "安装/更新依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "复制 .env.example 到 .env"
    cp .env.example .env
    echo "请编辑 .env 文件以配置环境变量"
fi

# 创建上传目录
mkdir -p uploads

# 启动应用
echo "启动生产服务器..."
gunicorn app.main:app -c gunicorn_conf.py