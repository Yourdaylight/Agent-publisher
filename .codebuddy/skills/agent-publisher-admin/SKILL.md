---
name: agent-publisher-admin
description: "Agent Publisher 管理后台：Agent 管理、风格预设、AI 生成、多风格改写、权限管理、数据源配置。需要管理员邮箱。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🔧",
        "requires": { "bins": ["uv"] },
        "primaryEnv": "AP_EMAIL",
      },
  }
---

# Agent Publisher Admin — 管理后台

管理写作身份（Agent）、AI 生成、风格改写、权限、数据源等后台功能。

## 前置条件

- Agent Publisher 后端运行中
- 邮箱为管理员或白名单用户
- 已安装 `uv`

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AP_URL` | 后端地址 | `http://localhost:9099` |
| `AP_EMAIL` | 管理员邮箱 | — |

---

## 命令速查

以下省略前缀 `uv run {baseDir}/scripts/agent_publisher_admin.py`。

### 认证

| 命令 | 说明 |
|------|------|
| `auth --email <email>` | 管理员认证 |
| `whoami` | 查看身份 |

### Agent（写作身份）

| 命令 | 说明 |
|------|------|
| `agents` | 列出所有 Agent |
| `create-agent --name <名称> --topic <主题> --account-id <ID>` | 创建 Agent |
| `update-agent <ID> --name/--topic/--default-style/--cron` | 更新 Agent |

### AI 生成

| 命令 | 说明 |
|------|------|
| `generate <agent_id> [--wait]` | 触发 AI 文章生成 |
| `task <task_id>` | 查看任务状态 |
| `collect <agent_id>` | 采集素材（不生成文章） |

### 风格预设

| 命令 | 说明 |
|------|------|
| `list-styles [--full]` | 查看风格预设 |
| `create-style <id> --name <名称> --prompt <提示词>` | 创建自定义风格 |
| `edit-style <id> --prompt <提示词>` | 编辑风格 |
| `delete-style <id>` | 删除风格 |

### 多风格改写

| 命令 | 说明 |
|------|------|
| `generate-variants <article_id> --agents 1,2 --styles tech,humor [--wait]` | 批量改写 |
| `variants <article_id>` | 查看改写版本 |

### 权限管理

| 命令 | 说明 |
|------|------|
| `list-admins` | 查看管理员列表 |
| `add-admin <email>` | 添加管理员 |
| `remove-admin <email>` | 移除管理员 |
| `accounts-all` | 查看所有公众号 |

---

## 典型工作流

```bash
# 1. 认证
uv run {baseDir}/scripts/agent_publisher_admin.py auth --email "admin@company.com"

# 2. 创建 Agent
uv run {baseDir}/scripts/agent_publisher_admin.py create-agent --name "科技观察" --topic "AI" --account-id 1

# 3. 配置风格
uv run {baseDir}/scripts/agent_publisher_admin.py update-agent 1 --default-style tech

# 4. AI 生成
uv run {baseDir}/scripts/agent_publisher_admin.py generate 1 --wait

# 5. 批量改写
uv run {baseDir}/scripts/agent_publisher_admin.py generate-variants 42 --agents 1,2 --styles tech,humor --wait
```
