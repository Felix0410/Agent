# 01 · 完整业务需求与总体系统架构

版本：v1.0 设计冻结候选；日期：2026-11-04；状态：总体设计，未经运行验证。
本文是“做什么、为什么、系统怎样组织”的唯一主文档。具体开发顺序见 02；边界契约见 04。

## 一、项目目标和最终成品

### 1.1 产品定义

Mini DeerFlow 是面向个人的通用智能体任务执行系统。用户以自然语言描述目标，系统决定是否需要步骤规划、哪些工具可用、哪些子任务值得交给独立 Sub-Agent，以及何时停止、汇总和交付。它不以替代 DeerFlow 为目标，而是选取其核心工程设计，构建规模可控、可测试、可长期迭代的简化版。

必须交付的不是一堆可单独演示的“功能点”，而是三条真实的端到端任务链路：联网研究、文档知识分析、多步骤文件处理。这三条共享同一 Agent 核心和任务运行设施，不重复构建三套 Agent 框架。

### 1.2 成功定义

- 功能完整：从用户请求、执行过程、外部工具、结果到产物都可追踪；简单问题不强制调用 Sub-Agent。
- 自主但受约束：Agent 可以做任务选择、搜索、生成文件，但工具权限、成本、循环次数和并发由代码限制。
- 可解释：任务计划、工具使用、子任务状态、失败原因与原始证据能被查看。
- 可靠：模型/工具异常不造成假成功；取消、断线、重启和重试有明确行为语义。
- 适合个人维护：模块化单体、简单部署、小上下文、少依赖；不为简历强上 MQ/Redis/K8s。
- 可验证：固定任务集、人工核对样本、自动测试、真实模型日志与费用记录相互区分。

### 1.3 明确不做

不构建企业多租户/RBAC/计费网关；不支持复杂 IM 渠道；不做 Agent 自我修改代码/配置；不做通用操作系统控制或未隔离 Shell；不提供插件商店/自动安装不可信 MCP；不开展模型训练、微调或强化学习；不宣称达到 DeerFlow 的功能覆盖率。

## 二、用户角色、入口与典型业务

### 2.1 用户与入口

V1 面向本地/自托管的单用户。入口为 Web Workspace；开发早期可以使用 CLI 或 API 调试。用户能新建会话、提问、上传文件、查看运行步骤、取消任务、再次追问、查看和下载产物。系统不主动执行未经发起的定时任务。

### 2.2 业务 A：通用交互与基础任务

输入：自然语言和可选工具权限、模型、会话上下文。
简单问题走模型直接答复；工具类问题经模型选择受限工具；复杂目标则调用 Todo。交互支持多轮、流式输出、错误呈现、历史记录、成本与状态。
验收：单轮/多轮/工具查询都能运行；工具错误可解释；前端不依赖模型说“完成了”就标记服务端成功。

### 2.3 业务 B：Deep Research

用户输入一个开放研究问题，例如“比较主流多智能体框架在工程落地上的差异”。
处理步骤：澄清必要范围（不能自行凭空设定）→ 建立研究计划 → 根据多个研究维度发起检索 → 对真实网页做去重/可信度判断 → 视需要委派 Research Sub-Agent → 汇总支持/反对证据与不确定性 → 输出含来源的 Markdown 报告和摘要。
输出对象：ResearchPlan、SearchHit、EvidenceRecord、ReportArtifact。
关键约束：每个事实必须标记来源类型；原始 URL 不能由模型虚构；无法访问来源时只能说明限制；引用必须和正文中的主张有明确对应关系。
降级路径：网络失败可基于已有证据有限输出，但必须注明范围；部分子任务失败不伪装为全部已核验。
V1 不保证专业论文级系统综述、正式学术审稿或海量全网爬取。

### 2.4 业务 C：多文档 RAG 与文献/技术文档分析

用户上传 PDF、Markdown、TXT，系统保留原始文件和合法访问记录。
管线：上传校验 → 文本/章节/页码解析 → Chunk 划分和元数据 → Embedding → 检索索引 → search_knowledge 工具 → 跨文档综合 → 带文件名/页码/片段引用的答案。
查询分为：单文档定位、跨文档比较、综合总结和证据不足拒答。支持根据选择的文档范围限制检索。
输出对象：Document、Chunk、IndexVersion、RetrievedEvidence、Citation、QAResponse。
引用要求：索引中的上下文增强文本与真实原文分开，不能把模型生成的摘要当成原始证据；原文位置映射能追溯。
性能目标先以小规模可验证文档集为准，不预设高 Hit@K。
起步只做常见文本型 PDF/Markdown/TXT；扫描件 OCR、复杂表格/图片证据、百万文档规模为后续增强。

### 2.5 业务 D：多步骤文件与数据任务

输入：用户已有 CSV、Markdown、文本资料和明确任务，如“合并资料并生成带分类统计的报告”。
执行：Lead Agent 生成或维护 Todo → 工具读取文件 → 确定性数据处理（白名单工具）→ 产物写入 Workspace → 显示实际完成状态 → 交付 Markdown/CSV/JSON。
不能凭空声明写出了文件；Artifact 必须可访问、包含元数据、大小及校验信息。模型生成的任意程序不能在宿主机直接运行；需要通用代码执行时进入隔离沙箱增强阶段。
文件写入明确覆盖、冲突及路径访问策略。

### 2.6 支撑业务能力总表

| 能力 | 作用 | V1 约束 |
| --- | --- | --- |
| Lead Agent | 动态决策、综合输出 | 模型驱动主循环，有限轮次 |
| Plan/Todo | 任务分解、进度 | 结构化 Todo，非固定流程图 |
| Sub-Agent | 独立分析、减少父上下文污染 | 最多有限并发，默认禁止递归委派 |
| Tool Registry | 工具参数/白名单/执行控制 | 工具权限在代码层 |
| MCP | 连接外部数据服务 | 少量审核过的只读服务 |
| Skills | 任务规范和工具使用方法 | 按需载入 SKILL.md，不自动提升权限 |
| Context Manager | 长对话压缩与预算 | 保留最新消息、Todo、证据、产物 |
| Checkpointer | LangGraph 状态持久化 | 不是外部副作用事务 |
| Run Service | 执行生命周期 | 不与 Graph State 混为一体 |
| Event Stream | SSE/进度/回放 | 事件有 run_id、序号、类型 |
| Workspace | 文件隔离与 Artifact | 目录安全、上传限制、原子写入 |
| Knowledge Service | RAG 解析索引检索 | 来源与范围透明 |
| Evaluation | 质量、延迟、成本、故障 | 不用模型主观分数冒充真值 |

## 三、系统总体架构

### 3.1 架构原则

采用一个仓库、一个后端应用、内部明确模块的模块化单体。框架依赖方向为 UI → API → Application Service → Agent/Domain → Infrastructure Adapter。Agent 核心不能 import HTTP Route；Tool 不可直接绕开授权访问任意文件；知识检索可独立由工具调用，但不会与模型提示词混成一个巨大的模块。

### 3.2 文本架构图

    Browser (Workspace / Chat / Todo / Subtasks / Files)
      |
      | HTTP + SSE
      v
    FastAPI Gateway
      |- Thread API / Run API / Files / Artifacts / Config
      |- Request Validation / Error Mapping / Run Creation
      v
    Application Services
      |- RunService / ThreadService / EventService
      v
    Agent Harness (LangChain + LangGraph)
      |- LeadAgentFactory / ModelFactory / RuntimeConfig
      |- AgentState + Middleware (Todo, Context, Errors, Budget)
      |- TaskDispatcher + SubAgentFactory
      |- ToolRegistry + MCPAdapter + SkillLoader
      v
    Infrastructure
      |- Checkpointer (SQLite initially)
      |- RunRepository / EventStore
      |- Workspace / ArtifactStorage
      |- SearchProvider / KnowledgeIndex / LLM Provider
      |- Optional isolated sandbox (only when approved)

### 3.3 目标目录

    backend/
      app/
        api/                 # HTTP routes, SSE, DTO, validation
        core/                # config, models, errors, logging
        agents/              # lead factory, graph state, middleware
          subagents/         # registry, dispatcher, executor, limits
        tools/               # contracts, registry, builtin, mcp
        skills/              # discovery, parser, activation, policy
        runtime/             # run lifecycle, checkpoint, events
        workspace/           # uploads, artifacts, path security
        knowledge/           # parser, chunks, retrieval, citations
        research/            # research skill support, evidence/report
      tests/
    frontend/
      src/                   # workspace, client, SSE, UI
    eval/                    # fixtures, scoring, experiment snapshots
    docs/                    # architecture, ADR, progress, references
    scripts/                 # developer commands
    .env.example

结构是目标而不是要求 P00 创建所有空包。当前阶段按需求逐渐形成目录，避免空抽象。

### 3.4 模块依赖和禁止项

- API 只负责请求/响应、鉴权入口、事件订阅，不承担 LLM 工具逻辑。
- Lead Agent 通过 ModelFactory、ToolRegistry、SubAgent Dispatcher 与 Skills 服务获得能力，不自行查询业务数据库。
- Sub-Agent 可以有独立模型/Prompt/工具白名单，但不默认无限委派或持有父 Agent 全部授权。
- ToolExecution 负责超时/鉴权/错误/审计；Skill 文本只能指导模型而不能绕过工具的真实策略。
- RunService 是运行状态权威源；Checkpoint 仅用于图状态；SSE 只是交互传输与观察。
- KnowledgeService 只返回有出处的检索结果，不承担最终生成答案。
- ResearchService 组织搜索证据和报告，既可被 Agent Tool 调用，也可由专用 Skill 指导。
- 未来若需要分布式 Worker，只能在明确的运行事务/幂等设计后引入。

## 四、核心对象与数据设计

### 4.1 身份标识与层级

Thread 对应连续会话；每次请求产生 Run；Run 可包含多个 DelegatedTask、ToolInvocation、Event 与 Artifact；Document 属于用户/Workspace，并由文档索引管理。必须区分 thread_id、run_id、task_id、tool_call_id 和 artifact_id，不能复用一个字符串表示不同语义。

### 4.2 最小领域对象

Thread：id、title、created_at、updated_at、metadata。
Run：id、thread_id、status、input_ref、started_at、ended_at、error、cancel_requested、model_name、usage。
AgentState：messages、todos、file_refs、research_evidence_refs、context_summary、可用工具元数据（字段逐阶段添加，Reducer 处理合并）。
DelegatedTask：id、parent_run_id、type、prompt_ref、status、attempt、timeout、result_ref、error。
ToolInvocation：id、run_id、task_id?、tool_name、arguments_digest、status、duration、result_ref、error_type。
Artifact：id、thread_id、run_id、virtual_path、name、mime、size、hash、created_at。
EvidenceRecord：source_type、source_url/document_id、location、retrieved_at、text_excerpt、confidence_policy、usable。
Document/Chunk：document_id、parse_version、chunk_id、page/section、source_text、retrieval_text、embedding_version。
Skill：name、description、path、enabled、allowed_tools（名称和权限不等于事实安全认证）。
EvaluationRun：dataset_version、git_sha、model/config、results、scores、token/cost、run_trace_refs。

初期数据库仅实现当前阶段需要的持久对象，不提前设计几十张表；实际 DDL、ORM 由对应任务决定。

### 4.3 Run 与任务状态机

Run：CREATED → RUNNING → SUCCEEDED / FAILED / CANCELLED / INTERRUPTED；启动后出现未知旧 RUNNING，应标 ORPHANED/UNKNOWN 并核对。
DelegatedTask：PENDING → RUNNING → COMPLETED / FAILED / CANCELLED / TIMED_OUT / UNKNOWN。
RunService 不可因模型内容出现“任务完成”字样而自动标记成功；必须根据图完成、工具/产物校验及业务合同判定。取消请求允许处于 CANCELLING 中间态，不能承诺立即杀掉所有外部命令。

### 4.4 三类不同的持久化

1. Graph Checkpoint：LangGraph 消息/Todo/节点状态，按 thread_id 等配置写入。
2. Run/Task 数据：请求与执行生命周期的业务记录，便于恢复、审计和列表展示。
3. Event/Artifact 数据：SSE 事件与文件/结果，支撑重连、回放及下载。

这些可能共享同一个 SQLite 实例，但逻辑必须分离。外部工具调用不可仅凭 Checkpoint 推断没有重复执行；写操作需要独立的幂等或人工确认。

## 五、详细运行链路

### 5.1 最基础的单轮 / 工具对话

UI 发消息 → API 校验 → 创建 Thread/Run → 读取历史 Checkpoint → 构造 Lead Agent → 模型做决策 →（可选）Tool 执行 → 返回 ToolMessage → 模型汇总 → 保存状态与事件 → Run 标终态 → UI 显示结果。
简单问题走直接答复，不创建 Sub-Agent。若工具失败，策略可选择说明失败、尝试替代工具或结束，而不是无限重试。

### 5.2 复杂任务 / 多智能体

用户目标 → Lead 判定需要 Todo → 以 write_todos 更新结构化计划 → 选择子任务范围 → task 工具委派 → Dispatcher 权限过滤/限流 → 子 Agent 私有消息上下文 → 工具执行 → 输出证据或失败 → 父 Agent 综合 → 校验产物 → 完成。
父子 Agent 可共享受控工作空间，但消息历史必须隔离；只返回必要的摘要、证据与产物引用。对于并发写入同一文件，使用独占/冲突策略，不允许静默覆盖。

### 5.3 上下文膨胀

每次模型调用前预算器估计消息/工具输出/Skill 文本大小；超过阈值触发裁剪/摘要。结构化 Todo、未完成任务、重要来源及关键文件引用应保持在独立状态或摘要保护集合。摘要之后用固定测试检查目标、约束、引用和动作可连续性；不将所有大工具输出原样回填上下文。

### 5.4 中断和恢复

正常 Checkpoint 解决已提交的 Graph 状态读取，但子任务进程、联网请求与外部副作用不一定能原地恢复。重启时 RunService 核查非终态 Run：对无副作用节点可考虑重调度；对结果未知的外部写操作标记 UNKNOWN，禁止盲目自动重试。面向用户只承诺已测试的“恢复/重试”精度，而不是泛化宣称断点续跑。

### 5.5 流式运行和取消

API 开始任务后，事件层发 run_started；图迭代产生 token/message delta、tool_start/end、todo_update、subtask_start/end、artifact_created；最终发 run_succeeded/run_failed/run_cancelled。每条事件含 run_id 与单调序号，UI 按事件而不是文本推断真实状态。
SSE 网络断开不等于服务端取消；前端重连时先获取 Run 状态，支持的情况下从 last_event_id 续订。取消是服务端幂等命令，停止新增工具动作，已经执行的外部副作用不保证撤销。

## 六、技术栈和演进约束

起步 Python 3.12+、FastAPI、LangChain 1.x、LangGraph、Pydantic、pytest、SQLite（持久 Checkpoint 与轻量业务状态）、React/Next.js（薄 UI）。版本以 P00 实际兼容测试锁定。
MCP 优先使用已有成熟 Adapter，不写协议栈。RAG 可以先小规模索引验证，再选择 PostgreSQL/pgvector 或其他可靠存储；决定须有数据规模/成本/维护依据。
容器部署主要用于可复现运行；模型生成的任意 Shell/Python 只有在真正隔离（文件/网络/进程/时间/资源限制）后才允许启用。
Redis、MQ、微服务、K8s 等仅在可证明需求和可解释取舍时引入。

## 七、安全、合规与系统边界

- API Key 等秘密只放环境变量/本地私密配置，日志脱敏，不提交 Git。
- 默认只读外部集成；文件写操作限定当前 Workspace，访问需要会话归属与路径校验。
- 对上传文件、网页和 MCP 内容执行不可信数据处理，严格隔离 Prompt 指令优先级。
- 文件名、路径符号链接、压缩包、超大文件、重复上传、表格公式注入等需要测试。
- Tool Schema、权限白名单、并发上限、时间预算在程序中强制，不能只靠 Prompt。
- 成本保护：每 Run 最大模型调用次数、最大工具轮次、预算、超时和最大并发。
- 用外部检索来源时记录出处和访问时间，不复制受限全文作为默认公开产物。
- 许可：借鉴设计可以；复制 MIT 代码必须保留许可与版权归属。

## 八、性能、质量和非功能要求

可用性：至少单用户单进程稳定完成三条代表任务；系统错误时清楚失败，不虚假成功。
可观测：run_id/thread_id/task_id/trace_id 贯穿日志；至少记录工具名、耗时、错误类别、Token 和可定位的证据。
部署：不要求公网及多租户；本地启动和 Docker Compose 至少提供一种可复现方案。
质量：核心状态、工具权限、SSE、Run 恢复使用自动化测试；研究报告与 RAG 答案有人工核验样本。
效率：不预设响应速度，先建基线；复杂任务保留 token/time/budget 统计，避免无界重试。
开发效率：模块接口小而清晰，运行快照/文档摘要便于本地 AI 在小上下文中工作。

## 九、最终产品验收边界

至少能完成以下真实演示，且不是提前写死答案：
A. 一个开放主题 → 有计划、联网工具调用、可核验真实来源、生成 Markdown 研究报告。
B. 上传至少两份文档 → 建索引 → 跨文档问题 → 返回可回到原文片段的引用。
C. 一个文件处理任务 → Todo/工具调用/文件写入 → 真实可下载产物；取消或失败有正确状态。
另外要展示一次 Sub-Agent 并发、一次上下文摘要和一次模型/工具故障测试。所有性能指标来自本项目真实运行，不使用上游宣传数字。

## 十、详细设计与开发对应

源码参考在 03；具体 Tool/API/Event 契约在 04；阶段 P00–P12 在 02；评测与门槛在 05；Codex 协作与部署在 06。本文规定边界与成果，不将未实施功能误写为已完成。
