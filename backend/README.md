# FastAPI Multi-Tenant Backend

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

## 默认初始化账号

- 租户编码: `platform`
- 管理员邮箱: `admin@example.com`
- 管理员密码: `Admin@123456`

## 本地运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
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
