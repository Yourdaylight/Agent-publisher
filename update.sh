#!/usr/bin/env bash
# ============================================================================
# update.sh — Agent Publisher 快速更新重启
#
# 用法:
#   bash update.sh                 # 完整更新: pull + 依赖 + 前端构建 + 重启
#   bash update.sh --no-pull       # 跳过 git pull（手动改完代码后使用）
#   bash update.sh --backend-only  # 跳过前端构建（只改了后端代码时加速）
# ============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# 颜色 & 输出工具
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
DO_PULL=true
DO_FRONTEND=true

for arg in "$@"; do
    case "$arg" in
        --no-pull)       DO_PULL=false ;;
        --backend-only)  DO_FRONTEND=false ;;
        -h|--help)
            echo "用法: bash update.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --no-pull        跳过 git pull（适用于手动修改代码后重新构建）"
            echo "  --backend-only   跳过前端构建（只更改了后端代码时加速更新）"
            echo "  -h, --help       显示此帮助信息"
            exit 0
            ;;
        *)
            error "未知参数: $arg"
            echo "使用 --help 查看可用选项"
            exit 1
            ;;
    esac
done

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="agent-publisher"

# ---------------------------------------------------------------------------
# 开始更新
# ---------------------------------------------------------------------------
echo -e "${BOLD}${GREEN}"
echo "╔═══════════════════════════════════════════════╗"
echo "║        Agent Publisher — 快速更新             ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

cd "$INSTALL_DIR"

# 记录更新前的 commit
COMMIT_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
info "当前版本: ${COMMIT_BEFORE} ($(git log -1 --format='%s' 2>/dev/null || echo 'N/A'))"

# ============================================================================
# 步骤 1: 拉取最新代码
# ============================================================================
if [[ "$DO_PULL" == true ]]; then
    step "步骤 1: 拉取最新代码"
    if git pull; then
        COMMIT_AFTER=$(git rev-parse --short HEAD)
        if [[ "$COMMIT_BEFORE" == "$COMMIT_AFTER" ]]; then
            info "已是最新版本 ($COMMIT_AFTER)"
        else
            success "代码已更新: $COMMIT_BEFORE → $COMMIT_AFTER"
            # 显示更新的 commit 列表
            echo ""
            git log --oneline "${COMMIT_BEFORE}..${COMMIT_AFTER}" 2>/dev/null | head -20 || true
            echo ""
        fi
    else
        error "git pull 失败"
        warn "请检查是否有未提交的本地修改: git status"
        warn "如已手动修改代码，可使用: bash update.sh --no-pull"
        exit 1
    fi
else
    step "步骤 1: 跳过 git pull (--no-pull)"
fi

# ============================================================================
# 步骤 2: 更新 Python 依赖
# ============================================================================
step "步骤 2: 更新 Python 依赖"
if uv sync; then
    success "Python 依赖更新完成"
else
    error "Python 依赖更新失败"
    warn "请检查 pyproject.toml 和网络连接"
    exit 1
fi

# ============================================================================
# 步骤 3: 构建前端
# ============================================================================
if [[ "$DO_FRONTEND" == true ]]; then
    step "步骤 3: 构建前端"
    if command -v node &>/dev/null && command -v npm &>/dev/null; then
        cd "$INSTALL_DIR/web"

        if npm install; then
            success "前端依赖安装完成"
        else
            error "npm install 失败"
            exit 1
        fi

        if npm run build; then
            success "前端构建完成"
        else
            error "前端构建失败"
            exit 1
        fi

        cd "$INSTALL_DIR"
    else
        info "未检测到 Node.js / npm，使用 git 仓库中预构建的前端资源"
    fi
else
    step "步骤 3: 跳过前端构建 (--backend-only)"
fi

# ============================================================================
# 步骤 4: 重启服务
# ============================================================================
step "步骤 4: 重启服务"

CMD_PREFIX=""
[[ $EUID -ne 0 ]] && CMD_PREFIX="sudo"

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "重启 $SERVICE_NAME 服务..."
    $CMD_PREFIX systemctl restart "$SERVICE_NAME"

    # 等待服务启动
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "服务重启成功！"
    else
        error "服务重启失败"
        warn "查看日志: journalctl -u $SERVICE_NAME -n 50 --no-pager"
        $CMD_PREFIX systemctl status "$SERVICE_NAME" --no-pager || true
        exit 1
    fi
else
    warn "systemd 服务未安装，请先运行 install.sh"
    warn "尝试手动启动..."
    info "可以手动运行: cd $INSTALL_DIR && uv run uvicorn agent_publisher.main:app --host 0.0.0.0 --port 9099"
    exit 1
fi

# ============================================================================
# 显示结果
# ============================================================================
COMMIT_FINAL=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║        ✅ 更新完成！                          ║${NC}"
echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}版本${NC}:  $COMMIT_BEFORE → $COMMIT_FINAL"
echo -e "  ${CYAN}状态${NC}:  $(systemctl is-active $SERVICE_NAME 2>/dev/null || echo 'unknown')"

# 获取端口号
PORT=$(grep -E '^PORT=' "$INSTALL_DIR/.env" 2>/dev/null | cut -d= -f2 || echo "9099")
echo -e "  ${CYAN}地址${NC}:  http://localhost:${PORT}"
echo ""
echo -e "  ${BOLD}查看日志:${NC} journalctl -u ${SERVICE_NAME} -f"
echo ""
