# 总体业务与系统架构（正式方案）

**版本**：v1.7 · 2026-11-09
**状态**：V1 总体架构确定；P01–P06 已有真实代码，P02–P06 仍待用户手动验收；P07 Deep Research 详细方案与逐文件实施合同已完成，**P07 业务代码尚未开发（PLAN_READY）**。开发前先复测P06最新注释提交的格式/直接回归。实际进度以 [DEVELOPMENT.md](DEVELOPMENT.md) 和 `docs/progress/` 为准。
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

### 3.2 实际工程布局与目标模块（按阶段增加）

目前使用可安装的 `backend/src/minideerflow/` 包，**不新建第二套 `backend/app/`**。P01 已有核心模型、Agent、计算工具及本地演示 API；P02 才增加运行时与历史会话：

```text
backend/
  pyproject.toml
  src/minideerflow/
    main.py                 # FastAPI 应用/lifespan
    config.py               # Settings 与根目录 .env
    api/                    # demo 已有，threads/runs 从 P02 增加
    core/                   # 模型工厂
    agents/                 # 主 Agent 和服务
    tools/                  # 受限内置工具
    runtime/                # P02: Run、SQLite、Checkpoint、EventBus
    workspace/              # P03 起
    skills/                 # P05 起
    research/               # P07 起
    knowledge/              # P08 起
  tests/
  data/                     # 本地数据库与执行产物，Git 忽略
frontend/                   # 已有 React + Vite + TypeScript
docs/DEVELOPMENT.md
docs/progress/
docs/tasks/                 # 当阶段 Codex 执行清单
```

上面注释为模块落地顺序，不表示未来模块已经创建。后端仍为单体，不按模块拆微服务，不构建两套 Agent 框架。API 只能调用应用服务，不把 Run 生命周期、LLM 调用和路径校验都塞进 Router。

### 3.3 P03 Workspace 安全域（具体实施见 DEVELOPMENT.md）

P03 在现有 `backend/src/minideerflow/` 包下新增 `workspace/{models,storage,repository,service}.py`、`tools/file_tools.py`、`api/files.py`，在当前 React `ChatPanel` 旁加入 `FilesPanel`。文件保存在被 Git 忽略的 `backend/data/workspaces/{thread_id}/`，文件真实路径只在服务端管理；所有上传、生成、Artifact 查询均登记到业务 SQLite。

**可信授权**：Thread Run 在后端构造 `WorkspaceContext(thread_id,run_id,workspace_service)`，由 `create_agent(context_schema=...)` / `ToolRuntime` 注入文件工具，不将这几个身份字段开放给模型参数。工具读取仅使用登记过的 file_id；写入仅接受安全显示名和文本；禁止宿主机 Shell/Python/任意路径与对已有文件覆盖。注意这是单用户本地范围内的文件安全边界，**不是认证的多租户隔离或容器沙箱**。

文件系统以 UUID 内部名、目录文件描述符和不跟随符号链接实现安全访问；数据库记录文件与产物归属和大小/sha256。附件最初只支持 UTF-8 文本及 PDF 原样保存；PDF 解析留待 P08，RAG 与复杂文件操作不属于 P03。

### 3.4 P04 Lead / Todo / Sub-Agent 的职责边界（设计态）

P04 保持单个 `create_agent` 主 Agent 和 P02 `RunService`，增加 `write_todos` 与 `task` 两个模型工具，按复杂任务需要使用，不强制简单聊天规划。Todo 由 LangGraph 自定义 `AgentState.todos` + `Command` 更新，同时保存当前 Run 的 SQL 快照供刷新/重启展示；不靠自然语言推断“任务完成”。

`task` 由服务端可信 `AgentRunContext` 决定 Run/Thread 权限，Dispatcher 仅允许 `general/research` 两种固定子代理。每 child 独立模型消息列表、无父 Checkpointer/子任务再次委派，工具权限仅为角色白名单与父权限的交集；子代理默认只读文件，由 Lead 决定是否生成最终 Artifact。最多 3 个并发子代理、每父 Run 4 次委派，child35秒/父Run600秒限额（P06调整）。子任务 SQL 生命周期与 EventBus SSE 绑定父 Run，不能把子模型文本假装服务端状态。

P04 不提供联网搜索、MCP、取消 API、子任务跨重启自动恢复或分布式队列。两个只读 GET 接口用于历史 Todo/Task 恢复；React `TodoPanel`、`TaskPanel` 同步真实执行过程。具体接口/逐文件任务见 [DEVELOPMENT.md P04](DEVELOPMENT.md) 和 [Codex P04-A/B/C/D](tasks/P04-ABCD.md)。

### 3.5 P05 ToolRegistry / MCP / Skills 执行边界（已实现，待审核）

P05 在现有 P04 Lead `create_agent` 工具列表与 LangChain ToolNode 之间增加**注册表与官方 `awrap_tool_call` Middleware**：将内置、批准的 MCP、Skill 元工具统一注册，构造当前可信 Run 的可用工具快照，二次检查权限与超时。Middleware 保留 `ToolMessage` 与修改 State 的 `Command`，尤其不能破坏 P04 的 `write_todos`；不另造 Agent 循环。P01 独立单轮计算不自动新增 MCP/Skills；P04 child 的现有只读工具白名单保持。

MCP 最初仅连接用户明确启用的、在单机回环地址运行、无副作用的 Streamable HTTP Server，工具名字/参数 Schema/说明经白名单和 SHA256 指纹双重批准；**默认完全禁用**。示例 Server 只提供确定性 `lookup_fact` 以验证真实工具协议，不能据此宣称已经具备外网 Deep Research。连接失败不影响 builtin；MCP 服务器本身必须可信，客户端不能单靠 readOnlyHint 强制它只读。

Skills 初期是版本管理的 `backend/skills/public/<name>/SKILL.md`：安全解析 YAML、发现简介、按需用 `list_skills/read_skill` 读取单篇正文；内容只作为模型的工具结果，不能提升权限或装载任意本地程序。React 只增加只读 CapabilityPanel 和 `GET /api/tools`、`GET /api/skills`，在原有 RunStatus 中观察实际 ToolCall/ToolTrace。已锁定mcp1.30.0/adapters0.3.2/PyYAML6.0.3；MCP断连只收回授权，不影响内置工具，恢复需重启。Fake、真实模型、浏览器与测试结果见[阶段进度](progress/P05.md)。具体见 [P05 正式合同](DEVELOPMENT.md) 和 [P05-A/B/C/D Codex 任务书](tasks/P05-ABCD.md)。

### 3.6 P06 上下文预算、Usage 与取消协议（已实现，待审核）

P06 不替换 P05 `ToolGuardMiddleware` 或 P04 `create_agent`，而是通过官方 `AgentMiddleware` 在模型/ToolCall 周围添加共享 RunBudgetTracker（父+子Agent+摘要模型）、SQLite Usage 数据记录和旧消息安全压缩。**模型提供方的真实 token 用量**与基于字符/字节的估算必须分列存储和展示，不计算未经提供方确认的实际账单。旧消息摘要不会修改 P02 业务历史记录，只在 LangGraph Checkpoint 中更新受控的消息列表，保留当前目标、Todo、完整 ToolCall/ToolMessage 配对与真实 File/Artifact 引用。

超过12KiB的成功纯文本工具输出在进入模型之前保留安全1KiB预览+已登记file_id或Artifact引用，不把同一原始已上传文件无意义地再复制一份；无法持久登记则显式错误，不能偷偷丢数据。P05 `write_todos` 的 `Command` 不受外置策略影响。

当前 SQLite `runs.status` 已允许 CANCELLED，但不支持 CANCELLING，P06 **不重建状态表**：以 `cancel_requested_at` 持久标记“请求取消中”，而非提前改变终态。CREATED 可直接 CANCELLED 并由队列跳过；RUNNING 取消仅终止当前独立 Graph Task，并在 P04 Child 与 Workspace/SQLite 归档后转 CANCELLED；外部副作用结果不可确认时 FAILED/OUTCOME_UNKNOWN 与 Thread 保守恢复。后端 Run 时限升至600秒时，前端轮询必须相应升至720秒，SSE 断线只断订阅、不取消 Run。

API 增 `GET /api/runs/{run_id}/usage` 与 `POST /api/runs/{run_id}/cancel`，Web 增 `UsagePanel`/取消按钮，继承全部 Thread/Run/Todo/Task/Artifact/MCP/Skill 行为。具体文件/状态规则参见 [P06 详细设计](DEVELOPMENT.md) 和 [P06-A/B/C/D Codex 执行合同](tasks/P06-ABCD.md)。

### 3.7 P07 Deep Research 结构化证据闭环（设计态）

P07 不引入第二个 LangGraph主循环。现有 P04 Lead/Todo/Research Child、P05 ToolRegistry/Skills、P06 共享预算/取消与P03 Workspace组成真实网络研究链。仅当用户明确配置Tavily API key时，在Registry增加三个只读研究工具`search_web(query)`/`fetch_webpage(evidence_id)`/`list_evidence()`及仅Lead可用的`save_research_report`。没有key时，普通Agent依旧离线可用，不宣称已联网。

**安全变更**：ResearchChild只增加前三个`read`研究工具，General不变，Child仍无写文件、委派、MCP/Skills。Child必须经过ToolGuard与父Policy/白名单的交集，并以P06共享Tracker记录**一次**工具调用，不重复安装旧ChildToolBudgetMiddleware。EvidenceStore存于同一个Run/Thread业务SQLite，最多6个Search调用/8个Extract/30来源/1报告；Source ID由服务端生成并核验，不信任模型生成的“来源”。

搜索经固定Tavily HTTPS Search API，网页正文由固定Tavily Extract API通过已登记Evidence ID抓取（**没有本机直接访问任意模型URL的HTTP接口**）。来源保留SNIPPET_ONLY/EXTRACTED/EXTRACTION_FAILED的精确定义；“已提取正文”不代表独立核实了事实。报告Markdown由服务器校验真实来源ID后生成脚注，经P03注册真实Artifact后才显示可下载。React只读`ResearchPanel`可刷新查历史，SSE仅小状态事件，不包含正文/密钥。详细合同：[P07开发方案](DEVELOPMENT.md)、[P07逐文件Codex任务](tasks/P07-ABCD.md)。

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
