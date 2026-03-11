# 实施计划

- [ ] 1. 默认 LLM 配置改为 OpenAI 兼容格式
  - 修改 `agent_publisher/config.py`：将 `default_llm_provider` 默认值从 `"claude"` 改为 `"openai"`，`default_llm_model` 从 `"claude-sonnet-4-6"` 改为 `"gpt-4o"`；新增 `default_llm_base_url` 字段（默认空字符串）
  - 修改 `agent_publisher/models/agent.py`：将 `llm_provider` 默认值改为 `"openai"`，`llm_model` 默认值改为 `"gpt-4o"`；新增 `llm_base_url` 字段（String(500), default=""）
  - 修改 `agent_publisher/schemas/agent.py`：`AgentCreate` 和 `AgentUpdate` 中对应默认值同步修改，新增 `llm_base_url` 字段；`AgentOut` 增加 `llm_base_url` 输出
  - 修改 `agent_publisher/services/llm_service.py`：`LLMAdapter.generate()` 方法签名新增 `base_url: str = ""` 参数；`OpenAIAdapter.generate()` 使用传入的 `base_url` 构造 `AsyncOpenAI(api_key=api_key, base_url=base_url or None)`；`LLMService.generate()` 静态方法新增 `base_url` 参数并透传给 adapter
  - 修改 `agent_publisher/services/article_service.py`：`generate_article()` 中调用 `self.llm.generate()` 时传入 `agent.llm_base_url`
  - 修改 `.env.example`：将 `DEFAULT_LLM_PROVIDER` 改为 `openai`，`DEFAULT_LLM_MODEL` 改为 `gpt-4o`，新增 `DEFAULT_LLM_BASE_URL=`
  - 修改 `web/src/components/AgentForm.vue`：LLM provider 选择器默认值改为 `openai`，新增 `base_url` 输入框
  - _需求：3.1、3.2、3.3、3.4、3.5、3.6_

- [ ] 2. Task 模型新增 `steps` 字段
  - 修改 `agent_publisher/models/task.py`：新增 `steps: Mapped[list | None] = mapped_column(JSON, default=list)` 字段，用于存储步骤日志数组（每个元素包含 `name`, `status`, `started_at`, `finished_at`, `output`）
  - 修改 `agent_publisher/schemas/task.py`：`TaskOut` 新增 `steps: list | None` 字段
  - 因为项目使用 SQLite 开发模式（`lifespan` 中 `create_all` 自动建表），兼容处理：如果已有数据库文件，删除后重新启动即可自动重建
  - _需求：1.3、2.1、2.3_

- [ ] 3. 后端生成接口改为异步执行
  - 修改 `agent_publisher/api/agents.py`：`generate_for_agent` 接口改为立即创建 Task（状态 pending），使用 `asyncio.create_task()` 在后台执行生成流程，接口立即返回 `{"task_id": task.id, "status": "pending"}`
  - 修改 `agent_publisher/services/task_service.py`：将 `run_generate` 方法拆分——提取异步执行逻辑为 `_execute_generate(task_id, agent_id)` 方法，该方法内部创建独立的数据库 session（使用 `async_session_factory`），执行完整的生成流程并更新 task 状态；原 `run_generate` 方法改为仅创建 task 并返回，不再 await 执行流程
  - 修改 `agent_publisher/api/tasks.py`：`batch_run` 接口同样改为异步执行模式，立即返回任务 ID 列表
  - _需求：1.1、1.2、1.4、1.5_

- [ ] 4. 任务执行过程中记录步骤日志
  - 修改 `agent_publisher/services/task_service.py`：在 `_execute_generate` 方法中，每执行到一个关键步骤（RSS 抓取、LLM 生成、图片生成、文章保存）时，更新 task 的 `steps` 数组，记录步骤名称、开始时间、结束时间、状态和关键输出摘要
  - 修改 `agent_publisher/services/article_service.py`：`generate_article` 方法新增可选的 `step_callback` 回调参数（`Callable` 类型），在 RSS 抓取完成后回调传递新闻标题列表，在 LLM 生成完成后回调传递生成结果摘要，在图片生成完成后回调传递 prompt 和结果状态
  - 每个步骤完成后立即 `await session.commit()` 将步骤日志持久化，保证即使后续步骤失败，已完成的步骤日志不丢失
  - _需求：1.3、2.1、2.5、2.6_

- [ ] 5. 新增 SSE 接口推送任务实时进度
  - 在 `agent_publisher/api/tasks.py` 新增 `GET /api/tasks/{task_id}/stream` SSE 接口，使用 FastAPI 的 `StreamingResponse`（content-type: text/event-stream）
  - SSE 接口逻辑：轮询数据库中 task 的 `steps` 和 `status` 字段，每 2 秒推送一次当前任务状态和最新步骤信息；当 task 状态变为 `success` 或 `failed` 时，推送最终结果并关闭连接
  - 在 `agent_publisher/main.py` 中确认 tasks_router 已注册（当前已注册，无需额外修改）
  - _需求：1.7、2.2、2.4_

- [ ] 6. LLM 流式输出支持
  - 修改 `agent_publisher/services/llm_service.py`：`LLMAdapter` 新增 `async def generate_stream(...)` 方法，返回 `AsyncGenerator[str, None]`；`OpenAIAdapter.generate_stream()` 使用 `stream=True` 参数调用 OpenAI API，逐 chunk yield 内容；`ClaudeAdapter.generate_stream()` 使用 Anthropic SDK 的 streaming 模式
  - 修改 `agent_publisher/services/article_service.py`：新增 `generate_article_stream()` 方法，在 LLM 生成步骤使用流式输出，通过回调将每个 chunk 推送出去，同时拼接完整响应用于后续处理
  - 修改 `agent_publisher/api/tasks.py`：SSE 接口在 LLM 生成步骤期间，将流式内容以 `event: llm_chunk` 类型推送给前端
  - _需求：2.2、2.4_

- [ ] 7. 前端文章管理页面展示"生成中"任务
  - 修改 `web/src/api/index.ts`：新增 `getRunningTasks` 接口调用 `GET /api/tasks?status=running`
  - 修改 `web/src/views/Articles.vue`：页面顶部新增"生成中"任务展示区域——在 `onMounted` 中调用 `getRunningTasks` 获取正在执行的任务列表，以卡片形式展示（显示 agent 名称、当前步骤、进度状态）；设置 5 秒轮询，当存在 running 任务时自动刷新，无 running 任务时停止轮询并刷新文章列表
  - _需求：1.6、1.7_

- [ ] 8. 前端任务详情页面：步骤时间线与 AI 实时输出
  - 修改 `web/src/views/Tasks.vue`：表格行点击打开任务详情抽屉（`t-drawer`），展示任务的步骤时间线（使用 TDesign `t-steps` 或自定义时间线组件），每个步骤显示名称、时间、状态和输出摘要
  - 新增 SSE 接入逻辑：当任务状态为 `running` 时，使用 `EventSource` 连接 `/api/tasks/{id}/stream`，实时更新步骤状态；接收到 `event: llm_chunk` 时，在 LLM 生成步骤区域逐字展示 AI 正在生成的文本内容（类似 ChatGPT 效果）
  - 任务完成或失败时自动关闭 SSE 连接，展示最终结果
  - _需求：2.2、2.3、2.4、2.5_

- [ ] 9. 前端 Agent 页面优化：生成按钮交互改进
  - 修改 `web/src/views/Agents.vue`：`onGenerate` 方法中，API 返回后提示"任务已创建"并展示任务 ID，提供"查看任务"链接跳转到任务管理页面；生成按钮在请求期间显示 loading 状态
  - 修改 `web/src/components/AgentForm.vue`（如果存在）：LLM 配置区域新增 `base_url` 输入框，provider 下拉默认选中 `openai`
  - _需求：1.1、3.4、3.6_

- [ ] 10. 前端构建与后端静态文件更新
  - 在 `web/` 目录执行 `npm run build`，将构建产物输出到 `agent_publisher/static/`
  - 验证后端 `main.py` 的 SPA 托管逻辑能正确加载新构建的前端页面
  - 端到端验证：启动后端 → 访问 Web 页面 → 创建 Agent → 点击生成 → 文章管理页面看到"生成中"任务 → 任务详情看到步骤时间线和 AI 输出 → 生成完成后看到文章
  - _需求：1.1、1.6、2.3、3.4_
