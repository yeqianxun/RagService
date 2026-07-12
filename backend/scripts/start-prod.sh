#!/bin/bash
# ========================================
# FastAPI RAG 系统 - 生产环境启动脚本
# ========================================
# 适用于 Linux 和 macOS 系统
# ========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ========================================
# 主函数
# ========================================
main() {
    cd "$BACKEND_DIR"
    
    echo ""
    echo "========================================"
    echo " FastAPI RAG 系统 - 生产环境启动"
    echo "========================================"
    echo ""

    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        log_error ".env 文件不存在！"
        log_info "请先运行 ./scripts/setup-production.sh 进行配置"
        exit 1
    fi

    # 检查 Docker 是否安装
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装！"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装！"
        exit 1
    fi

    log_info "正在检查 Docker 服务状态..."
    if ! docker info &> /dev/null; then
        log_error "Docker 服务未运行！"
        exit 1
    fi

    log_info "正在拉取/构建 Docker 镜像..."
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.prod.yml build --pull
    else
        docker-compose -f docker-compose.prod.yml build --pull
    fi

    echo ""
    log_info "正在启动服务..."
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.prod.yml up -d
    else
        docker-compose -f docker-compose.prod.yml up -d
    fi

    echo ""
    log_success "服务已启动！"
    echo ""
    log_info "服务信息："
    echo "  - 后端 API: http://localhost:8000"
    echo "  - API 文档: http://localhost:8000/docs"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000"
    echo ""
    log_info "查看日志运行: docker compose -f docker-compose.prod.yml logs -f"
    log_info "停止服务运行: ./scripts/stop-prod.sh"
    echo ""
}

# 运行主函数
main
