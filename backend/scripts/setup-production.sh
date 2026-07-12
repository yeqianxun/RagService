#!/bin/bash
# ========================================
# FastAPI RAG 系统 - 生产环境配置脚本
# ========================================
# 适用于 Linux 和 macOS 系统
# ========================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
# 生成随机密钥函数
# ========================================
generate_random_key() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    elif command -v python3 &> /dev/null; then
        python3 -c "import secrets; print(secrets.token_hex(32))"
    else
        # 回退方案 - 使用 /dev/urandom
        cat /dev/urandom | head -c 32 | xxd -p -c 32
    fi
}

# ========================================
# 主函数
# ========================================
main() {
    echo ""
    echo "========================================"
    echo " FastAPI RAG 系统 - 生产环境配置"
    echo "========================================"
    echo ""

    # 检查是否已存在 .env 文件
    if [ -f "$BACKEND_DIR/.env" ]; then
        log_warning ".env 文件已存在！"
        read -p "是否覆盖现有的 .env 文件？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "配置已取消。"
            exit 1
        fi
        # 备份现有文件
        cp "$BACKEND_DIR/.env" "$BACKEND_DIR/.env.backup.$(date +%Y%m%d%H%M%S)"
        log_info "已备份现有 .env 文件"
    fi

    # 复制模板文件
    log_info "正在从 .env.example 复制模板..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"

    # ========================================
    # 交互式配置
    # ========================================
    echo ""
    echo "请根据提示配置以下参数（直接回车使用默认值）："
    echo ""

    # 1. SECRET_KEY
    DEFAULT_SECRET_KEY=$(generate_random_key)
    read -p "请输入 SECRET_KEY [随机生成]: " SECRET_KEY
    SECRET_KEY=${SECRET_KEY:-$DEFAULT_SECRET_KEY}
    sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$BACKEND_DIR/.env"

    # 2. 数据库配置
    read -p "请输入数据库用户名 [postgres]: " DB_USER
    DB_USER=${DB_USER:-postgres}
    
    read -s -p "请输入数据库密码: " DB_PASSWORD
    echo
    DB_PASSWORD=${DB_PASSWORD:-change-me}
    
    read -p "请输入数据库主机 [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    
    read -p "请输入数据库端口 [5432]: " DB_PORT
    DB_PORT=${DB_PORT:-5432}
    
    read -p "请输入数据库名称 [rag_service]: " DB_NAME
    DB_NAME=${DB_NAME:-rag_service}
    
    DATABASE_URL="postgresql+psycopg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
    sed -i.bak "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" "$BACKEND_DIR/.env"

    # 3. CORS 配置
    echo ""
    log_info "CORS 配置（只允许特定域名访问）"
    read -p "请输入允许的 CORS 域名（多个用逗号分隔） [https://your-domain.com]: " CORS_INPUT
    CORS_INPUT=${CORS_INPUT:-https://your-domain.com}
    
    # 转换为 JSON 数组格式
    CORS_ARRAY=$(echo "$CORS_INPUT" | awk -F',' '{printf "["; for(i=1;i<=NF;i++) {gsub(/^[ \t]+|[ \t]+$/, "", $i); printf "\"%s\"", $i; if(i<NF) printf ","}; printf "]"}')
    sed -i.bak "s|CORS_ORIGINS=.*|CORS_ORIGINS=$CORS_ARRAY|" "$BACKEND_DIR/.env"

    # 4. DeepSeek API 配置
    echo ""
    read -p "请输入 DeepSeek API Key: " LLM_API_KEY
    if [ -n "$LLM_API_KEY" ]; then
        sed -i.bak "s/LLM_API_KEY=.*/LLM_API_KEY=$LLM_API_KEY/" "$BACKEND_DIR/.env"
    else
        log_warning "未配置 DeepSeek API Key，RAG 功能将不可用！"
    fi

    # 5. Redis 配置
    echo ""
    read -p "请输入 Redis 主机 [localhost]: " REDIS_HOST
    REDIS_HOST=${REDIS_HOST:-localhost}
    sed -i.bak "s/REDIS_HOST=.*/REDIS_HOST=$REDIS_HOST/" "$BACKEND_DIR/.env"
    
    read -p "请输入 Redis 端口 [6379]: " REDIS_PORT
    REDIS_PORT=${REDIS_PORT:-6379}
    sed -i.bak "s/REDIS_PORT=.*/REDIS_PORT=$REDIS_PORT/" "$BACKEND_DIR/.env"
    
    read -s -p "请输入 Redis 密码 (可选): " REDIS_PASSWORD
    echo
    if [ -n "$REDIS_PASSWORD" ]; then
        sed -i.bak "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASSWORD/" "$BACKEND_DIR/.env"
    fi

    # 6. 管理员配置
    echo ""
    read -p "请输入管理员邮箱 [admin@your-domain.com]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@your-domain.com}
    sed -i.bak "s/DEFAULT_ADMIN_EMAIL=.*/DEFAULT_ADMIN_EMAIL=$ADMIN_EMAIL/" "$BACKEND_DIR/.env"
    
    read -s -p "请输入管理员密码: " ADMIN_PASSWORD
    echo
    if [ -n "$ADMIN_PASSWORD" ]; then
        sed -i.bak "s/DEFAULT_ADMIN_PASSWORD=.*/DEFAULT_ADMIN_PASSWORD=$ADMIN_PASSWORD/" "$BACKEND_DIR/.env"
    fi

    # 清理临时备份文件
    rm -f "$BACKEND_DIR/.env.bak"

    # ========================================
    # 完成配置
    # ========================================
    echo ""
    echo "========================================"
    log_success "生产环境配置已完成！"
    echo "========================================"
    echo ""
    log_info "配置文件位置: $BACKEND_DIR/.env"
    echo ""
    log_warning "重要安全提醒："
    echo "1. 请确保 .env 文件不会被提交到版本控制系统！"
    echo "2. 建议检查 .gitignore 文件是否包含 .env"
    echo "3. 生产环境建议使用环境变量或密钥管理服务"
    echo ""
    log_info "下一步："
    echo "1. 检查 .env 文件内容是否正确"
    echo "2. 运行 'docker-compose -f docker-compose.prod.yml up -d' 启动服务"
    echo "3. 或运行 ./scripts/start-prod.sh 启动服务"
    echo ""
}

# 运行主函数
main
