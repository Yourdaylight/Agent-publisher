---
name: agent-publisher
description: "微信公众号发布工具：本地写好文章 → 上传到平台 → 排版美化 → 一键发布到微信草稿箱。"
metadata:
  {
    "openclaw":
      {
        "emoji": "�",
        "requires": { "bins": ["uv"] },
        "primaryEnv": "AP_EMAIL",
      },
  }
---

# Agent Publisher — 微信公众号发布工具

本地编辑好内容，通过 CLI 上传、美化排版、发布到微信草稿箱。

## 前置条件

- Agent Publisher 后端运行中（默认 `http://localhost:9099`）
- 邮箱已加入白名单
- 已安装 `uv`

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AP_URL` | 后端地址 | `http://localhost:9099` |
| `AP_EMAIL` | 认证邮箱 | — |

---

## 核心工作流

### 1. 认证

```bash
uv run {baseDir}/scripts/agent_publisher.py auth --email "you@example.com"
```

### 2. 绑定公众号（首次使用）

```bash
uv run {baseDir}/scripts/agent_publisher.py create-account --name "我的公众号" --appid wx123 --appsecret sec456
```

获取 AppID/AppSecret：登录 https://mp.weixin.qq.com → 设置与开发 → 基本配置。

### 3. 上传文章

**从 Markdown 文件创建（推荐，自动通过 wenyan 引擎转为精美排版）：**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-article --agent-id 1 --title "文章标题" --content-file ./article.md
```

> **强烈推荐使用 Markdown**：Markdown 文件会通过 wenyan 渲染引擎自动转为精美排版，
> 并支持 `beautify` 主题切换和 `ai-beautify` 增强美化。HTML 文件无法使用这些功能。

**从 HTML 文件创建（不推荐，仅向后兼容）：**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-article --agent-id 1 --title "文章标题" --content-file ./article.html --force-html
```

**设置封面图（素材库 ID 或外部 URL）：**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-article --agent-id 1 --title "标题" --content-file ./article.md --cover media:5
uv run {baseDir}/scripts/agent_publisher.py create-article --agent-id 1 --title "标题" --content-file ./article.md --cover "https://example.com/cover.jpg"
```

### 4. 排版美化

**wenyan 主题美化（8 个内置主题，纯本地渲染）：**

```bash
uv run {baseDir}/scripts/agent_publisher.py beautify <article_id>
uv run {baseDir}/scripts/agent_publisher.py beautify <article_id> --theme orangeheart
```

可选主题：`default`、`orangeheart`、`rainbow`、`lapis`、`pie`、`maize`、`purple`、`phycat`

**AI 增强美化（基于 wenyan 排版，LLM 做装饰增强）：**

```bash
uv run {baseDir}/scripts/agent_publisher.py ai-beautify <article_id>
uv run {baseDir}/scripts/agent_publisher.py ai-beautify <article_id> --style-hint "科技极简风，大量留白"
uv run {baseDir}/scripts/agent_publisher.py ai-beautify <article_id> --theme orangeheart --style-hint "暖色调"
```

> 推荐工作流：先 `beautify` 选主题 → 再 `ai-beautify` 做精细调整。
> `ai-beautify` 会自动先用 wenyan 渲染基底，再让 AI 在此基础上增强，不会从零重建排版。

### 5. 发布到微信

```bash
uv run {baseDir}/scripts/agent_publisher.py publish <article_id>
```

发布后文章进入微信草稿箱，在微信后台确认群发。

**编辑后重新同步到草稿箱：**

```bash
uv run {baseDir}/scripts/agent_publisher.py edit-article <article_id> --content-file ./updated.md
uv run {baseDir}/scripts/agent_publisher.py beautify <article_id> --theme lapis
uv run {baseDir}/scripts/agent_publisher.py sync-article <article_id>
```

---

## 命令速查

以下省略前缀 `uv run {baseDir}/scripts/agent_publisher.py`。

### 认证

| 命令 | 说明 |
|------|------|
| `auth --email <email>` | 邮箱认证 |
| `whoami` | 查看当前身份 |

### 公众号

| 命令 | 说明 |
|------|------|
| `accounts` | 列出我的公众号 |
| `create-account --name <名称> --appid <ID> --appsecret <Secret>` | 绑定公众号 |

### 文章（核心）

| 命令 | 说明 |
|------|------|
| `create-article --agent-id <ID> --title <标题> --content-file <file>` | 上传文章（推荐 .md） |
| `edit-article <ID> --title/--content-file/--cover` | 编辑文章 |
| `article <ID>` | 查看文章详情 |
| `articles [--status draft]` | 列出文章 |

### 美化排版

| 命令 | 说明 |
|------|------|
| `beautify <ID> [--theme orangeheart]` | wenyan 主题排版 |
| `ai-beautify <ID> [--theme lapis] [--style-hint "风格描述"]` | AI 增强美化（基于 wenyan 基底） |

### 发布

| 命令 | 说明 |
|------|------|
| `publish <article_id>` | 发布到微信草稿箱 |
| `sync-article <article_id>` | 同步编辑到草稿箱 |
| `batch-publish <id1> <id2> ...` | 批量发布（管理员） |

### 素材库

| 命令 | 说明 |
|------|------|
| `media` | 列出素材 |
| `upload-media <文件路径>` | 上传图片 |

### 数据

| 命令 | 说明 |
|------|------|
| `followers <account_id>` | 粉丝趋势 |
| `article-stats <account_id>` | 阅读数据 |

---

## 注意事项

- Token 有效期 30 天，过期重新 `auth`
- `create-article` 需要 `--agent-id`，用 `agents` 命令查看可用的 Agent ID
- **文章内容建议使用 Markdown 格式**，wenyan 会自动渲染为微信适配的精美 HTML
- HTML 文件虽然支持，但无法使用 beautify 主题美化和 AI 增强美化
- 封面图支持 `media:<id>`（素材库 ID）或 `http(s)://` URL
- AppSecret 敏感信息不会被打印
