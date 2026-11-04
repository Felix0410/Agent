# 开发方案、任务顺序、局部测试与进度

**方案版本**：v1.1 · 2026-11-04  
**当前状态**：设计确定；P00 尚未开始。  
**原则**：从零构建 Mini DeerFlow，逐步增加能力；一个阶段可以拆成多个很小的任务，但 Codex 每次只执行一个；用户审核后才能进入下一个阶段。

## 1. 固定的实施方案

- 项目：一个 GitHub 仓库，模块化单体，一个 Python FastAPI 后端和一个 React/Vite 前端。
- Python 3.12 + uv 管理依赖；FastAPI/Pydantic；LangChain + LangGraph（使用框架已有 Agent/Tool/Checkpointer，不重写其核心）。
- 单模型提供方先打通 Tool Calling；模型通过 ModelFactory 替换，不建立多模型调度平台。
- SQLite 存会话/Run 业务信息，LangGraph SQLite Checkpointer 保存 Graph 状态；单 Worker。
- SSE 输出模型 token、工具和子任务状态；前端只根据真实服务状态展示任务完成情况。
- Sub-Agent 通过 `task` 工具委派；`asyncio` 有界并发，独立上下文、白名单、超时。
- MCP 通过现成 Adapter 接入；Skills 使用 `SKILL.md`，仅加载当前相关的内容。
- 文档 RAG 使用 Docling、Embedding、Chroma；先实现基线向量检索，不无证据增加复杂重排序。
- 安全文件工具和 Workspace 优先；宿主机 Shell 禁止。Docker Compose 仅在最终交付阶段配置。
- 精确三方版本、模型可用性与异步 Checkpointer 兼容性在 P00 实测并记录；选型原则不因短期技术潮流频繁变更。

## 2. 最重要的测试规则：只测本次改动

**每个任务包只测试：①本次新增的功能；②本次修改的功能；③因其公开接口或共享实现被本次改动直接影响的调用方。**

绝不默认在每次任务完成后运行整个项目的 pytest、全部 E2E、所有旧模块、全部 Research/RAG 评测。不是“所有阶段都全量回归”，也不是“每次重复跑过去的全部测试”。

| 改动类型 | 必须做的局部测试 | 不需要做的事 |
|---|---|---|
| 只修改文档 | 检查链接/章节一致性 | 无须跑代码测试 |
| 新增独立 Tool | 此 Tool 的正常、失败/参数校验测试 | 重测全部其他 Tool |
| 修改共享 ToolRegistry | Registry 与直接使用其接口的测试 | 全量 Agent + UI 测试 |
| 修改 Sub-Agent Dispatcher | 委派、并发/超时及直接依赖测试 | 重测 RAG、所有业务报告 |
| 修改 Run/Checkpoint | 状态转换、保存/恢复、受影响的 API 合同 | 全套业务质量 Eval |
| 修改 SSE 事件字段 | 对应事件映射及直接消费该事件的前端测试 | 全站 E2E |
| 修改文件读写 | 当前文件工具的安全/边界测试 | 所有模块的测试 |
| 修改 RAG 检索 | 本次检索与引用测试/局部金标题 | 重新跑所有研究任务 |
| 修改 Research Skill | 指定研究场景/工具链 Smoke | 全部旧文档 QA |

**共享模块变更时**，由 Codex 明确列出受影响调用链，最多扩展到直接受影响接口；禁止为了“保险”无边界扩大到全项目。如果变更与其他模块无关，绝不重测它们。

**测试类型**：先做本次改动对应的单元测试；需要跨接口时做最小集成测试；只有用到真实模型/真实 MCP/真实搜索时才做该功能的真实 Smoke。Mock 结果与真实调用结果分开记录。必要的文件安全、并发与副作用边界测试仍属于当前功能的局部测试，不能省略。

**阶段结束不做自动全量回归**。最终 P09 仅做三条核心业务的发布验收 Demo 和本阶段变更对应测试；是否额外执行全量测试套件，届时由用户决定。异常修复优先补一个能复现该异常的局部测试，而非重新跑所有历史用例。

Codex 报告必须明确列出“本次改了什么 → 测了哪些 → 为什么足够覆盖直接影响范围 → 哪些没测（因为未受影响）”。不允许把“没跑完整套测试”误写成“所有测试通过”。

## 3. 总体开发阶段

| 阶段 | 实际交付 | 本阶段仅需验证的内容 | DeerFlow 主要参考 |
|---|---|---|---|
| P00 工程初始化 | 可运行 FastAPI 基础项目与环境 | 健康检查、安装、配置加载 | Agent factory/依赖布局 |
| P01 单 Agent | 模型→工具→模型最小循环 | 真实 Tool Call、参数/失败 | Lead Agent、factory |
| P02 API/会话/Web 最小版 | Thread、Run、SQLite Checkpoint、SSE、薄聊天 UI | 新 Run/Thread API、当前 SSE 和状态保存 | runtime/runs、checkpointer、Gateway |
| P03 Workspace | 上传、受控读写、Artifact 下载 | 当前文件工具与路径安全 | sandbox、uploads/artifacts |
| P04 Todo / Sub-Agent | 动态 Todo、有限并发委派与汇总 | 当前 Todo/Task、超时/隔离 | todo、task_tool、executor |
| P05 MCP / Skills | 外部工具注册、SKILL.md 按需加载 | 新 MCP/Skill 和工具权限 | tools/mcp/skills |
| P06 长任务可靠性 | 上下文压缩、预算、取消、Run 孤儿检查 | 改动的 Summary/Run 路径 | middleware、RunManager |
| P07 Deep Research | 搜索、多子任务、带引用研究报告 | 新 Research 业务案例和引用 | deep-research SKILL.md |
| P08 文档 RAG | Docling、Chroma、跨文档检索、引用 | 新解析/检索与局部金标问题 | 上游工具/文件接口 |
| P09 交付 | UI 完善、Docker、固定评测与演示 | 本次交付相关测试 + 三条真实 Demo | 上游 Web/运行接口 |

阶段是开发顺序和依赖，不是承诺工期；每阶段再次拆小任务以控制 AI 上下文。任何功能如果已经稳定，不因为新阶段开始就做无关重构。

## 4. 每阶段任务详细说明

### P00 — 工程初始化（下一步唯一允许开始的任务）

目标：建立最小 Python 项目、统一环境与 Git 工作规范。
实际工作：Python 3.12、uv、依赖锁；FastAPI 健康检查；最小配置（含模型环境变量模板）、pytest、ruff、.gitignore；必要的 backend/ 结构。暂不创建复杂前端/数据库/十几个空业务包。
验收：干净环境能够安装、启动健康检查；能运行 P00 的测试；没有真实密钥提交；README 与实际命令一致。
参考：DeerFlow `agents/factory.py` 的分层思想，实际框架版本要本地验证。
**不做**：Agent 模型调用、MCP、Sub-Agent、RAG、Docker。

### P01 — 最小可运行 Agent

目标：命令或简单 API 输入自然语言，模型真实调用一个有 Schema 的只读 Tool，再用 ToolResult 回答。
实现：ModelFactory、最小 Lead Agent、一个简单只读工具、超时与错误；用 LangChain 的 Agent 构造能力，不手写大规模图编排。
局部测试：该 Tool 参数、失败和调用循环；一次真实模型 Tool Calling Smoke（可用时）。
参考：`agents/lead_agent/agent.py`、`agents/factory.py`、`tools/tools.py`。
不做：规划、子 Agent、RAG、持久化。

### P02 — 服务化 + 最简前端

目标：真正从浏览器操作 Agent，而不是长期停留在脚本阶段。
实现：Thread/Run ID、RunService、SQLite Checkpoint、多轮会话、FastAPI SSE、查询状态与最小 React/Vite 聊天界面。首版同一 Thread 只允许一个活跃 Run；SSE 断开不等于任务取消。
局部测试：新 Thread/Run 接口、Checkpoint 读回、流事件结束与真实 Run 终态一致；UI 只做新增事件消费的测试。
参考：`runtime/runs/manager.py`、`runtime/runs/worker.py`、`runtime/checkpointer/async_provider.py`、`app/gateway/routers/runs.py`。
不做：完全兼容 DeerFlow Gateway、跨进程 Worker、全套前端页面。

### P03 — 文件工作空间

目标：能从 Web 上传文件，Agent 使用受限文件工具，并交付真实文件。
实现：每 Thread 独立 Workspace，受控 list/read/write、Artifact Registry、下载 API；文件容量、路径、符号链接与覆盖策略。
局部测试：上传读取写入下载；../、跨会话读取、软链接逃逸与超额操作。文件安全测试是 P03 直接相关，不算无关全量测试。
参考：`sandbox/security.py`、`sandbox/local/local_sandbox.py`、`app/gateway/routers/uploads.py`。
不做：任意 Bash、完整容器沙箱池。

### P04 — Todo 与 Sub-Agent

目标：复杂任务能建立可更新计划，Lead Agent 委派最多有限数量的子 Agent，独立运行后归并结果。
实现：Todo State/工具；`task` Tool；general 与 research 两个配置角色；单进程 `asyncio.Semaphore` 限制并发；子 Agent 只接收必要上下文和工具权限；超时/取消/状态事件。
局部测试：Todo 更新、两个子任务委派、并发上限、子任务失败、超时和权限拒绝。
参考：`todo_middleware.py`、`tools/builtins/task_tool.py`、`subagents/executor.py`。
不做：分布式执行、递归委派、子任务崩溃精确续跑。

### P05 — MCP 与 Skills

目标：新增 MCP 工具和 SKILL.md 不需要重写 Lead Agent。
实现：统一 ToolRegistry；一类真实只读 MCP Server；Tool allowlist/timeout；Skills 元信息发现、按需正文注入及工具约束。
局部测试：新工具调用、MCP 连接失败、Schema 校验、Skill 解析/激活与禁用工具无法越权。
参考：`tools/tools.py`、`mcp/tools.py`、`skills/parser.py`、`skills/tool_policy.py`。
不做：MCP 市场/自动安装、复杂认证服务。

### P06 — 上下文、预算与可靠执行

目标：长任务不无限吃上下文；取消、错误、模型超时有正确状态。
实现：Token/工具次数/时间预算、工具长输出管理、触发式摘要与保护性状态、循环检测、Run 取消和服务重启孤儿 Run 标记。
局部测试：触发摘要后 Todo/来源引用保留、预算终止、当前 Run 取消/恢复行为和错误路径。
参考：`summarization_middleware.py`、`tool_output_budget_middleware.py`、`runtime/runs/manager.py`。
不做：未经证明的“任意中断点自动恢复”，不做完整长期记忆。

### P07 — Deep Research

目标：第一个完整复杂业务闭环。
实现：Web Search + Fetch Tool（只采用一个可验证的检索供应商，通过 Adapter 隔离）；Research Skill；多轮检索和来源去重；Sub-Agent 辅助研究；报告模板、引用与 Markdown Artifact。
局部测试：Research 新增工具及固定研究问题；至少一次真实来源搜索并人工检查主要引用。
参考：`skills/public/deep-research/SKILL.md`、上游 Task Tool。
不做：无限抓取、证据不足时硬生成权威结论。

### P08 — 多文档 RAG

目标：支持至少两份真实文档的索引、检索、跨文档问题与引用。
实现：Docling 解析、Chunk/来源位置、Embedding、Chroma 本地索引；统一 `search_knowledge` 工具；答复引用稳定证据 ID。先向量检索基线；复杂 Hybrid/Rerank 如无评测收益则不加。
局部测试：本次 Parser、索引、查询、引用链路和少量有金标的 QA；解析失败和无证据拒答。
参考：DeerFlow 的文件/工具/Skills 接口；RAG 内部独立实现。
不做：PostgreSQL/pgvector、扫描件 OCR、百万文档支持。

### P09 — 发布与真实演示

目标：形成求职可展示的完整应用。
实现：Web 任务进度与文件体验完善、Docker Compose 单机运行、README 实际操作、成本/Token 记录、简单评测脚本、源码归属。
局部测试：P09 新增部署/界面，以及三条完整业务 Demo（Research、RAG、文件任务）。**不自动运行历史全部测试**；是否做全量套件另由用户决定。
验收：真实产物可访问，日志/模型/版本/失败限制可核对，不伪造测试数字。
参考：上游 Web 组件与 Runtime 契约。

## 5. Codex 执行规则：让本地 AI 用最少上下文开发

每次仅交给 Codex：
- 本次任务 ID 与验收要求；
- 本项目当前涉及的少量源码/测试（通常 2–5 个文件）；
- 对应 DeerFlow 1–3 个明确参考文件；
- 当前真实功能摘要（本文件末尾进度区和本阶段提交）。

先说明业务主流程，再选择框架/实现，再完成最小主链，然后处理本次功能的边界。新技术第一次出现时，说明“是什么、为什么现在引入、核心机制、替代方案”；不要为了美观创建空模块或无用设计模式。

完成后必须报告：**改动文件、真实运行命令、仅本次改动的测试及结果、未测试范围、Git SHA、发现的问题、下一步依赖**。阶段完成标记 PENDING_REVIEW，等待用户与 Codex 审查；用户明确说开始下一阶段才继续。

## 6. 决策与风险（本文件集中维护，不再另建决策/测试文档）

**已固定：** 独立新建项目、模块化单体、Python/FastAPI/LangGraph、React/Vite、SQLite、少量 Tools/MCP/Skills、Docling+Chroma、P00–P09 顺序、局部增量测试、逐阶段审核。

**可依据事实调整：** 锁定的具体依赖小版本、首个可用模型、联网搜索供应商；调整要写出触发原因与替代方案，不得影响架构主线。

**需警惕：** Run 状态不等于 Checkpoint；Sub-Agent 不会因为父任务落库就自动精确续跑；本地文件路径映射不是不可信代码沙箱；网页/PDF/MCP 返回不能作为高优先级指令；编排越复杂不代表任务成功率越高。

**重要取舍：** 没有当前业务/实测瓶颈，不引入 Redis、RabbitMQ、PostgreSQL、K8s、多租户、复杂权限和全能 Coding Agent。

## 7. 当前进度账本

| 阶段 | 状态 | 说明 |
|---|---|---|
| 项目范围与实施方案 | CONFIRMED | 本次已整理为 README + 两份主文档 |
| P00 | NOT_STARTED | 下一项：工程初始化 |
| P01 | NOT_STARTED | 最小 Agent |
| P02 | NOT_STARTED | 运行服务/薄前端 |
| P03 | NOT_STARTED | Workspace |
| P04 | NOT_STARTED | Plan/Sub-Agent |
| P05 | NOT_STARTED | MCP/Skills |
| P06 | NOT_STARTED | 上下文/可靠性 |
| P07 | NOT_STARTED | Research |
| P08 | NOT_STARTED | RAG |
| P09 | NOT_STARTED | 部署/评测 |

更新格式：`日期 | 任务 ID | 变更摘要 | 只测当前哪些内容/真实结果 | 未测范围 | Commit SHA | 用户审核状态`。进度事实只写在这里，不另建重复的 PROGRESS、TEST_PLAN 或 Codex 规则文档。
