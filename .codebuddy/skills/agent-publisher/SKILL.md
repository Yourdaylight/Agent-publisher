---
name: agent-publisher
description: Manage WeChat Official Accounts and AI content agents via Agent Publisher. Authenticate with your email, bind accounts, create content agents, generate articles, and publish to WeChat draft box.
metadata:
  {
    "openclaw":
      {
        "emoji": "📢",
        "requires": { "bins": ["uv", "curl"] },
        "primaryEnv": "AP_EMAIL",
      },
  }
---

# Agent Publisher — WeChat Content Automation Skill

Manage WeChat Official Accounts and AI-powered content agents. Authenticate with your whitelisted email, bind accounts, create agents, generate articles, and publish to WeChat draft box — all through a single CLI script.

## Prerequisites

- **Agent Publisher backend** running (default: `http://<your-server-ip>:9099`)
- Your email must be whitelisted on the backend
- `uv` installed (for running the bundled Python script)

## Quick Start

The user provides two pieces of info:
1. **Email** — their whitelisted email address
2. **Backend URL** — (optional, defaults to `http://<your-server-ip>:9099`)

### Step 1: Authenticate

```bash
uv run {baseDir}/scripts/agent_publisher.py --url "$AP_URL" auth --email "user@example.com"
```

This saves a token to `~/.agent-publisher-token`. All subsequent commands auto-use this token.

### Step 2: Check identity

```bash
uv run {baseDir}/scripts/agent_publisher.py whoami
```

---

## All Commands

Every command below uses the saved token automatically. Add `--url <URL>` if the backend is not the default.

### Account Management

**List your WeChat accounts:**

```bash
uv run {baseDir}/scripts/agent_publisher.py accounts
```

**Bind a new WeChat Official Account:**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-account --name "My Account" --appid "wx1234567890" --appsecret "secret_here"
```

**List ALL accounts (admin only):**

```bash
uv run {baseDir}/scripts/agent_publisher.py accounts-all
```

### Agent Management

**List your content agents:**

```bash
uv run {baseDir}/scripts/agent_publisher.py agents
```

**Create a content agent:**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-agent \
  --name "Tech Observer" \
  --topic "AI and Technology" \
  --account-id 1 \
  --cron "0 8 * * *" \
  --llm-model "Kimi-K2.5"
```

Optional flags:
- `--description "Agent description"`
- `--rss "TechCrunch=https://feeds.feedburner.com/TechCrunch"` (repeatable)
- `--llm-provider openai`
- `--image-style "Modern minimalist"`

### Article Generation

**Trigger generation for an agent:**

```bash
uv run {baseDir}/scripts/agent_publisher.py generate 1
```

**Trigger and wait for completion:**

```bash
uv run {baseDir}/scripts/agent_publisher.py generate 1 --wait
```

**Check task status:**

```bash
uv run {baseDir}/scripts/agent_publisher.py task 42
```

### Article Management

**List articles:**

```bash
uv run {baseDir}/scripts/agent_publisher.py articles
```

**Filter by status:**

```bash
uv run {baseDir}/scripts/agent_publisher.py articles --status draft
```

**Get article detail:**

```bash
uv run {baseDir}/scripts/agent_publisher.py article 1
```

### Publishing

**Publish a single article to WeChat draft box:**

```bash
uv run {baseDir}/scripts/agent_publisher.py publish 1
```

**Publish to specific target accounts (multi-account):**

```bash
uv run {baseDir}/scripts/agent_publisher.py publish 1 --account-id 2 --account-id 3
```

**Sync article edits to specific accounts:**

```bash
uv run {baseDir}/scripts/agent_publisher.py sync-article 1 --account-id 2
```

**Batch publish articles (admin only):**

```bash
uv run {baseDir}/scripts/agent_publisher.py batch-publish 1 2 3
```

**Batch publish to specific accounts (admin only):**

```bash
uv run {baseDir}/scripts/agent_publisher.py batch-publish 1 2 3 --account-id 4 --account-id 5
```

**Enable test mode for detailed JSON output:**

```bash
uv run {baseDir}/scripts/agent_publisher.py publish 1 --account-id 2 --test-mode
uv run {baseDir}/scripts/agent_publisher.py sync-article 1 --account-id 2 --test-mode
```

The `--test-mode` flag prints the full structured JSON response, including per-account results with `status`, `wechat_media_id`, `stage`, and `error` for each target account.

---

## Environment Variables

| Variable   | Description                                          | Default                          |
|------------|------------------------------------------------------|----------------------------------|
| `AP_URL`   | Agent Publisher backend URL                          | `http://localhost:9099`          |
| `AP_EMAIL` | Email for auto-authentication                        | —                                |
| `AP_TOKEN` | Skill token (alternative to saved token file)        | —                                |

You can set `AP_URL` and `AP_EMAIL` to skip passing `--url` and `--email` every time:

```bash
export AP_URL="http://<your-server-ip>:9099"
export AP_EMAIL="user@example.com"
uv run {baseDir}/scripts/agent_publisher.py auth
```

## Typical Workflow

1. **Auth** → `auth --email "me@company.com"`
2. **Bind account** → `create-account --name "My GZH" --appid wx123 --appsecret sec456`
3. **Create agent** → `create-agent --name "Daily Tech" --topic "AI" --account-id 1 --default-style tech`
4. **Generate** → `generate 1 --wait`
5. **Review** → `articles` then `article <id>`
6. **Publish** → `publish <id>` (or `publish <id> --account-id 1 --account-id 2` for multi-account)

### Multi-Account Testing Workflow

1. **Auth** → `auth --email "tester@company.com"`
2. **Check accounts** → `accounts` to see available account IDs
3. **Publish to remote with explicit accounts** → `publish <id> --account-id 2 --account-id 3 --test-mode`
4. **Review results** → Test mode prints full structured JSON including per-account status, media IDs, and errors
5. **Sync edits** → `sync-article <id> --account-id 2 --test-mode`

This workflow allows testing against a remote environment by explicitly specifying target accounts and enabling test mode output, without modifying any database bindings.

### Style & Variant Workflow

1. **Browse styles** → `list-styles`
2. **Bind style to agent** → `update-agent 1 --default-style tech`
3. **Edit a style prompt** → `edit-style tech --prompt "你是一位科技编辑..."`
4. **Create custom style** → `create-style humor --name "幽默风" --prompt "你是一位段子手..."`
5. **Generate variants** → `generate-variants 42 --agents 1,2,3 --styles tech,uncle,clickbait --wait`
6. **Check variants** → `variants 42`

---

## All Commands Reference

### Style Preset Management

**List all style presets (built-in + custom):**

```bash
uv run {baseDir}/scripts/agent_publisher.py list-styles
uv run {baseDir}/scripts/agent_publisher.py list-styles --full  # show full prompt content
```

**Edit a style preset's name/description/prompt:**

```bash
uv run {baseDir}/scripts/agent_publisher.py edit-style tech --prompt "新的提示词内容"
uv run {baseDir}/scripts/agent_publisher.py edit-style tech --name "新名称" --description "新描述"
uv run {baseDir}/scripts/agent_publisher.py edit-style tech --prompt-file /path/to/prompt.txt
```

**Create a custom style preset:**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-style humor --name "幽默风" --prompt "你是一位段子手..."
uv run {baseDir}/scripts/agent_publisher.py create-style humor --name "幽默风" --prompt-file /path/to/prompt.txt
```

**Delete a custom style preset:**

```bash
uv run {baseDir}/scripts/agent_publisher.py delete-style humor
```

### Agent Configuration (incl. Style Binding)

**Update agent config and bind a default style:**

```bash
uv run {baseDir}/scripts/agent_publisher.py update-agent 1 --default-style tech
uv run {baseDir}/scripts/agent_publisher.py update-agent 1 --default-style ""   # clear binding
uv run {baseDir}/scripts/agent_publisher.py update-agent 1 --name "New Name" --topic "New Topic" --cron "0 10 * * *"
```

**Create agent with default style binding:**

```bash
uv run {baseDir}/scripts/agent_publisher.py create-agent \
  --name "Tech Observer" \
  --topic "AI and Technology" \
  --account-id 1 \
  --default-style tech
```

### Variant Article Generation

**Generate variant articles from a source article:**

```bash
uv run {baseDir}/scripts/agent_publisher.py generate-variants 42 --agents 1,2,3 --styles tech,uncle,clickbait
uv run {baseDir}/scripts/agent_publisher.py generate-variants 42 --agents 1,2,3 --styles tech,uncle --wait
```

**Check variant generation task status:**

```bash
uv run {baseDir}/scripts/agent_publisher.py variant-status 99
```

**List variant articles for a source article:**

```bash
uv run {baseDir}/scripts/agent_publisher.py variants 42
```

## Roles

- **Normal user**: Can manage their own accounts, agents, and articles
- **Admin**: Can see all accounts/articles and batch-publish

## Notes

- Token expires after 30 days. Re-run `auth` to refresh.
- AppSecret is sensitive — the script never prints it.
- The `--wait` flag on `generate` polls every 5 seconds for up to 5 minutes.
- If the user hasn't provided their WeChat AppID/AppSecret yet, guide them to:
  1. Log in to https://mp.weixin.qq.com
  2. Go to "设置与开发" → "基本配置"
  3. Copy the AppID and reset/copy the AppSecret
  4. Add the server IP to the IP whitelist
