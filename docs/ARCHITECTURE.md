# 总体业务与系统架构（正式方案）

**版本**：v1.1 · 2026-11-04  
**状态**：架构方向和 V1 范围确定，尚无业务代码；开发过程如遇事实冲突，通过开发文档记录变更，不随意改目标。  
**参考基线**：[DeerFlow 2.0.0](https://github.com/bytedance/deer-flow/tree/v2.0.0)，commit `7e7f0410797693cf882594555ba414e0361d4c6f`。本项目自行实现，不 Fork 原项目。

## 1. 目标与边界

Mini DeerFlow 是面向单用户、本地/自托管的通用任务型 Agent，不是只会对话的 Chatbot，也不是完整的 DeerFlow 平台。用户提出多步骤任务，主智能体决定是否规划、选工具、是否委派子 Agent、何时汇总；系统维护可观察的执行记录、状态和工作文件。

**最终必须具备**：Lead Agent、结构化 Todo、Sub-Agent、工具/MCP、Skills、Workspace、上下文预算/压缩、SQLite Checkpoint、Run 状态、SSE、轻量 Web、Deep Research、文档 RAG、基础任务评测。

**刻意不做**：多用户/SSO/RBAC、企业网关、IM 多渠道、K8s、分布式运行、Agent 市场、自动升级自身、音视频生成、全能 Coding Agent、未经隔离的任意 Shell/Python。长期记忆、复杂多模型调度、Redis/MQ、浏览器自动操作属于非 V1 必需。

## 2. 三个真正要交付的业务

### 2.1 联网 Deep Research

**场景**：用户要求调研某个技术方向、比较多个方案并生成报告。

- 输入：研究问题、范围、可选输出格式和成本/任务预算。
- 流程：Lead Agent 判定复杂度 → 生成/更新 Todo → 选择搜索工具 → 获取真实链接与页面摘要 → 根据子主题委派 Research Sub-Agent → 汇总来源、冲突与不足 → 生成 Markdown 报告。
- 输出：自然语言摘要、参考来源、报告文件及子任务/工具记录。
- 合同：引用必须来自实际检索到的来源；URL 不由模型凭空编造；网页内容不可信；网络或子任务失败时不得伪称全量研究完成。
- 能力验证：一个任务能够真实调用多个工具，必要时并行委派，最终产物可打开且来源可核查。

### 2.2 多文档 RAG

**场景**：上传论文、产品手册或多份技术资料，做原文定位与跨文档分析。

- 输入：文本型 PDF、Markdown、TXT 文档和问题。
- 建库：上传 → 校验 → Docling 解析/保留页码和章节 → 分块与原文位置映射 → Embedding → Chroma 索引。
- 查询：Agent 调用 `search_knowledge` → 返回片段、文档 ID、页码/位置、得分 → 选择证据 → 回答和引用。
- 输出：可回到原始片段的答案、可选文档比较报告。
- 合同：区分原文与生成摘要；无证据时说明未知；索引与文档版本对应；更新/删除文件必须同步处理索引。
- 范围：先实现小规模、文本型 PDF，不承诺扫描 OCR/复杂图表和海量文档。

### 2.3 多步骤工作空间任务

**场景**：用户上传 CSV/Markdown，要求整理、汇总、生成报告或数据文件。

- 输入：文件、指令、允许操作的 Workspace。
- 流程：Lead 决定是否生成 Todo → 受控文件/确定性数据工具读取和加工 → 写出新 Artifact → 校验文件真实存在 → 返回下载入口。
- 输出：Markdown / CSV / JSON 文件、执行记录、错误原因。
- 安全：只在会话工作空间读写；不直接开放宿主机 Shell；覆盖与并发写入要有明确策略。

普通单轮聊天、工具问答、多轮追问，是三条业务共享的底座，不另建三套工作流。

## 3. 最终技术架构（固定）

| 层 | 技术 | 职责 |
|---|---|---|
| Web | React + TypeScript + Vite | 聊天、会话、Todo、子任务、文件、SSE 展示 |
| API | Python 3.12、FastAPI、Pydantic | HTTP/SSE、请求校验、线程/Run/文件接口 |
| Agent | LangChain + LangGraph | Lead Agent、工具循环、状态/中间件、任务协调 |
| Sub-Agent | LangGraph Agent + `asyncio` | 独立上下文，受限工具，有限并发、超时、取消 |
| Tools/MCP | LangChain Tool + `langchain-mcp-adapters` | 工具注册、MCP 接入、权限、错误封装 |
| Skills | 本地 `SKILL.md` | 发现、元信息、按需加载、工具权限约束 |
| Persistence | SQLite + LangGraph SQLite Checkpointer | 多轮图状态、Thread/Run 元数据 |
| File | 本地 Workspace + Artifact Registry | 上传、受控读写、产物与下载 |
| Research | Web Search/Fetch 工具 + Research Skill | 真实来源收集、核验与报告生成 |
| Knowledge | Docling + Embedding + Chroma | 文档解析、分块、索引和检索 |
| Quality | pytest、ruff、固定任务集 | 局部自动化测试、业务评测 |
| Delivery | 本地启动；最终 Docker Compose | 单机可复现运行 |

**选型理由**：不用 Next.js 是为了减少前端运行与构建复杂度；不用 PostgreSQL/pgvector 是因为第一版目标是小规模本地知识库，Chroma 更易部署。若未来规模、过滤或事务需求确实需要，再通过设计变更评估 PostgreSQL。模型使用一个经过验证的兼容接口，不承诺所有“OpenAI 兼容”模型具有相同工具调用能力。

**固定边界**：一个 Python 后端/一个 Web 前端；默认单用户、单 Worker，不对公网开放无认证接口；先 SQLite，不上 Redis/RabbitMQ。库的精确版本由 P00 进行一次兼容性验证后锁定。

### 3.1 数据流总图

```text
Browser / React-Vite
  └─ HTTP + SSE
      └─ FastAPI
          ├─ ThreadService / RunService / EventStream
          ├─ Upload / Artifact API
          └─ AgentExecutor (LangGraph)
              ├─ Lead Agent (reasoning + Todo + tools)
              │   ├─ Task Tool → SubAgent Dispatcher → Sub-Agents
              │   ├─ Builtin Tools + MCP Tools
              │   └─ Skill Loader (SKILL.md)
              ├─ Context / Tool Budget / Error Handling
              └─ Checkpointer (SQLite)
          ├─ RunStore / ThreadStore (SQLite)
          ├─ Workspace (files, artifacts)
          ├─ Research Services (search, evidence, report)
          └─ Knowledge Services (Docling, embedding, Chroma)
```

### 3.2 目标代码目录（逐阶段创建，禁止先堆空包）

```text
backend/
  app/
    api/            # threads, runs, SSE, files API
    core/           # settings, model factory, errors
    agents/         # lead agent, state, middleware
      subagents/    # task dispatcher, registry
    tools/          # builtin tools, registry, MCP adapter
    skills/         # SKILL.md discovery/activation
    runtime/        # run lifecycle, event stream, checkpoint
    workspace/      # safe file access and artifacts
    research/       # web search, evidence, report
    knowledge/      # parsing, chunking, vector retrieval
  tests/
frontend/            # React + Vite + TypeScript
eval/                # fixed examples and true evaluation outputs
docs/ARCHITECTURE.md
docs/DEVELOPMENT.md
```

后端不按模块拆微服务，不建两套 Agent 框架。API 只能调用应用服务，不把 Run 生命周期、LLM 调用和文件路径校验全部放进 Router。

## 4. 模块职责与接口

| 模块 | 输入 | 输出 | 严禁承担 |
|---|---|---|---|
| ModelFactory | 模型配置 | 兼容的 ChatModel | 保存用户运行状态 |
| Lead Agent | 用户请求 + State + 能力 | Tool Calls/最终回复 | 自行绕过 Tool Policy |
| Todo | 当前计划变更 | 结构化状态/进度事件 | 强制所有任务分步 |
| SubAgentDispatcher | 子任务 + 白名单 + 预算 | 结果/状态 | 无限并发/递归委派 |
| ToolRegistry | 工具定义 | 可用工具集合 | 替代 Agent 规划 |
| ToolExecutor | ToolCall + RuntimePolicy | 结果/异常 | 根据 Prompt 自行提升权限 |
| SkillLoader | Skill 名称和任务 | 必要指令文本 | 执行未授权副作用 |
| ContextManager | 消息、预算、任务重点 | 压缩后的输入 | 充当 Checkpoint |
| RunService | Run 创建/取消/终态 | 可查询执行记录 | 取代 LangGraph GraphState |
| EventStream | 后端真实事件 | SSE Envelope | 用文字猜测 Run 是否完成 |
| Workspace | 文件标识/安全操作 | File/Artifact Ref | 访问任意宿主机路径 |
| Research | 查询与来源 | Evidence/Report | 编造 URL 或假引用 |
| Knowledge | 文档与查询 | 带位置的检索片段 | 无来源生成事实 |

**通用工具合同**：稳定名称、参数 Schema、结果和错误类型、工具权限、超时、最大输出大小、是否有副作用。ToolResult 至少区分 success、content、artifact_refs、error_code、retryable、side_effect_unknown。真正授权在执行器中校验，Skill 仅是指导文件。

## 5. 关键运行状态与一致性

`thread_id` 为会话；`run_id` 为一次用户执行；`task_id` 为子任务；`tool_call_id` 为工具执行；`artifact_id` 为文件产物。不能将这些 ID 混用。

| 状态类别 | 负责什么 | 不保证什么 |
|---|---|---|
| LangGraph State / Checkpoint | messages、todos、状态快照、多轮继续 | 外部工具副作用 Exactly-Once |
| RunStore | RUNNING/SUCCEEDED/FAILED/CANCELLED 等服务端终态 | 模型输出文本的正确性 |
| Subtask 状态 | PENDING/RUNNING/COMPLETED/FAILED/TIMED_OUT/CANCELLED | 进程崩溃后任意子任务精确续跑 |
| SSE Events | token、todo、tool、subtask、run 事件 | SSE 断开即任务取消 |
| Artifact Store | 文件及归属、大小、路径和版本 | 模型声称已生成文件就确实存在 |

**恢复语义固定**：SQLite Checkpoint 用于已提交图状态和多轮历史；服务重启要检查孤儿 Run，不能自动将旧 RUNNING 置成功。对于执行状态未知的外部写工具，禁止盲目重试。首版不承诺所有正在执行的 Sub-Agent 在崩溃后从中间一步继续。

## 6. API 与 SSE 最小契约

- `POST /api/threads`、`GET /api/threads`：建立/列出会话。
- `POST /api/threads/{id}/runs`：开始任务；返回 run_id。
- `GET /api/runs/{id}`：查询 Run 状态、错误与基本统计。
- `GET /api/runs/{id}/events`：SSE 订阅；初期不承诺完整历史回放。
- `POST /api/runs/{id}/cancel`：幂等取消请求。
- `POST /api/threads/{id}/files`：上传；`GET /api/threads/{id}/artifacts`：产物列表。
- `GET /api/artifacts/{id}`：经归属校验下载。

SSE 事件包含 `event_id, run_id, thread_id, type, timestamp, payload`，子任务事件附带 `task_id`。事件类型至少覆盖 run_start/end、assistant_delta、tool_start/end、todo_update、subtask_start/end、artifact_created、error。前端依据服务端 Run 状态判断完成，不能通过检测助手说“已完成”判成功。SSE 断线不自动取消后端任务。

## 7. 关键安全约束

- 本地默认仅 `127.0.0.1` 访问；若未来公网部署，必须先添加认证与访问控制。
- API Key 只在环境变量中；工具参数/日志脱敏；Git 不提交 .env、用户文档、Checkpoint/数据库和模型输出密钥。
- 上传/网页/MCP/Skill 文本均是不可信内容，不允许覆盖系统级指令或绕过 ToolPolicy。
- Workspace 防路径穿越、符号链接逃逸、超大上传、任意覆盖和跨会话读取。
- 子 Agent 使用受限工具白名单、最大轮次/并发/超时，默认不可再次委派子 Agent。
- 不执行未经隔离的模型生成 Shell/Python；V1 文件任务用内置确定性工具。
- 模型/Tool 错误、引用不足和未知副作用要明确失败/不确定，不能虚构成功。

## 8. DeerFlow 2.0 精确源码参考索引

源码地址统一基于 https://github.com/bytedance/deer-flow/tree/v2.0.0 ，以下每个路径可在仓库中定位。开发时只阅读当前阶段的 1–3 个参考文件。

| 要开发的能力 | DeerFlow 2.0 文件 | 具体参考 |
|---|---|---|
| Lead 装配 | `backend/packages/harness/deerflow/agents/lead_agent/agent.py` | 模型、工具、Middleware 的装配顺序 |
| Agent 工厂 | `backend/packages/harness/deerflow/agents/factory.py` | 使用 LangChain create_agent；避免隐藏全局依赖 |
| 状态定义 | `backend/packages/harness/deerflow/agents/thread_state.py` | State Reducer 和 Todo/Artifact 合并 |
| Todo | `backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py` | 动态 Todo，而非所有任务硬编码工作流 |
| Task Tool | `backend/packages/harness/deerflow/tools/builtins/task_tool.py` | 把委派包装为 Tool、进度和结果 |
| Sub-Agent | `backend/packages/harness/deerflow/subagents/executor.py` | 独立上下文/并发/超时，父子 Checkpointer 分离 |
| Tool Registry | `backend/packages/harness/deerflow/tools/tools.py` | 内置/MCP 工具合并与去重 |
| MCP | `backend/packages/harness/deerflow/mcp/tools.py` | 外部工具内容与调用转换 |
| Skill Parser | `backend/packages/harness/deerflow/skills/parser.py` | SKILL.md Frontmatter 解析 |
| Skill Activation | `backend/packages/harness/deerflow/agents/middlewares/skill_activation_middleware.py` | 按需加载 |
| Skill Policy | `backend/packages/harness/deerflow/skills/tool_policy.py` | 工具允许列表 |
| Context | `backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py` | 摘要时保留必要上下文 |
| Tool Output | `backend/packages/harness/deerflow/agents/middlewares/tool_output_budget_middleware.py` | 大工具输出截断与预算 |
| RunManager | `backend/packages/harness/deerflow/runtime/runs/manager.py` | Run 终态、取消、孤儿处理 |
| Run Worker | `backend/packages/harness/deerflow/runtime/runs/worker.py` | graph.astream、运行错误、事件映射 |
| Checkpointer | `backend/packages/harness/deerflow/runtime/checkpointer/async_provider.py` | 异步 SQLite Checkpoint 使用 |
| Stream Bridge | `backend/packages/harness/deerflow/runtime/stream_bridge/base.py` | 事件发布/订阅抽象 |
| 文件路径安全 | `backend/packages/harness/deerflow/sandbox/security.py` | Host Bash 限制；本地目录非安全沙箱 |
| Workspace | `backend/packages/harness/deerflow/sandbox/local/local_sandbox.py` | 路径映射与受控文件操作 |
| API | `backend/app/gateway/routers/runs.py`、`threads.py` | Run/Thread 请求与状态契约 |
| Web 任务事件 | `frontend/src/core/tasks/context.tsx` | 子任务进度显示 |
| Deep Research | `skills/public/deep-research/SKILL.md` | 多轮检索、覆盖与核查方法 |

**不照搬**：原仓库大量渠道集成、完整 Gateway 协议、线程池后台执行细节、多种沙箱 Provider、复杂长期记忆和平台管理 UI。DeerFlow 的研究 Skill 不是 RAG 引擎，RAG 后端另行实现。

## 9. 交付标准

三个真实业务演示：带核验来源的研究报告；至少两份文档的跨文档问答与原文定位；多步骤文件任务生成可下载产物。附带真实执行状态、必要测试、失败案例与模型/Token 成本记录，不预设成功率或性能数字。开发顺序和**仅测试本次改动**规则见 [DEVELOPMENT.md](DEVELOPMENT.md)。
