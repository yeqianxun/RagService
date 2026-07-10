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
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/database_name
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
- `GET /api/v1/permissions`
- `POST /api/v1/permissions`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/users/roles`
- `POST /api/v1/users/upload`
- `GET /api/v1/health` (健康检查端点)

## 权限与安全设计

系统提供**两种授权校验机制**，根据业务场景选择使用：

### 1. 基于权限编码的校验 — `require_permissions`

适用于**租户内部**的资源操作，如查看租户列表、管理用户等。

```python
# GET /api/v1/tenants — 需要 tenant:read 权限
current_user: User = Depends(require_permissions("tenant:read"))
```

- 校验当前用户角色是否包含指定的权限编码
- 权限编码通过 `Role ←→ Permission` 多对多关联表分配
- 租户管理员通过 `init_db.py` 中的 `DEFAULT_ADMIN_PERMISSION_CODES` 获得默认权限

### 2. 基于超级管理员身份的校验 — `is_superuser`

适用于**跨租户**的系统级操作，如创建新租户。

```python
# POST /api/v1/tenants — 仅超级管理员可用
current_user: User = Depends(get_current_active_user)

if not current_user.is_superuser:
    raise AppException.from_error(AppErrorCode.PERMISSION_DENIED)
```

- 直接检查 JWT payload 中的 `is_superuser` 字段
- 适用于不属于某个具体租户权限体系的全局操作
- 普通租户内的 admin 角色也不应当拥有此能力

### 3. 两种机制的选择原则

| 场景 | 校验方式 | 原因 |
|---|---|---|
| 租户内的 CRUD（用户管理、角色管理） | `require_permissions("xxx")` | 权限可被租户管理员灵活分配 |
| 跨租户系统操作（创建租户） | `is_superuser` 硬校验 | 不应属于任何租户的权限范畴 |
| 读取当前用户信息 | `get_current_active_user` | 仅需认证，无需额外校验 |
| 查看租户列表 | `require_permissions("tenant:read")` + `is_superuser` 分流 | 超级管理员看全部，普通用户只看自己的 |

### 4. 权限数据模型

权限系统重构为独立表结构，支持动态管理：

- **`permissions` 表** — 权限主表，包含 `code`(编码)、`name`(名称)、`description`(描述)、`module`(所属模块)
- **`role_permissions` 关联表** — `Role` 与 `Permission` 的多对多关联
- **预置权限**：9 个权限，分为 `tenant`、`user`、`permission` 三个模块
- **租户管理员默认权限**：6 个（不含 `tenant:create`、`permission:create`/`delete`/`update`）
- **超级管理员**：拥有全部 9 个权限

完整的权限 CRUD API 位于 `/api/v1/permissions` 路由下。

## 多租户安全策略

1. **数据行级隔离**：所有业务模型继承 `TenantScopedMixin`，通过 `tenant_id` 外键实现数据隔离
2. **租户创建限制**：仅超级管理员可创建新租户，防止横向越权
3. **认证链**：JWT 携带 `tenant_id` + `is_superuser` → `get_current_active_user` 验证身份 → 按需叠加 `require_permissions` 或 `is_superuser` 校验
4. **文件隔离**：上传文件按 `tenant_id` 子目录存储

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