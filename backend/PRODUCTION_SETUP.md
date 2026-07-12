# FastAPI RAG 系统 - 生产环境部署指南

## 概述

本文档提供了将 FastAPI RAG 系统部署到生产环境的完整指南（Linux/macOS）。

## 前置要求

- Docker 和 Docker Compose 已安装
- 有效的 DeepSeek API Key
- PostgreSQL 和 Redis 服务（或使用 Docker 容器）

## 快速开始

### 1. 配置生产环境

```bash
# 1. 进入后端目录
cd backend

# 2. 给脚本添加执行权限
chmod +x scripts/setup-production.sh
chmod +x scripts/start-prod.sh
chmod +x scripts/stop-prod.sh

# 3. 运行配置脚本
./scripts/setup-production.sh
```

配置脚本将引导您设置以下参数：
- SECRET_KEY（自动生成强随机密钥）
- 数据库连接信息
- CORS 允许的域名
- DeepSeek API Key
- Redis 配置
- 管理员账号

### 2. 启动生产环境

```bash
./scripts/start-prod.sh
```

### 3. 访问服务

服务启动后，可以通过以下地址访问：

- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (默认账号: admin/admin)

### 4. 停止服务

```bash
./scripts/stop-prod.sh
```

## 生产环境最佳实践

### 1. 安全配置

- **SECRET_KEY**: 必须使用强随机字符串，不要使用默认值
- **数据库密码**: 使用强密码，定期更换
- **Redis 密码**: 生产环境必须设置 Redis 密码
- **CORS 配置**: 只允许特定的域名访问，不要使用通配符

### 2. 网络安全

- 生产环境建议使用反向代理（Nginx, Traefik 等）
- 配置 HTTPS 和证书自动更新（Let's Encrypt）
- 限制不必要的端口暴露
- 配置防火墙规则

### 3. 数据安全

- 定期备份数据库
- 加密敏感数据
- 配置数据卷持久化
- 实施访问控制

### 4. 监控和日志

- 使用 Prometheus + Grafana 进行监控
- 配置日志轮转和归档
- 设置告警规则
- 定期检查系统健康状态

## Docker 直接操作

如果需要直接使用 Docker Compose 命令：

```bash
# 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 停止服务（保留数据）
docker-compose -f docker-compose.prod.yml down

# 停止并删除所有数据
docker-compose -f docker-compose.prod.yml down -v

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart backend
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `.env.example` | 环境变量模板文件 |
| `docker-compose.prod.yml` | 生产环境 Docker Compose 配置 |
| `scripts/setup-production.sh` | Linux/macOS 配置脚本 |
| `scripts/start-prod.sh` | Linux/macOS 启动脚本 |
| `scripts/stop-prod.sh` | Linux/macOS 停止脚本 |
| `.gitignore` | Git 忽略文件配置 |

## 故障排查

### 服务无法启动

1. 检查 Docker 服务是否正常运行
2. 查看服务日志: `docker-compose -f docker-compose.prod.yml logs`
3. 确认端口没有被占用
4. 检查 .env 文件配置是否正确

### 数据库连接失败

1. 确认 PostgreSQL 容器正常运行
2. 检查 DATABASE_URL 配置是否正确
3. 确认数据库用户权限
4. 查看数据库容器日志

### Redis 连接失败

1. 确认 Redis 容器正常运行
2. 检查 Redis 密码配置
3. 查看 Redis 容器日志

### API 请求限流

系统已配置限流中间件，默认限制：
- 登录接口: 5 次/分钟
- RAG 查询: 30 次/分钟
- 文件上传: 10 次/小时

如需要调整，可以修改 `app/core/rate_limiter.py` 配置。

## 技术支持

如遇到问题，请检查：
1. 服务日志
2. 系统资源使用情况
3. 网络连接状态
4. 环境变量配置
