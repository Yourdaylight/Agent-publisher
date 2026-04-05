# Agent Publisher

AI 驱动的多公众号内容生产与分发平台。每个公众号绑定一个 Agent，每个 Agent 聚焦一个垂直主题，平台可以从热点与素材池中发现选题，通过 LLM 生成公众号文章，使用腾讯混元生图 API 生成配图，最终批量推送到各公众号草稿箱，并逐步扩展到演示稿与视频等多形态内容产出。

## 核心特性

- 多公众号管理：一套系统管理多个公众号账号
- Agent 机制：每个 Agent 绑定一个公众号 + 一个垂直主题，独立运行
- 热点发现：聚合热点素材，支持筛选、导出与一键创作
- 创作工作台：从热点/素材池进入统一创作台，选择 Agent、风格预设与提示词模板生成草稿
- 提示词库：沉淀可复用的 Prompt 模板，支持系统模板与自定义模板
- 在线编辑：支持 TipTap 富文本编辑、Markdown 渲染预览、HTML 精修
- 会员中心：预置套餐、订单占位与联系二维码，为后续支付接入预留产品结构
- 演示稿扩展：支持将文章延展为 HTML 演示稿，为视频化输出打基础
- 草稿箱推送：文章自动推送到微信公众号草稿箱，人工审核后发布
- 定时调度：APScheduler 支持按 cron 表达式定时执行
- Web + CLI 双入口：FastAPI 后台 API + Typer 命令行工具

## 从热点到多形态内容分发的产品故事

Agent Publisher 正在从“自动写公众号文章的工具”升级为“内容经营工作台”。

站在产品经理视角，这条故事线可以拆成 5 个连续环节：

1. **发现机会**：运营先在「热点发现」里看到今天值得跟进的话题，而不是从空白页开始。
2. **组织素材**：热点、RSS、手动上传内容都进入统一素材池，形成可复用的内容资产。
3. **快速成稿**：运营在「创作工作台」里选择 Agent、风格预设和提示词模板，把热点快速转成公众号草稿。
4. **精修发布**：运营进入「在线编辑」页，用 TipTap 富文本、Markdown 和 HTML 预览把草稿打磨成可发版本，再同步到微信草稿箱。
5. **扩展变现**：当内容资产稳定沉淀后，可以继续扩展为会员能力、模板市场、演示稿、短视频等更高客单价产品。

这意味着平台的价值不再只是“帮你写一篇文章”，而是：

- 把选题、创作、编辑、发布放到一条产品链路里
- 让内容资产（素材、模板、风格、Agent 配置）可复用、可沉淀、可复利
- 为后续的视频化、团队协作、商业化付费能力预留结构

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
| 热点发现 | 聚合热点、查看趋势、导出 CSV、一键创作 |
| 创作工作台 | 从素材池生成草稿，组合 Agent / 风格预设 / 提示词模板 |
| 公众号管理 | CRUD 管理公众号账号 |
| Agent 管理 | CRUD 管理 Agent + 触发生成 |
| 提示词库 | 管理系统模板和自定义 Prompt 模板 |
| 文章管理 | 筛选/预览/发布文章 |
| 在线编辑 | TipTap 富文本、Markdown 与 HTML 三种编辑方式 |
| 会员中心 | 展示套餐、订单占位、联系二维码 |
| 任务管理 | 查看任务状态 + 批量触发 |

## 内容视频化路线评估

当前仓库已经具备把“文章”继续扩展成“视频素材包”的基础条件，尤其是 slideshow 扩展已经提供了较完整的中间产物：

- 文章正文与 `html_content`：适合作为视频脚本与画面来源
- `slideshow` 扩展：可把文章拆成章节与页面
- `timeline.json`：已具备场景、时长、备注、章节结构等可编排信息
- 竖屏场景模板：已经有面向视频模式的 `vertical_scene.html.j2`
- `notes` 旁白字段：天然适合作为 TTS 口播输入

这意味着，**如果后续接入 Remotion 渲染层或等价的视频 skill / 服务，整体是可行的**。

建议的最小产品路径是：

1. 文章生成完成后，调用 slideshow 扩展生成章节时间线
2. 导出 `timeline.json`、场景 HTML 和封面/插图等素材
3. 接入 TTS，把 `notes` 转成音频轨
4. 用 Remotion 或独立渲染服务把时间线、字幕、配音和视觉模板合成为视频
5. 把最终视频回写为新的内容资产，进入分发链路

从产品视角看，这条路线会把 Agent Publisher 从“公众号自动化工具”进一步升级成“图文 + 演示稿 + 视频”一体化的内容操作系统。

## 注意事项

- **IP 白名单**：微信公众号 API 只允许白名单 IP 调用，家用宽带 IP 会变动，需及时更新
- **AppSecret 安全**：请勿将 AppSecret 提交到代码仓库，使用 `.env` 文件管理
- **混元并发限制**：混元文生图默认 1 并发，多 Agent 生图时需排队处理
- **LLM 模型选择**：日常文章生成推荐 Haiku（快速、低成本），重要内容可切换 Sonnet/Opus
