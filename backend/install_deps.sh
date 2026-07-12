#!/bin/bash
# ========================================
# FastAPI RAG 系统 - 依赖安装脚本
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

# ========================================
# 主函数
# ========================================
main() {
    cd "$BACKEND_DIR"

    echo ""
    echo "========================================"
    echo " FastAPI RAG 系统 - 安装依赖"
    echo "========================================"
    echo ""

    # 检查 Python 是否安装
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Python 未安装！"
        exit 1
    fi

    # 确定 Python 命令
    if command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
        PIP_CMD=pip3
    else
        PYTHON_CMD=python
        PIP_CMD=pip
    fi

    log_info "使用 Python 命令: $PYTHON_CMD"

    # 检查虚拟环境
    if [ ! -d ".venv" ]; then
        log_warning "虚拟环境不存在，正在创建..."
        $PYTHON_CMD -m venv .venv
        log_success "虚拟环境创建成功！"
    fi

    # 激活虚拟环境
    log_info "激活虚拟环境..."
    source .venv/bin/activate

    # 更新 pip
    log_info "更新 pip..."
    $PIP_CMD install --upgrade pip setuptools wheel

    # 安装依赖
    log_info "安装依赖包..."
    $PIP_CMD install -r requirements.txt

    echo ""
    log_success "依赖安装完成！"
    echo ""
    log_info "验证安装..."

    # 验证关键模块
    echo ""
    echo "验证模块安装："
    echo "----------------------------------------"

    modules=("fastapi" "slowapi" "limits" "langchain" "redis" "sqlalchemy")
    all_ok=true

    for module in "${modules[@]}"; do
        if $PYTHON_CMD -c "import $module" 2>/dev/null; then
            version=$($PYTHON_CMD -c "import $module; print(getattr($module, '__version__', 'unknown'))" 2>/dev/null || echo "unknown")
            echo -e "  ${GREEN}✓${NC} $module ($version)"
        else
            echo -e "  ${RED}✗${NC} $module"
            all_ok=false
        fi
    done

    echo "----------------------------------------"
    echo ""

    if [ "$all_ok" = true ]; then
        log_success "所有依赖安装成功！"
    else
        log_warning "部分模块安装失败，请检查日志。"
    fi

    echo ""
    log_info "激活虚拟环境运行: source .venv/bin/activate"
    log_info "或者使用启动脚本: ./scripts/start-prod.sh"
    echo ""
}

# 运行主函数
main
