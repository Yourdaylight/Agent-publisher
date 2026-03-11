# 需求文档

## 引言

当前 Agent Publisher 系统存在三个核心体验问题：

1. **任务执行不可见**：用户在 Agent 列表点击"生成"后，文章管理页面看不到正在执行中的任务，只能等到文章完全生成后才能看到结果。生成接口 (`POST /api/agents/{id}/generate`) 是同步阻塞的——前端等待直到整个 RSS→LLM→生图→存库 流程全部完成才返回，期间用户无法感知进度。
2. **AI 思考过程不透明**：用户完全看不到 AI 是如何工作的——抓了哪些新闻、LLM 正在生成什么内容、图片生成进展如何。当前 Task 模型只记录最终结果（`result` JSON），没有中间步骤日志。
3. **默认 LLM 配置不通用**：当前默认 LLM provider 是 `claude`（使用 Anthropic 原生 SDK），用户希望默认使用 OpenAI 兼容格式，这样可以对接更多 LLM 服务（如本地部署的模型、各类兼容 OpenAI API 的服务）。

本需求旨在解决以上问题，提升系统可用性和用户体验。

---

## 需求

### 需求 1：任务异步执行与进度可见

**用户故事：** 作为一名内容运营人员，我希望点击"生成"后能立即看到任务状态并实时跟踪进度，以便了解文章生成是否正常、何时完成。

#### 验收标准

1. WHEN 用户在 Agent 列表点击"生成"按钮 THEN 系统 SHALL 立即返回任务 ID 和初始状态（pending），并在后台异步执行生成流程，前端不再阻塞等待。
2. WHEN 任务开始执行 THEN 系统 SHALL 将任务状态更新为 `running`，并记录 `started_at` 时间戳。
3. WHEN 任务执行过程中到达每个关键步骤（RSS 抓取、LLM 生成、图片生成、文章保存）THEN 系统 SHALL 更新任务的步骤日志（`steps` 字段），记录当前步骤名称、状态和时间。
4. WHEN 任务执行成功 THEN 系统 SHALL 将状态更新为 `success`，并在 `result` 中记录生成的文章 ID。
5. WHEN 任务执行失败 THEN 系统 SHALL 将状态更新为 `failed`，并在 `result` 中记录错误信息。
6. WHEN 用户在文章管理页面访问时 THEN 系统 SHALL 展示当前正在执行中的生成任务（以"生成中"状态卡片或表格行的形式），让用户知道有文章正在生成。
7. WHEN 任务列表页面打开且存在 `running` 状态的任务 THEN 系统 SHALL 自动轮询（或 SSE 推送）任务状态，实时更新进度展示。

---

### 需求 2：AI 思考过程可视化

**用户故事：** 作为一名内容运营人员，我希望能看到 AI 生成文章时的完整思考过程（抓了什么新闻、正在写什么内容），以便对 AI 的工作质量有直观感知，并在出问题时快速定位原因。

#### 验收标准

1. WHEN 任务执行到 RSS 抓取步骤 THEN 系统 SHALL 记录抓取到的新闻条目摘要（标题列表），并将其存储到任务的步骤日志中。
2. WHEN 任务执行到 LLM 生成步骤 THEN 系统 SHALL 通过流式输出（streaming）方式接收 LLM 响应，并将流式内容实时推送给前端。
3. WHEN 用户查看某个任务详情 THEN 系统 SHALL 展示该任务的完整执行步骤时间线，包括：每个步骤的名称、开始/结束时间、状态（进行中/成功/失败）、以及关键输出摘要。
4. WHEN 用户查看正在进行中的 LLM 生成步骤 THEN 系统 SHALL 实时展示 AI 正在生成的文本内容（类似 ChatGPT 的逐字输出效果）。
5. IF LLM 调用失败 THEN 系统 SHALL 在步骤日志中记录完整的错误信息，包括 provider、model、错误类型和错误消息。
6. WHEN 任务执行到图片生成步骤 THEN 系统 SHALL 记录图片生成的 prompt 和结果状态到步骤日志中。

---

### 需求 3：默认 LLM 改为 OpenAI 兼容格式

**用户故事：** 作为一名系统管理员，我希望默认 LLM 使用 OpenAI 兼容的 API 格式，以便对接更多 LLM 服务（本地部署模型、各类兼容服务），而不需要每次都手动配置。

#### 验收标准

1. WHEN 系统初始化默认配置 THEN 系统 SHALL 将 `default_llm_provider` 默认值设为 `openai`，`default_llm_model` 默认值设为通用模型名（如 `gpt-4o`）。
2. WHEN Agent 模型中 `llm_provider` 未指定 THEN 系统 SHALL 使用 `openai` 作为默认 provider。
3. WHEN 使用 OpenAI 兼容格式调用 LLM THEN 系统 SHALL 支持通过配置 `base_url` 来指定自定义的 API 端点地址（例如本地部署的 LLM 服务地址）。
4. WHEN 用户在 Agent 配置中选择 LLM provider THEN 系统 SHALL 在前端表单中将 `openai` 作为默认选项展示。
5. IF 用户配置了自定义 `base_url` THEN `OpenAIAdapter` SHALL 使用该 `base_url` 进行 API 调用，而非默认的 OpenAI 官方地址。
6. WHEN 新建 Agent 且未手动指定 LLM 配置 THEN 系统 SHALL 自动填充全局默认的 OpenAI 兼容配置（provider、model、base_url、api_key）。

---

## 技术约束与边界情况

### 后端
- 异步任务执行应使用 `asyncio.create_task()` 或 `BackgroundTasks` 将生成流程从 API 请求中解耦。
- Task 模型需要新增 `steps` 字段（JSON 类型）用于存储步骤日志。
- LLM 流式输出使用 SSE（Server-Sent Events）推送到前端。
- 数据库迁移需兼容 SQLite 和 PostgreSQL。
- OpenAI 兼容 adapter 需要支持 `base_url` 参数。

### 前端
- 文章管理页面需增加"生成中"任务的展示区域。
- 任务详情需要新增步骤时间线组件。
- LLM 流式内容展示需要接入 SSE/EventSource。
- 轮询间隔建议 3-5 秒，当没有 running 任务时停止轮询。

### 成功标准
- 用户点击"生成"后 1 秒内看到任务已创建的反馈。
- 文章管理页面能看到所有正在生成中的任务。
- 任务详情页面能看到完整的步骤执行记录。
- 默认新建的 Agent 使用 OpenAI 兼容配置，无需手动修改。
