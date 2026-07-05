# 使用官方 Python 基础镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        postgresql-server-dev-all \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY backend/requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ .

# 创建上传目录
RUN mkdir -p uploads

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["gunicorn", "app.main:app", "-c", "gunicorn_conf.py"]