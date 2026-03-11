# Agent Publisher

AI 驱动的多公众号自动内容发布平台。每个公众号绑定一个 Agent，每个 Agent 聚焦一个垂直主题，平台自动从 RSS 源抓取热点新闻，通过 LLM 生成公众号文章，使用腾讯混元生图 API 生成配图，最终批量推送到各公众号草稿箱。

## 核心特性

- 多公众号管理：一套系统管理多个公众号账号
- Agent 机制：每个 Agent 绑定一个公众号 + 一个垂直主题，独立运行
- RSS 热点抓取：自动从 RSS 源采集新闻素材
- AI 写稿：通过 Claude Code Internal CLI（claude-internal）调用 Haiku 模型生成文章
- 混元配图：腾讯混元 AI 自动生成公众号封面图
- 草稿箱推送：文章自动推送到微信公众号草稿箱，人工审核后发布
- 定时调度：APScheduler 支持按 cron 表达式定时执行
- Web + CLI 双入口：FastAPI 后台 API + Typer 命令行工具

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 后台 | FastAPI |
| CLI 命令行 | Typer |
| 数据库 | PostgreSQL + SQLAlchemy (async) + Alembic |
| 任务调度 | APScheduler |
| AI 交互 | Claude Code Internal CLI (`claude-internal`)，推荐使用 Haiku 模型 |
| 文生图 | 腾讯混元 AI (`aiart.tencentcloudapi.com`) |
| 公众号 SDK | 微信公众平台 API（自封装） |
| RSS 解析 | feedparser |

## AI 模型说明

本系统推荐使用 **Claude Code Internal CLI**（`claude-internal`）作为核心 LLM 交互方式。在用于文章生成等本系统的日常交互时，**请选择 Haiku 模型**（`claude-haiku-4-5-20251001`），兼顾速度和成本。

配置方式：

```bash
# Agent 配置中设置 LLM
agent-pub agent config <id> --llm-provider claude --llm-model claude-haiku-4-5-20251001
```

如需更高质量的输出（如重要选题、深度分析），可切换到 Sonnet 或 Opus 模型。

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd agent-publisher

# 复制环境变量配置
cp .env.example .env
# 编辑 .env，填入数据库连接、腾讯云密钥等

# 安装依赖
pip install -e .
```

### 2. 数据库初始化

```bash
# 确保 PostgreSQL 已运行，然后执行迁移
alembic upgrade head
```

### 3. 配置公众号

去微信公众平台（`mp.weixin.qq.com`）获取 AppID 和 AppSecret：

- 登录后进入「设置与开发」->「基本配置」
- 复制 AppID，重置并复制 AppSecret
- **配置 IP 白名单**：将服务器公网 IP 添加到白名单（`curl ifconfig.me` 查看当前 IP）

```bash
agent-pub account add --name "AI看公司" --appid your_appid --appsecret your_appsecret
```

### 4. 创建 Agent

```bash
agent-pub agent add \
  --name "科技前沿观察员" \
  --topic "AI与科技" \
  --account-id 1 \
  --rss "https://feeds.feedburner.com/example"

# 配置 LLM（推荐 Haiku）
agent-pub agent config 1 \
  --llm-provider claude \
  --llm-model claude-haiku-4-5-20251001 \
  --llm-api-key your_api_key
```

### 5. 生成并发布文章

```bash
# 生成文章
agent-pub article generate 1

# 预览
agent-pub article preview 1

# 发布到草稿箱
agent-pub article publish 1
```

## CLI 命令一览

```bash
# 账号管理
agent-pub account add --name "AI看公司" --appid xxx --appsecret xxx
agent-pub account list
agent-pub account remove <id>

# Agent 管理
agent-pub agent add --name "科技观察员" --topic "AI科技" --account-id 1 --rss "https://..."
agent-pub agent list
agent-pub agent config <id> --llm-provider claude --llm-model claude-haiku-4-5-20251001

# 文章操作
agent-pub article generate <agent-id>     # 单个 Agent 生成文章
agent-pub article preview <article-id>     # 预览文章
agent-pub article publish <article-id>     # 发布到草稿箱

# 批量任务
agent-pub run --all                        # 所有 Agent 执行生成
agent-pub run --agent-id 1,2,3             # 指定 Agent 执行
agent-pub task list                        # 查看任务状态
agent-pub task status <task-id>            # 查看具体任务

# RSS 管理
agent-pub rss test <url>                   # 测试 RSS 源是否可用
agent-pub rss fetch <agent-id>             # 手动抓取某 Agent 的 RSS

# 图片测试
agent-pub image generate "一只猫在看电脑"   # 测试混元文生图
```

## API 接口

启动 Web 服务后访问 `/docs` 查看 Swagger UI。

```bash
# 启动服务
uvicorn agent_publisher.main:app --host 0.0.0.0 --port 8000
```

主要接口：

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/accounts` | 添加公众号 |
| GET | `/api/accounts` | 公众号列表 |
| PUT | `/api/accounts/{id}` | 更新公众号 |
| DELETE | `/api/accounts/{id}` | 删除公众号 |
| POST | `/api/agents` | 创建 Agent |
| GET | `/api/agents` | Agent 列表 |
| PUT | `/api/agents/{id}` | 更新 Agent |
| POST | `/api/agents/{id}/generate` | 触发生成文章 |
| POST | `/api/tasks/batch` | 批量执行 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/{id}` | 任务详情 |
| GET | `/api/articles` | 文章列表 |
| GET | `/api/articles/{id}` | 文章详情 |
| POST | `/api/articles/{id}/publish` | 发布到草稿箱 |

## 项目结构

```
agent-publisher/
├── pyproject.toml
├── alembic.ini
├── web/                       # 前端工程（TDesign Vue 3 + Vite）
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/index.ts
│       ├── api/index.ts
│       ├── views/             # 页面组件
│       └── components/        # 复用组件
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── .env.example
├── agent_publisher/
│   ├── main.py              # FastAPI 入口 + 调度器启动
│   ├── cli.py               # Typer CLI
│   ├── config.py            # pydantic-settings 配置
│   ├── database.py          # 异步数据库引擎
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── models/              # SQLAlchemy ORM
│   │   ├── account.py       # 公众号账号
│   │   ├── agent.py         # Agent 配置
│   │   ├── article.py       # 生成的文章
│   │   └── task.py          # 任务记录
│   ├── services/            # 业务逻辑
│   │   ├── rss_service.py   # RSS 抓取
│   │   ├── llm_service.py   # LLM 多模型适配
│   │   ├── image_service.py # 混元文生图
│   │   ├── wechat_service.py# 微信公众号 API
│   │   ├── article_service.py# 文章生成编排
│   │   └── task_service.py  # 任务管理
│   ├── api/                 # FastAPI 路由
│   │   ├── accounts.py
│   │   ├── agents.py
│   │   ├── articles.py
│   │   ├── tasks.py
│   │   └── deps.py
│   └── schemas/             # Pydantic schemas
│       ├── account.py
│       ├── agent.py
│       ├── article.py
│       └── task.py
└── tests/
    ├── test_rss_service.py
    ├── test_llm_service.py
    ├── test_image_service.py
    └── test_wechat_service.py
```

## 前端界面

项目包含基于 TDesign Vue 3 + Vite 构建的 SPA 前端。

### 开发模式

```bash
# 安装前端依赖
cd web && npm install

# 启动前端开发服务器（自动代理 /api 到 localhost:8000）
npm run dev

# 同时启动后端
uvicorn agent_publisher.main:app --reload
```

浏览器访问 `http://localhost:3000` 即可使用前端界面。

### 生产构建

```bash
cd web && npm run build
```

构建产物输出到 `agent_publisher/static/`，启动后端后访问 `http://localhost:8000` 即可直接使用。

### 前端功能

| 页面 | 功能 |
|------|------|
| 仪表盘 | 统计卡片 + 最近文章 |
| 快速配置 | 6 步向导：注册公众号 → 获取密钥 → 配置白名单 → 添加账号 → 创建 Agent → 生成文章 |
| 公众号管理 | CRUD 管理公众号账号 |
| Agent 管理 | CRUD 管理 Agent + 触发生成 |
| 文章管理 | 筛选/预览/发布文章 |
| 任务管理 | 查看任务状态 + 批量触发 |

## 注意事项

- **IP 白名单**：微信公众号 API 只允许白名单 IP 调用，家用宽带 IP 会变动，需及时更新
- **AppSecret 安全**：请勿将 AppSecret 提交到代码仓库，使用 `.env` 文件管理
- **混元并发限制**：混元文生图默认 1 并发，多 Agent 生图时需排队处理
- **LLM 模型选择**：日常文章生成推荐 Haiku（快速、低成本），重要内容可切换 Sonnet/Opus
