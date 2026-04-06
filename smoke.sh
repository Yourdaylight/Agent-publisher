#!/usr/bin/env bash
# smoke.sh — Agent Publisher 冒烟测试
#
# 用法:
#   bash smoke.sh                    # 默认测试 localhost:9099
#   bash smoke.sh --port 9099        # 指定端口
#   bash smoke.sh --url http://1.2.3.4:9099   # 指定完整 URL
#   bash smoke.sh --access-key mykey # 指定 access key
#
# 退出码: 0=全通过, 1=有失败

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
pass() { echo -e "  ${GREEN}✅${NC}  $*"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "  ${RED}❌${NC}  $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
skip() { echo -e "  ${YELLOW}⏭${NC}  $*"; }
section() { echo -e "\n${BOLD}${CYAN}── $* ──${NC}"; }

# ── 参数 ──────────────────────────────────────────────────────────────
BASE_URL="http://localhost:9099"
ACCESS_KEY="${AP_ACCESS_KEY:-agent-publisher-2024}"
PASS_COUNT=0
FAIL_COUNT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)       BASE_URL="http://localhost:$2"; shift 2 ;;
    --url)        BASE_URL="$2"; shift 2 ;;
    --access-key) ACCESS_KEY="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════╗"
echo "║   Agent Publisher — Smoke Test               ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Target: ${BASE_URL}"
echo ""

# ── 工具函数 ───────────────────────────────────────────────────────────
# Returns HTTP status code. Always outputs 3-digit code.
http_status() { curl -s -o /dev/null -w "%{http_code}" "$@" 2>/dev/null || echo "000"; }
http_body()   { curl -sf "$@" 2>/dev/null || echo "{}"; }

check_status() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    pass "$desc (HTTP $actual)"
  else
    fail "$desc (expected $expected, got $actual)"
  fi
}

# ── Section 1: 服务健康 ────────────────────────────────────────────────
section "服务健康"

STATUS=$(http_status "${BASE_URL}/api/version")
check_status "GET /api/version" "200" "$STATUS"

STATUS=$(http_status "${BASE_URL}/")
check_status "静态首页 /" "200" "$STATUS"

# ── Section 2: 认证 ────────────────────────────────────────────────────
section "认证"

TOKEN=$(http_body -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"access_key\":\"${ACCESS_KEY}\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

if [[ -n "$TOKEN" ]]; then
  pass "管理员登录获取 Token"
else
  fail "管理员登录失败（access_key 错误或服务未就绪）"
  echo ""
  echo -e "  ${RED}无 Token，后续认证类测试将跳过${NC}"
fi

if [[ -n "$TOKEN" ]]; then
  STATUS=$(http_status "${BASE_URL}/api/auth/verify" -H "Authorization: Bearer $TOKEN")
  check_status "GET /api/auth/verify" "200" "$STATUS"

  STATUS=$(http_status "${BASE_URL}/api/auth/me" -H "Authorization: Bearer $TOKEN")
  check_status "GET /api/auth/me" "200" "$STATUS"

  STATUS=$(http_status "${BASE_URL}/api/auth/verify" -H "Authorization: Bearer bad-token")
  check_status "无效 Token → 401" "401" "$STATUS"
fi

# ── Section 3: 核心 API ─────────────────────────────────────────────────
section "核心 API"

if [[ -n "$TOKEN" ]]; then
  for path in \
    "/api/stats" \
    "/api/accounts" \
    "/api/agents" \
    "/api/articles" \
    "/api/hotspots?limit=3" \
    "/api/settings" \
    "/api/credits/balance" \
    "/api/style-presets" \
    "/api/prompts" \
    "/api/extensions" \
    "/api/invite-codes/stats"
  do
    STATUS=$(http_status "${BASE_URL}${path}" -H "Authorization: Bearer $TOKEN")
    check_status "GET ${path}" "200" "$STATUS"
  done
fi

# ── Section 4: 写入 API ─────────────────────────────────────────────────
section "写入 API (幂等检查)"

if [[ -n "$TOKEN" ]]; then
  STATUS=$(http_status -X PUT "${BASE_URL}/api/settings/proxy" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"wechat_proxy":""}')
  check_status "PUT /api/settings/proxy (清空)" "200" "$STATUS"

  STATUS=$(http_status -X PUT "${BASE_URL}/api/settings/trending" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"interval_minutes":60}')
  check_status "PUT /api/settings/trending" "200" "$STATUS"

  # 邀请码：创建一条测试码再查询删除
  CREATE_RESP=$(http_body -X POST "${BASE_URL}/api/invite-codes" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"channel":"smoke","max_uses":1,"bonus_credits":0}')
  SMOKE_CODE=$(echo "$CREATE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); lst=d.get('created',d.get('codes',[])); print(lst[0] if isinstance(lst[0] if lst else None, str) else '')" 2>/dev/null || echo "")
  if [[ -n "$SMOKE_CODE" ]]; then
    pass "POST /api/invite-codes (创建邀请码 $SMOKE_CODE)"
    # 查出 ID 再删除
    LIST_RESP=$(http_body "${BASE_URL}/api/invite-codes" -H "Authorization: Bearer $TOKEN")
    SMOKE_ID=$(echo "$LIST_RESP" | python3 -c "import sys,json; codes=json.load(sys.stdin); matched=[c['id'] for c in codes if c.get('code')=='$SMOKE_CODE']; print(matched[0] if matched else '')" 2>/dev/null || echo "")
    [[ -n "$SMOKE_ID" ]] && http_status -X DELETE "${BASE_URL}/api/invite-codes/${SMOKE_ID}" -H "Authorization: Bearer $TOKEN" >/dev/null
  else
    fail "POST /api/invite-codes (响应: ${CREATE_RESP:0:120})"
  fi
fi

# ── Section 5: 权限边界 ─────────────────────────────────────────────────
section "权限边界"

for path in "/api/stats" "/api/accounts" "/api/invite-codes"; do
  STATUS=$(http_status "${BASE_URL}${path}")
  check_status "未认证 GET ${path} → 401" "401" "$STATUS"
done

STATUS=$(http_status -X POST "${BASE_URL}/api/extensions/slideshow/generate" \
  -H "Content-Type: application/json" -d '{"article_id":1}')
check_status "未认证 POST /api/extensions/slideshow/generate → 401" "401" "$STATUS"

# ── Section 6: 前端路由 (SPA) ─────────────────────────────────────────
section "前端路由 (SPA)"

for frontend_path in "/" "/home" "/login" "/trending" "/create" "/articles"; do
  STATUS=$(http_status "${BASE_URL}${frontend_path}")
  check_status "GET ${frontend_path}" "200" "$STATUS"
done

# ── 汇总 ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════${NC}"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
if [[ $FAIL_COUNT -eq 0 ]]; then
  echo -e "${BOLD}${GREEN}  ✅ 全部通过：${PASS_COUNT}/${TOTAL}${NC}"
else
  echo -e "${BOLD}${RED}  ❌ 失败：${FAIL_COUNT}/${TOTAL}   通过：${PASS_COUNT}/${TOTAL}${NC}"
fi
echo -e "${BOLD}══════════════════════════════════════${NC}"
echo ""

exit $FAIL_COUNT
