#!/usr/bin/env bash
# dev.sh — 本地开发一键启动
# 用法:
#   bash dev.sh              # 构建前端 + 启动后端（后端托管前端静态文件）
#   bash dev.sh --no-build   # 跳过构建，只启动后端
# 按 Ctrl+C 停止

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PORT=9099
DO_BUILD=true

for arg in "$@"; do
  case "$arg" in
    --no-build) DO_BUILD=false ;;
    -h|--help)
      echo "用法: bash dev.sh [--no-build]"
      exit 0 ;;
  esac
done

# 1. 停旧进程
echo "[1/2] 停止旧进程..."
pids=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null || true)
if [[ -n "$pids" ]]; then
  echo "$pids" | xargs kill -9 2>/dev/null || true
fi
sleep 1

# 2. 构建前端（产物直接输出到 agent_publisher/static/）
if [[ "$DO_BUILD" == true ]]; then
  echo "[2/2] 构建前端..."
  cd "$REPO/web" && npm run build
  echo "      构建完成"
else
  echo "[2/2] 跳过构建"
fi

# 启动后端（前端由后端 StaticFiles 托管）
echo ""
echo "=========================================="
echo "  http://localhost:${PORT}"
echo "  按 Ctrl+C 停止"
echo "=========================================="
echo ""

cd "$REPO"
exec uv run uvicorn agent_publisher.main:app --host 0.0.0.0 --port $PORT
