#!/usr/bin/env bash
# ============================================================================
# install.sh — Agent Publisher 首次安装向导
#
# 用法:
#   bash install.sh                  # 交互式安装
#   bash install.sh --non-interactive  # 非交互式（从环境变量读取配置）
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
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }
banner()  {
    echo -e "${BOLD}${GREEN}"
    echo "╔═══════════════════════════════════════════════╗"
    echo "║        Agent Publisher — 安装向导             ║"
    echo "╚═══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
NON_INTERACTIVE=false
for arg in "$@"; do
    case "$arg" in
        --non-interactive) NON_INTERACTIVE=true ;;
        -h|--help)
            echo "用法: bash install.sh [--non-interactive]"
            echo ""
            echo "  --non-interactive  从环境变量读取配置，跳过交互式向导"
            echo "                     需要设置: PORT, DATABASE_URL, DEFAULT_LLM_PROVIDER,"
            echo "                     DEFAULT_LLM_MODEL, DEFAULT_LLM_API_KEY, ACCESS_KEY, ADMIN_EMAILS"
            exit 0
            ;;
        *)
            error "未知参数: $arg"
            exit 1
            ;;
    esac
done

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="agent-publisher"

# ---------------------------------------------------------------------------
# 已安装检测
# ---------------------------------------------------------------------------
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    warn "Agent Publisher 服务已在运行中。"
    warn "如需更新，请使用: bash update.sh"
    echo ""
    read -rp "是否继续重新安装？(y/N) " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        info "已取消。"
        exit 0
    fi
fi

banner

# ============================================================================
# 步骤 1: 检测系统环境
# ============================================================================
step "步骤 1/6: 检测系统环境"

check_command() {
    local cmd="$1"
    local name="$2"
    local install_hint="$3"
    if command -v "$cmd" &>/dev/null; then
        local version
        version=$("$cmd" --version 2>&1 | head -1)
        success "$name 已安装: $version"
        return 0
    else
        error "$name 未找到"
        warn "  安装建议: $install_hint"
        return 1
    fi
}

check_python_version() {
    if ! command -v python3 &>/dev/null; then
        error "Python3 未找到"
        warn "  安装建议: sudo apt install python3 (Ubuntu) / brew install python3 (macOS)"
        return 1
    fi
    local py_version
    py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)
    if [[ "$py_major" -ge 3 && "$py_minor" -ge 10 ]]; then
        success "Python $py_version (>= 3.10 ✓)"
        return 0
    else
        error "Python $py_version 版本过低 (需要 >= 3.10)"
        return 1
    fi
}

check_node_version() {
    if ! command -v node &>/dev/null; then
        error "Node.js 未找到"
        warn "  安装建议: https://nodejs.org/ 或 nvm install 18"
        return 1
    fi
    local node_major
    node_major=$(node -v | sed 's/v//' | cut -d. -f1)
    if [[ "$node_major" -ge 18 ]]; then
        success "Node.js $(node -v) (>= 18 ✓)"
        return 0
    else
        error "Node.js $(node -v) 版本过低 (需要 >= 18)"
        return 1
    fi
}

MISSING=0
HAS_NODE=true
check_python_version || MISSING=1
check_node_version || { HAS_NODE=false; warn "无 Node.js — 将使用 git 仓库中预构建的前端资源"; }
if [[ "$HAS_NODE" == true ]]; then
    check_command npm "npm" "随 Node.js 一起安装" || { HAS_NODE=false; warn "无 npm — 将使用 git 仓库中预构建的前端资源"; }
fi
check_command uv "uv" "curl -LsSf https://astral.sh/uv/install.sh | sh" || MISSING=1
check_command git "git" "sudo apt install git (Ubuntu) / brew install git (macOS)" || MISSING=1

if [[ "$MISSING" -eq 1 ]]; then
    echo ""
    error "缺少必要的依赖，请先安装上述标记的工具后重试。"
    exit 1
fi

success "系统环境检测通过！"

# ============================================================================
# 步骤 2: 配置向导
# ============================================================================
step "步骤 2/6: 配置向导"

prompt_with_default() {
    local prompt_text="$1"
    local default_value="$2"
    local var_name="$3"
    local result

    if [[ "$NON_INTERACTIVE" == true ]]; then
        # 非交互模式：从环境变量读取，使用默认值作为后备
        result="${!var_name:-$default_value}"
    else
        read -rp "  $prompt_text [$default_value]: " result
        result="${result:-$default_value}"
    fi
    echo "$result"
}

prompt_secret() {
    local prompt_text="$1"
    local default_value="$2"
    local var_name="$3"
    local result

    if [[ "$NON_INTERACTIVE" == true ]]; then
        result="${!var_name:-$default_value}"
    else
        read -rsp "  $prompt_text [$default_value]: " result
        echo "" # 换行
        result="${result:-$default_value}"
    fi
    echo "$result"
}

# --- 服务端口 ---
info "服务器配置"
CFG_HOST=$(prompt_with_default "监听地址" "0.0.0.0" "HOST")
CFG_PORT=$(prompt_with_default "服务端口" "9099" "PORT")

# --- 数据库 ---
echo ""
info "数据库配置"
if [[ "$NON_INTERACTIVE" == true ]]; then
    CFG_DB_URL="${DATABASE_URL:-sqlite+aiosqlite:///agent_publisher.db}"
else
    echo "  1) SQLite (轻量, 默认)"
    echo "  2) PostgreSQL (生产环境推荐)"
    read -rp "  选择数据库类型 [1]: " db_choice
    db_choice="${db_choice:-1}"
    if [[ "$db_choice" == "2" ]]; then
        CFG_DB_URL=$(prompt_with_default "PostgreSQL 连接串" "postgresql+asyncpg://user:password@localhost:5432/agent_publisher" "DATABASE_URL")
    else
        CFG_DB_URL="sqlite+aiosqlite:///agent_publisher.db"
    fi
fi

# --- LLM 配置 ---
echo ""
info "LLM 配置"
CFG_LLM_PROVIDER=$(prompt_with_default "LLM Provider (openai/anthropic)" "openai" "DEFAULT_LLM_PROVIDER")
CFG_LLM_MODEL=$(prompt_with_default "LLM Model" "gpt-4o" "DEFAULT_LLM_MODEL")
CFG_LLM_API_KEY=$(prompt_secret "LLM API Key" "your_api_key" "DEFAULT_LLM_API_KEY")
CFG_LLM_BASE_URL=$(prompt_with_default "LLM Base URL (可选，留空使用默认)" "" "DEFAULT_LLM_BASE_URL")

# --- Access Key ---
echo ""
info "认证配置"
# 生成随机 JWT Secret
DEFAULT_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "change-me-$(date +%s)")
CFG_ACCESS_KEY=$(prompt_secret "Access Key (管理员登录密码)" "agent-publisher-2024" "ACCESS_KEY")
CFG_JWT_SECRET="${JWT_SECRET:-$DEFAULT_JWT_SECRET}"

# --- Admin Email ---
echo ""
CFG_ADMIN_EMAILS=$(prompt_with_default "管理员邮箱 (多个用逗号分隔)" "admin@example.com" "ADMIN_EMAILS")
CFG_EMAIL_WHITELIST=$(prompt_with_default "邮箱白名单 (多个用逗号分隔，可选)" "" "EMAIL_WHITELIST")

# --- Server Host ---
echo ""
info "公网访问配置"
CFG_SERVER_HOST=$(prompt_with_default "服务器公网域名或IP (用于微信白名单指引，留空自动检测)" "" "SERVER_HOST")

# --- 生成 .env ---
info "生成 .env 配置文件..."

cat > "$INSTALL_DIR/.env" <<ENVEOF
# Agent Publisher — 由 install.sh 自动生成 $(date '+%Y-%m-%d %H:%M:%S')

# Database
DATABASE_URL=$CFG_DB_URL

# Tencent Cloud (Hunyuan Image Generation)
TENCENT_SECRET_ID=your_secret_id
TENCENT_SECRET_KEY=your_secret_key

# Default LLM
DEFAULT_LLM_PROVIDER=$CFG_LLM_PROVIDER
DEFAULT_LLM_MODEL=$CFG_LLM_MODEL
DEFAULT_LLM_API_KEY=$CFG_LLM_API_KEY
DEFAULT_LLM_BASE_URL=$CFG_LLM_BASE_URL

# Authentication
ACCESS_KEY=$CFG_ACCESS_KEY
JWT_SECRET=$CFG_JWT_SECRET

# Server
HOST=$CFG_HOST
PORT=$CFG_PORT
DEBUG=false

# Public-facing host (domain or IP, for WeChat whitelist guide)
SERVER_HOST=$CFG_SERVER_HOST

# User Authentication
EMAIL_WHITELIST=$CFG_EMAIL_WHITELIST
ADMIN_EMAILS=$CFG_ADMIN_EMAILS
ENVEOF

success ".env 文件已生成"

# ============================================================================
# 步骤 3: 安装 Python 依赖
# ============================================================================
step "步骤 3/6: 安装 Python 依赖"
info "运行 uv sync ..."

cd "$INSTALL_DIR"
if uv sync; then
    success "Python 依赖安装完成"
else
    error "Python 依赖安装失败"
    warn "请检查 pyproject.toml 和网络连接，然后重试: cd $INSTALL_DIR && uv sync"
    exit 1
fi

# 以 editable 模式安装当前包（uv sync 不会自动注册包到 Python 路径）
info "运行 uv pip install -e . ..."
if uv pip install -e .; then
    success "agent_publisher 包已注册"
else
    warning "editable 安装失败，尝试继续..."
fi

# ============================================================================
# 步骤 4: 构建前端（可跳过）
# ============================================================================
step "步骤 4/6: 构建前端"

if [[ "$HAS_NODE" == true ]]; then
    info "安装前端依赖并构建..."

    cd "$INSTALL_DIR/web"
    if npm install; then
        success "前端依赖安装完成"
    else
        error "npm install 失败"
        warn "请检查 Node.js 版本和网络连接"
        exit 1
    fi

    if npm run build; then
        success "前端构建完成"
    else
        error "前端构建失败"
        warn "请查看上方的错误信息，修复后重新运行 install.sh"
        exit 1
    fi
    cd "$INSTALL_DIR"
elif [[ -f "$INSTALL_DIR/agent_publisher/static/index.html" ]]; then
    info "未检测到 Node.js / npm，使用 git 仓库中预构建的前端资源"
    success "前端静态文件已就绪: agent_publisher/static/"
else
    error "未检测到 Node.js 且 git 仓库中无预构建前端资源"
    warn "请安装 Node.js >= 18 后重试，或确保 agent_publisher/static/ 目录存在"
    exit 1
fi

# ============================================================================
# 步骤 4.5: 安装 Remotion 视频渲染依赖 (可选)
# ============================================================================
step "安装 Remotion 依赖"

REMOTION_DIR="$INSTALL_DIR/agent_publisher/extensions/video/remotion"
if [[ "$HAS_NODE" == true && -f "$REMOTION_DIR/package.json" ]]; then
    info "安装 Remotion 依赖..."
    cd "$REMOTION_DIR"
    if npm install; then
        success "Remotion 依赖安装完成"
    else
        warn "Remotion npm install 失败，视频渲染功能将不可用"
    fi
    cd "$INSTALL_DIR"
elif [[ ! -f "$REMOTION_DIR/package.json" ]]; then
    warn "未找到 Remotion package.json，跳过安装"
else
    warn "无 Node.js — 跳过 Remotion 依赖安装（视频渲染功能不可用）"
fi

# Copy guide images into static directory
if [[ -d "$INSTALL_DIR/docs/images" ]]; then
    mkdir -p "$INSTALL_DIR/agent_publisher/static/guide-images"
    cp -f "$INSTALL_DIR/docs/images/"*.png "$INSTALL_DIR/agent_publisher/static/guide-images/" 2>/dev/null || true
    success "引导图片已同步到 static/guide-images/"
fi

# ============================================================================
# 步骤 5: 生成并安装 systemd 服务
# ============================================================================
step "步骤 5/6: 配置 systemd 服务"

CURRENT_USER="${SUDO_USER:-$(whoami)}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TEMPLATE_FILE="$INSTALL_DIR/agent-publisher.service.template"

if [[ ! -f "$TEMPLATE_FILE" ]]; then
    error "找不到服务模板文件: $TEMPLATE_FILE"
    exit 1
fi

info "生成 systemd 服务文件..."
info "  用户: $CURRENT_USER"
info "  目录: $INSTALL_DIR"
info "  地址: $CFG_HOST:$CFG_PORT"

# 替换模板中的占位符
SERVICE_CONTENT=$(sed \
    -e "s|{INSTALL_DIR}|$INSTALL_DIR|g" \
    -e "s|{USER}|$CURRENT_USER|g" \
    -e "s|{HOST}|$CFG_HOST|g" \
    -e "s|{PORT}|$CFG_PORT|g" \
    "$TEMPLATE_FILE")

# 需要 root 权限写入 /etc/systemd/system/
if [[ $EUID -eq 0 ]]; then
    echo "$SERVICE_CONTENT" > "$SERVICE_FILE"
    systemctl daemon-reload
    success "systemd 服务文件已安装: $SERVICE_FILE"
else
    warn "需要 sudo 权限安装 systemd 服务文件"
    echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null
    sudo systemctl daemon-reload
    success "systemd 服务文件已安装: $SERVICE_FILE"
fi

# ============================================================================
# 步骤 6: 启动服务
# ============================================================================
step "步骤 6/6: 启动服务"

enable_and_start() {
    local cmd_prefix=""
    [[ $EUID -ne 0 ]] && cmd_prefix="sudo"

    info "启用开机自启..."
    $cmd_prefix systemctl enable "$SERVICE_NAME"

    info "启动服务..."
    $cmd_prefix systemctl start "$SERVICE_NAME"

    # 等待几秒让服务启动
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "服务启动成功！"
        return 0
    else
        error "服务启动失败"
        warn "查看日志: journalctl -u $SERVICE_NAME -n 50 --no-pager"
        $cmd_prefix systemctl status "$SERVICE_NAME" --no-pager || true
        return 1
    fi
}

enable_and_start

# ============================================================================
# 完成提示
# ============================================================================
echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║        ✅ 安装完成！                          ║${NC}"
echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}访问地址${NC}:  http://localhost:${CFG_PORT}"
echo -e "  ${CYAN}管理员登录${NC}: 使用 Access Key 登录"
echo ""
echo -e "  ${BOLD}常用命令:${NC}"
echo -e "    查看状态:    systemctl status ${SERVICE_NAME}"
echo -e "    查看日志:    journalctl -u ${SERVICE_NAME} -f"
echo -e "    重启服务:    systemctl restart ${SERVICE_NAME}"
echo -e "    停止服务:    systemctl stop ${SERVICE_NAME}"
echo -e "    快速更新:    bash ${INSTALL_DIR}/update.sh"
echo ""
echo -e "  ${YELLOW}下一步:${NC}"
echo -e "    1. 打开 http://localhost:${CFG_PORT} 登录管理后台"
echo -e "    2. 添加微信公众号账号"
echo -e "    3. 创建 Agent 并配置 RSS 源"
echo -e "    4. 开始自动生成和发布内容"
echo ""
