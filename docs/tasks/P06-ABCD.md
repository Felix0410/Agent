# P06-A/B/C/D · 预算、上下文压缩、取消与恢复 — Codex 逐文件编码合同

> **设计态 READY_FOR_CODE，尚无 P06 业务代码。** 用户于 2026-11-06 提出“已提交，设计 p6”，P05 的 A/B/C/D 远端提交确已核对；P05 仍待手动验收。本文必须在用户明确启动代码实施后交给本地 Codex。执行 A→B→C→D，**每子项单独测试、同步 React、提交 Git SHA**，关键失败停止，不进入 P07。  
> Repo `Felix0410/Agent`；P06 Branch `feat/p06-context-budget-cancel`；唯一详细合同：[docs/DEVELOPMENT.md P06](../DEVELOPMENT.md)，工程规范 [AGENTS.md](../../AGENTS.md)。不要自行设计大规模服务或新 Agent while 循环。

## 0. 初始化和签名验证

1. `git status -sb`、`git log -8 --oneline`、`git branch -vv`，确认基线为 P05 全量代码；保护未提交文件/.env/业务库和用户 Workspace，禁止 `reset --hard` / `clean` / force push / 自动合并 main。
2. 准确定位现有 `backend/src/minideerflow/runtime/{db,models,repository,runner,streaming,task_registry}.py`、`agents/{lead,context,state}.py`、`agents/subagents/{executor,dispatcher}.py`、`tools/{executor,registry,file_tools}.py`、`workspace/service.py`、`frontend/src/{api/runtime.ts,components/RunStatus.tsx,components/ChatPanel.tsx}`。不要覆盖 P05 Guard、P04 write_todos Command 或 P03文件安全。
3. 用本地已锁定依赖和 Fake Model 检查 `AgentMiddleware.awrap_model_call(request,handler)` 的真实返回类型、`AIMessage.usage_metadata`、`SummarizationMiddleware` 的 `RemoveMessage/REMOVE_ALL_MESSAGES` 消息更新与 `awrap_tool_call` 的 Command/ToolMessage 顺序；**先验兼容性**。若不同于文档，提出最小兼容方案并记录，不能绕过 Framework 或伪造 usage。
4. 初期只使用临时业务 SQLite/SQLite Saver、`tmp_path` Workspace、Fake Provider；没有真实模型时不得假装进行了真 Token 使用测试。必要的真实模型 Smoke 仅用合成文本、记录预算限制以节省额度。P05 本地 MCP 进程默认关闭；测试需显式启动时仅用已批准的只读 sample。

## A · RunBudget/Usage/页面用量

| 文件 | 具体实现 |
|---|---|
| `runtime/budget.py`（新） | `RunBudget`、`RunBudgetTracker`，Run 开始 `time.monotonic()` deadline；父+child+摘要共享锁与 max_model_calls=40 / max_tool_calls=30 / max_elapsed=600 / estimate_input_limit=120000；模型工具请求之前原子预留，超限 `BUDGET_EXCEEDED`，任务失败也计数，不虚构真实 Token |
| `runtime/usage.py`（新） | `UsageRepository` 与 `RunUsage/UsageCall`；一次模型调用唯一 invocation ID 防止模型 stream chunk/汇总重复计费；provider null vs estimate、parent/child/summary来源、elapsed_ms、计数和摘要/外置累计统计 |
| `runtime/db.py` | `run_usage` + `usage_calls` 增量 DDL、run id FK / 调用唯一索引；为 C 的 `cancel_requested_at` 实现准备幂等迁移机制，但 A 不开启 cancel API |
| `agents/middleware.py`（新） | `UsageBudgetMiddleware` 基于锁版 `awrap_model_call`，预扣→执行→记录单次最终 AIMessage/provider usage，失败也记录计数；无双计数、不修改模型输出；child 复用同一个 Tracker |
| `tools/executor.py` | 在现有 `ToolGuardMiddleware` 中以最小代码统计 ToolCall 总数/时间/结果；权限/Schema/timeout/ToolMessage/Command 原有行为不变 |
| `agents/context.py`、`agents/subagents/{dispatcher,executor}.py` | 父 `AgentRunContext` 和 ChildContext 都带同一 Tracker + UsageRecorder，通过冻结 dataclass 默认可选字段兼容旧 tests；child model 也安装计数 Middleware、不增加任何工具 |
| `runtime/runner.py`、`main.py`、`config.py` | Run 开始真实装配 Tracker/UsageRepository，父时限默认600且不可超过600，旧 P01 单轮45秒；Run 结束保存聚合，不阻断正常语义，日志脱敏 |
| `api/runs.py` | GET `/api/runs/{run_id}/usage`，未知 Run404，无调用时实际 provider Token 应 NULL |
| `frontend/src/api/runtime.ts`、`components/UsagePanel.tsx`、`RunStatus.tsx`、`ChatPanel.tsx` | 当前和历史 Run 显示模型/工具调用数量、实际与估算 Token、时长；Run 完成和刷新后 GET 用量；SSE `budget_updated` 只携带统计值，展示“不支持 Provider 统计”而非0费用 |
| `tests/test_budget.py`、`test_usage.py`、`test_budget_demo.py` | Fake 验证共享预算、原子并发计数、Provider usage与 estimated 分开、未返回 usage=unknown、持久化重启、ToolCall IDs、历史 Run/Thread 归属与假模型正常终结 |

**A验收**：`model_calls`、`tool_calls`、provider/estimate、`elapsed_ms` 真实 SQLite；刷新页面和数据库重开可查询；模型 Tool Guard 和 Todo Command 保持；子 Agent 不得绕开父 Run 预算；旧 P01 不能误用 P06 Tracker。根据受影响范围运行 `test_budget/test_usage/test_runner/test_subagents/test_tool_guard/test_todos/test_planning_demo`，`uv run ruff check src tests`、`uv run ruff format --check src tests`、`npm run build`。成功后独立提交 `feat(p06-a): track shared run budget and provider usage` + 真实测试记录，继续 B。

## B · 工具结果外置 + 安全旧对话压缩

| 文件 | 具体实现 |
|---|---|
| `tools/output_budget.py`（新） | `ToolOutputBudgetMiddleware.awrap_tool_call` 真 handler返回后检查：<=12KiB 保留；P04 Command 原样、失败 ToolMessage 原样；大的普通成功 ToolMessage 生成 **1KiB预览+可追溯file_id/artifact_id**，保留 ToolCall ID/status；原 `read_text(file_id)` 指向已有登记 file ID 优先避免重复创建；其它无来源文本用 P03 write_text 安全登记新 Artifact；Child 不写文件 |
| `agents/context_manager.py`（新） | `ContextManager.prepare/partition/build_summary`：预测每次 model 输入使用保守确定性估计；soft12k、hard18k，保留最近6条完整交互/最新用户目标和所有不完整工具组合；旧完整回合摘要，真实 file/artifact IDs 从注册表/已保存 Graph/SQL 单独保护，不相信摘要模型凭空发明 ID |
| `agents/middleware.py` | `ContextCompactionMiddleware` 和 ToolOutput 的顺序，与 P05 Guard/Usage 中间件共存；优先锁版官方 SummarizationMiddleware 的消息删除/Checkpoint 接口，无法满足 Todo/成对 ToolMessage 的保护时做最小官方状态更新 hook；摘要模型须计入同一 Tracker |
| `agents/state.py`（必要时） | Graph state 中用于摘要文本的字段（例如 `context_summary`）与 P04 `todos` 区分，不能用 reducer 重复追加；旧 Todo 字段不修改 |
| `agents/lead.py`、`runtime/runner.py`、`runtime/streaming.py` | 装配 Middleware，Graph 经压缩后仍 `astream` 正常 ToolMessage ID 追踪、最后回复判定；旧历史 Run 的 SQL 不因 Graph 压缩删除 |
| `workspace/service.py`（必要时最小复用） | 只走现有 `write_text`/已登记 file ID/下载 API，绝不读写宿主机绝对路径或覆盖旧产物，不做第三套文件存储 |
| `frontend/src/api/runtime.ts`、`components/UsagePanel.tsx` | `context_compacted`、`tool_output_externalized` 事件的真实统计显示；刷新仍读 `GET usage`，不展示私有文档正文 |
| `tests/test_context.py`、`test_output_budget.py` | 8+轮历史/并发 ToolMessage、20KiB/64KiB UTF8、中英文、错误/Command、SQL/Checkpoint、Tool Trace/Artifact sha、Thread隔离/文件配额/摘要失败/Provider上下文预算保护 |

**B验收**：模型上下文规模实际缩小、最近消息/当前目标/真实 Todo 不丢，所有 AI tool_calls 与 ToolMessage ID 成对，复问仍能准确引用早期文件 ID（文件身份必须服务端验证）；工具过长结果不进入模型历史全文/Run trace，原内容可由下载 Artifact 或原 file ID 追踪。若原文件大且当前没有分块阅读工具，须如实记录单次读取仅预览的能力边界，不能声称可以用该短预览完成整个文件精读。测试 B + P03文件/P04Todo/P05 Guard消费者、Ruff、frontend build，独立提交 `feat(p06-b): compact safe history and externalize large tool outputs`。

## C · POST Cancel、Worker与Child回收、重启核查

| 文件 | 具体实现 |
|---|---|
| `runtime/db.py` | **真正**检查 PRAGMA table_info 后幂等 `ALTER TABLE runs ADD COLUMN cancel_requested_at TEXT`，不能仅改旧 CREATE TABLE IF NOT EXISTS；不重建 status CHECK |
| `runtime/models.py`、`runtime/repository.py` | RunDto 新增 `cancel_requested_at`；`request_cancel(run_id)` SQL 原子状态机，CREATED→CANCELLED、RUNNING仅置时间、终态重复返回现状；`complete_cancel` 与 `complete_run(SUCCEEDED)` CAS 保证取消先写入后不会再标 SUCCEEDED；FAILED/OUTCOME_UNKNOWN 标 Thread需恢复，Graph成功先赢则cancel不得撤销 |
| `runtime/cancellation.py`（新） | `RunCancellationRegistry` 管理 run→Graph asyncio.Task/信号/in-flight 未确定标志；不管理 worker 生命周期；用户取消与服务 shutdown 语义区分；`register(run_id,task)` 后立即复核 SQL cancel_requested_at，覆盖 RUNNING 已写但 Graph Task 尚未注册时请求先到的竞态 |
| `runtime/runner.py` | worker创建/await单 Run Task；CREATED已被取消时跳过队列tombstone；RUNNING 收到显式取消先置数据库标记再只取消对应 Graph Task，await P04 child + P03文件shield + SQLite落库后才发终态；延续现有 Worker 不杀整个队列 |
| `tools/executor.py`、`agents/middleware.py` | 下一次 Tool/Model 之前检查共享取消信号，不使取消后继续新增副作用；取消已启动的外部write且结果未知时标保守 outcome_unknown，**不自动重试** |
| `api/runs.py` | POST `/api/runs/{run_id}/cancel`，无请求体，202表示取消请求接受、200表示已经终态，404不存在；返回实际 `run_id/status/cancel_requested_at` |
| `frontend/src/api/runtime.ts`、`components/ChatPanel.tsx`、`RunStatus.tsx` | 活动 Run 显示“取消运行”；点击后立即停止重复提交（不是马上把Run显示CANCELLED），页面展示“正在取消”，最终以GET实际终态覆盖；SSE `run_cancel_requested`、`run_end`，断开 SSE 不等于取消；轮询从180增加到720次 |
| `backend/tests/test_cancel_recovery.py`、`test_budget_demo.py` | queued CREATION/active运行、重复取消、取消vs成功竞态、child/文件写入清理、shutdown中断不伪造CANCELLED、重启未知副作用不重试、Thread恢复、SSE事件按DB真实顺序 |

**C验收**：取消 queued Run 后它**从不调用模型**，队列 worker 继续处理其它 Run；取消 running 后子任务/已发起操作安全收尾，事件不能先于数据库伪称终态；重复请求无额外执行；重启后的 Run/Task 标志符合P02/P04原逻辑；历史旧 SQLite 能直接启动并新建取消，不丢既有 rows。局部 cancel+Runner/repository/runsAPI/task registry/SSE用例，Ruff与frontend build；独立提交 `feat(p06-c): add idempotent run cancellation and safe recovery`。

## D · 端到端长会话和异常收尾

1. 构造20–64KiB合成文件和8+轮对话（优先 Fake 触发阈值，节省真实Token）：测完整问答/工具/Child→上下文缩减、Todo未完成状态、真实 file_id/Artifact ID 不变，Graph Checkpoint 确实存摘要后的状态；Usage GET 与 SQL一致，provider null 与 estimated 无混用。
2. 启动 2 个并行Run和至少1个受限 Child（Fake慢调用）：取消其中 Run，验证另一个继续工作、子代理全部收尾、Run终态与“正在取消”状态真实准确。重启应用：历史答复/Usage/Artifact仍可查，遗留 RUNNING/CREATED 标记失败并保守处理有副作用结果。
3. 组合真实 P05 本地 MCP + Skill（只有用户显式配置），MCP 掉线不破坏内置工具；取消在MCP ToolCall过程中不能自动重试未知动作。旧 P01/02/03/04/05 受直接修改影响的接口验证，不做无关P07–P09扩展。
4. 用隔离端口、两库及 Workspace、Fake/可用时真模型执行浏览器短 Demo：UsagePanel、真实长工具结果回执、压缩次数、Cancel按钮与最终GET状态、刷新/跨Thread都正确。真实模型若用量不足以触发压缩，不得强行消耗高额Token，通过可调低的测试阈值或Fake验证压缩；报告具体触发条件。
5. `uv lock --check` / `uv sync --locked --group dev`、局部 `pytest`、Ruff、`npm ci && npm run build`；准确写 A/B/C/D commit SHA、各自测试通过数、是否使用真实模型、已知限制、Push成功与否。不自动标 P02–P05 ACCEPTED，不进入P07。最终 `docs/progress/P06.md` 为 `PENDING_REVIEW`，等待用户亲自Demo。

## 统一阻塞条件

- P05 `write_todos` Command 丢失或 ToolMessage ID 变化；Provider usage重复计数/估算装作实际；超限仍发起新调用；摘要误删当前目标/未成对 ToolCall；用户取消标记入库后仍出现新Tool/Model Call；外部未知结果自动重试；旧 SQLite 增列损坏历史；P04 child逃逸/绕开共享预算；长正文因错误拦截无法找回。任何一条成立就停止当前实施并报告最小复现，不能降低安全要求。

## 交付报告

向用户统一报告：A/B/C/D 独立 SHA 与 Push 结果、修改文件、每段局部测试与UI更新、运行默认预算与Token出处、摘要真实触发和Checkpoint证据、长工具输出及原始内容引用、取消队列/Graph/Child/Restart证据、未验证事项、手动Demo操作；只有真实执行的命令才能称“passed”。
