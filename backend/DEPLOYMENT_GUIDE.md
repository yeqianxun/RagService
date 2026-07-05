# 部署指南

## 本地开发环境

### 环境要求
- Python 3.9+
- PostgreSQL 13+
- pgvector 扩展

### 步骤
1. 安装 PostgreSQL 并启用 pgvector 扩展
2. 克隆项目并进入 backend 目录
3. 创建虚拟环境并安装依赖
4. 配置环境变量
5. 启动应用

### 启动命令
```bash
# Windows
start_dev.bat

# Linux/Mac
./start_dev.sh
```

## 生产环境部署

### 方式一：传统部署（推荐用于简单部署）

#### 服务器要求
- Linux 服务器（Ubuntu 20.04+ 推荐）
- Python 3.9+
- PostgreSQL 13+（已安装 pgvector 扩展）
- nginx（可选，用于反向代理）

#### 部署步骤
1. 在服务器上克隆代码
2. 安装 Python 依赖
3. 配置环境变量
4. 启动服务

```bash
# 使用便捷脚本
bash start_prod.sh
```

#### 使用 systemd 管理服务（推荐）
创建服务文件 `/etc/systemd/system/rag-backend.service`：

```ini
[Unit]
Description=RAG Backend Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/your/backend
EnvironmentFile=/path/to/your/backend/.env
ExecStart=/path/to/your/backend/.venv/bin/gunicorn app.main:app -c gunicorn_conf.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启用并启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable rag-backend
sudo systemctl start rag-backend
```

### 方式二：Docker 部署（推荐用于容器化环境）

#### 单机部署
```bash
# 构建并启动
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### Kubernetes 部署（适用于大规模生产环境）
需要创建相应的 Deployment、Service 和 ConfigMap 资源文件。

## 环境变量配置

以下是必需的环境变量：

```env
# 应用配置
APP_NAME=FastAPI Multi Tenant System
APP_VERSION=1.0.0
DEBUG=false  # 生产环境设为 false
API_V1_PREFIX=/api/v1

# 安全配置
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# 数据库配置
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/database_name

# CORS 配置
CORS_ORIGINS=["https://yourdomain.com"]

# 上传目录
UPLOAD_DIR=./uploads

# 默认租户和管理员配置
DEFAULT_TENANT_NAME=Platform Tenant
DEFAULT_TENANT_CODE=platform
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_ADMIN_PASSWORD=SecurePassword123!
DEFAULT_ADMIN_FULL_NAME=Platform Admin
```

## 数据库迁移

当前系统使用 SQLAlchemy 的 create_all 方法进行自动迁移。在生产环境中，建议使用 Alembic 进行更精细的数据库迁移管理。

## 监控和日志

### 日志配置
- 访问日志和错误日志通过 gunicorn 输出
- 可以重定向到文件或发送到日志管理系统

## 部署前检查

在部署之前，您可以运行预检查脚本来验证环境配置：

```bash
python pre_deploy_check.py
```

该脚本将检查：
- Python 版本 (需要 3.9+)
- 必需的依赖包
- 环境文件配置
- 必需的目录
- 数据库连接

## 监控和日志

### 日志配置
- 访问日志和错误日志通过 gunicorn 输出
- 可以重定向到文件或发送到日志管理系统

### 健康检查
- 应用提供基本的健康检查端点
- 可以通过监控系统定期检查 `/api/v1/health` 端点
- 端点返回 200 状态码和 {"status": "ok"} 表示服务正常

## 性能优化建议

1. 使用 Redis 作为缓存层
2. 配置数据库连接池
3. 使用 CDN 加速静态资源
4. 启用 Gzip 压缩
5. 配置合适的 workers 数量（CPU 核心数 * 2 + 1）

## 安全建议

1. 使用 HTTPS
2. 定期更新依赖包
3. 使用强密码策略
4. 限制数据库访问权限
5. 定期备份数据