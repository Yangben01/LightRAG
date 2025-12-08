#!/bin/bash

#####################################################################################################
# 清理前端和后端虚拟环境依赖脚本
# 
# 用途：清理 node_modules、Python 虚拟环境、缓存文件等
# 使用方法：chmod +x clean_dependencies.sh && ./clean_dependencies.sh
#####################################################################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目根目录（使用脚本所在目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# 计算目录大小
get_size() {
    if [ -d "$1" ]; then
        du -sh "$1" 2>/dev/null | cut -f1
    else
        echo "0"
    fi
}

# 清理前端依赖
clean_frontend() {
    log "清理前端依赖..."

    cd "$PROJECT_ROOT/lightrag_webui"

    # 清理 node_modules（相对当前目录）
    if [ -d "node_modules" ]; then
        SIZE=$(get_size "node_modules")
        log_info "删除 node_modules (大小: $SIZE)..."
        rm -rf node_modules
        log "✓ node_modules 已删除"
    else
        log_info "node_modules 不存在，跳过"
    fi

    # 清理 .next 构建目录
    if [ -d ".next" ]; then
        SIZE=$(get_size ".next")
        log_info "删除 .next 构建目录 (大小: $SIZE)..."
        rm -rf .next
        log "✓ .next 已删除"
    fi

    # 清理 npm/yarn/pnpm 缓存文件
    log_info "清理 npm/yarn/pnpm 缓存文件..."
    rm -f npm-debug.log* yarn-debug.log* yarn-error.log* .pnpm-debug.log* lerna-debug.log*
    rm -rf .npm .yarn .pnp .pnp.js

    # 清理 ESLint 缓存
    if [ -f ".eslintcache" ]; then
        rm -f .eslintcache
        log_info "✓ ESLint 缓存已删除"
    fi

    log "前端依赖清理完成 ✓"
}

# 清理后端依赖
clean_backend() {
    log "清理后端依赖..."

    cd "$PROJECT_ROOT/lightrag"

    # 清理虚拟环境（相对当前目录）
    for venv_dir in "venv" ".venv" "env" ".env"; do
        if [ -d "$venv_dir" ]; then
            SIZE=$(get_size "$venv_dir")
            log_info "删除虚拟环境 $venv_dir (大小: $SIZE)..."
            rm -rf "$venv_dir"
            log "✓ $venv_dir 已删除"
        fi
    done

    # 清理根目录的虚拟环境（相对当前目录）
    cd "$PROJECT_ROOT"
    for venv_dir in "venv" ".venv" "env"; do
        if [ -d "$venv_dir" ] && [ "$venv_dir" != "backend/venv" ]; then
            SIZE=$(get_size "$venv_dir")
            log_info "删除根目录虚拟环境 $venv_dir (大小: $SIZE)..."
            rm -rf "$venv_dir"
            log "✓ $venv_dir 已删除"
        fi
    done

    cd "$PROJECT_ROOT/lightrag"

    # 清理 Python 缓存文件
    log_info "清理 Python 缓存文件..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    find . -type f -name "*.pyd" -delete 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

    # 清理构建目录
    log_info "清理构建目录..."
    rm -rf build/ dist/ *.egg-info .eggs/

    # 清理测试和覆盖率文件
    log_info "清理测试缓存..."
    rm -rf .pytest_cache/ .coverage htmlcov/ .tox/ .nox/ .hypothesis/
    rm -rf .mypy_cache/ .pytype/ .dmypy.json dmypy.json

    log "后端依赖清理完成 ✓"
}

# 清理其他缓存
clean_other() {
    log "清理其他缓存文件..."

    cd "$PROJECT_ROOT"

    # 清理 IDE 缓存（相对当前目录）
    log_info "清理 IDE 缓存..."
    rm -rf .vscode/.ropeproject .idea/
    find . -type f -name "*.swp" -delete 2>/dev/null || true
    find . -type f -name "*.swo" -delete 2>/dev/null || true
    find . -type f -name "*~" -delete 2>/dev/null || true

    # 清理日志文件
    log_info "清理日志文件..."
    find . -type f -name "*.log" -not -path "./node_modules/*" -not -path "./.git/*" -delete 2>/dev/null || true
    
    # 清理临时文件
    log_info "清理临时文件..."
    rm -rf .DS_Store Thumbs.db
    
    log "其他缓存清理完成 ✓"
}

# 显示清理统计
show_summary() {
    log ""
    log "════════════════════════════════════════"
    log "  清理完成！"
    log "════════════════════════════════════════"
    log ""
    log "已清理内容："
    log "  ✓ 前端: node_modules, .next, 缓存文件"
    log "  ✓ 后端: 虚拟环境, __pycache__, 构建文件"
    log "  ✓ 其他: IDE 缓存, 日志文件, 临时文件"
    log ""
    log "下一步操作："
    log "  1. 前端: cd frontend && npm install"
    log "  2. 后端: cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    log ""
}

# 主函数
main() {
    log "开始清理依赖..."
    log "项目根目录: $PROJECT_ROOT"
    log ""
    
    # 确认操作
    read -p "确定要清理所有依赖吗？这将删除 node_modules 和虚拟环境 (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "操作已取消"
        exit 0
    fi
    
    log ""
    
    # 执行清理
    clean_frontend
    log ""
    clean_backend
    log ""
    clean_other
    log ""
    
    # 显示总结
    show_summary
}

# 运行主函数
main
