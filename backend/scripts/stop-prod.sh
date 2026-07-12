#!/bin/bash
# ========================================
# FastAPI RAG 系统 - 生产环境停止脚本
# ========================================
# 适用于 Linux 和 macOS 系统
# ========================================

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

# ========================================
# 主函数
# ========================================
main() {
    cd "$BACKEND_DIR"

    echo ""
    echo "========================================"
    echo " FastAPI RAG 系统 - 停止生产环境服务"
    echo "========================================"
    echo ""

    # 询问是否保留数据卷
    read -p "是否保留数据卷？(Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_warning "将删除所有数据卷！"
        read -p "确认删除所有数据？(yes/NO): " -n 3 -r
        echo
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "已取消删除操作。"
            exit 0
        fi

        log_info "正在停止并删除所有服务和数据卷..."
        if docker compose version &> /dev/null; then
            docker compose -f docker-compose.prod.yml down -v
        else
            docker-compose -f docker-compose.prod.yml down -v
        fi
        log_success "所有服务和数据卷已删除！"
    else
        log_info "正在停止服务（保留数据）..."
        if docker compose version &> /dev/null; then
            docker compose -f docker-compose.prod.yml down
        else
            docker-compose -f docker-compose.prod.yml down
        fi
        log_success "服务已停止，数据已保留！"
    fi

    echo ""
}

# 运行主函数
main
