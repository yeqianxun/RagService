# FastAPI Multi-Tenant Backend with PostgreSQL + pgvector

## 目录结构

```text
backend
├── app
│   ├── api
│   ├── core
│   ├── db
│   ├── models
│   ├── schemas
│   └── services
├── scripts
├── .env.example
├── gunicorn_conf.py
└── requirements.txt
```

## 核心能力

- 基于 `APIRouter` 的分层路由组织
- `Pydantic v2` 数据校验与 `from_attributes` ORM 转换
- `SQLAlchemy 2.0` 异步 ORM 分层
- 基于 JWT 的登录鉴权与 `Depends` 权限依赖注入
- 多租户租户级数据隔离，默认按 `tenant_id` 过滤
- 统一异常处理与参数校验错误格式化
- CORS 中间件、`BackgroundTasks`、文件上传
- `lifespan` 生命周期初始化数据库与默认管理员
- `pydantic-settings` 环境变量管理
- 标准化返回体 `ResponseModel`
- PostgreSQL + pgvector 支持向量相似度搜索
- RAG (检索增强生成) 系统的数据存储能力

## 默认初始化账号

- 租户编码: `platform`
- 管理员邮箱: `admin@example.com`
- 管理员密码: `Admin@123456`

## 本地运行

### 环境准备

1. 安装 PostgreSQL 并启用 pgvector 扩展
2. 创建数据库并确保用户有适当权限

### 启动步骤

#### 方法一：手动启动
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 文件以配置数据库连接
uvicorn app.main:app --reload
```

#### 方法二：使用启动脚本

Windows:
```cmd
start_dev.bat
```

Linux/Mac:
```bash
chmod +x start_dev.sh
./start_dev.sh
```

### 环境变量配置

编辑 `.env` 文件，配置 PostgreSQL 连接：
```env
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/database_name
```

## 生产部署

有关详细的部署指南，包括各种环境的配置说明，请参阅 [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)。

在部署前，您可以运行预检查脚本来验证环境配置：
```bash
python pre_deploy_check.py
```

### 方式一：传统部署

使用 gunicorn 部署：
```bash
# 确保已安装依赖
pip install -r requirements.txt
# 复制环境变量文件
cp .env.example .env
# 编辑 .env 文件配置生产环境参数
# 运行部署脚本
bash scripts/deploy.sh  # Linux/Mac
# 或
powershell scripts/deploy.ps1  # Windows
# 或使用便捷启动脚本
bash start_prod.sh  # Linux/Mac
# 或
powershell start_prod.ps1  # Windows
```

或者手动运行：

```bash
gunicorn app.main:app -c gunicorn_conf.py
```

### 方式二：Docker 部署

使用 Docker Compose 部署整个应用栈（推荐）：

```bash
# 构建并启动服务
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

使用单独的 Docker 容器：

```bash
# 构建镜像
docker build -t rag-backend .

# 运行容器（需要先启动 PostgreSQL 服务）
docker run -d --name rag-backend-container \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://username:password@host:port/database \
  rag-backend
```

## 示例接口

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/tenants`
- `POST /api/v1/tenants`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/users/roles`
- `POST /api/v1/users/upload`
- `GET /api/v1/health` (健康检查端点)

## PostgreSQL + pgvector 设置

### 安装 PostgreSQL

1. 下载并安装 PostgreSQL
2. 启动 PostgreSQL 服务

### 安装 pgvector 扩展

```bash
# Ubuntu/Debian
git clone --depth=1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 或者使用 Docker
docker run --name postgres-pgvecto-rs -p 5432:5432 \
  -e POSTGRES_DB=mydatabase \
  -e POSTGRES_USER=username \
  -e POSTGRES_PASSWORD=password \
  -d tensorchord/pgvecto-rs:pg14-v0.2.0
```

### 数据库迁移

系统会在启动时自动创建所需的表和启用 pgvector 扩展。