# P04-A/B/C/D · Todo + Sub-Agent 连续编码任务书

> **状态：READY_FOR_CODE / 尚未编码**。2026-11-06 用户要求“设计 P4”，本文是严格实施任务合同，**不是已经获准自动运行 Codex 的记录**；用户确定开始编码后，允许 A→B→C→D 一次连续执行，阶段内部必须分别测试、提交，关键阻塞立即停止。  
> 原则上只读：[AGENTS.md](../../AGENTS.md)、[DEVELOPMENT.md · P04](../DEVELOPMENT.md)、[P04 progress](../progress/P04.md) 和当前 P03 代码；不要让 Codex 自行设计新架构。
>
> 开发分支：`feat/p04-planning-subagents`，起点是 P03 完整实现；P02/P03 仍为 `PENDING_REVIEW`，不得伪称手动验收完成。

## 0. 编码前核验（禁止跳过）

1. `git status --short --branch` / `git log -8 --oneline` / `git branch -vv`，核对远端 P04 文档与 P03 完整代码。不能 reset/clean/force push/覆盖用户本地修改。若本地停留 P03 分支，在确认干净且用户授权后切换 `feat/p04-planning-subagents`；**不能从 main 编码**。
2. 从 `backend/` 的已安装环境运行最小兼容性样例：`AgentState` 扩展 `todos`、`create_agent(state_schema=P04AgentState)`、`@tool` + `ToolRuntime[AgentRunContext,P04AgentState]` + `Command(update={"todos":...,"messages":[ToolMessage(...)]})`、`create_agent` 独立子代理 `ainvoke`、`context=` 注入。用 FakeChatModel 和临时 Saver，不耗费真实模型额度；**无法实测 ToolRuntime/Command 就暂停，不在本地 AI 的想象中修改合同**。
3. P01 单轮 `run_agent_once`、P02 `RunService/stream_agent/EventBus/RuntimeRepository`、P03 `WorkspaceContext/file_tools/FilesPanel` 是基础实现；任何向 P04 的适配只做可选参数与局部拆分。P03 已有 read/write 的权限检查，子 Agent 只注册 list/read，不复制第三套 Workspace。
4. 使用本地 `backend/.venv` / uv locked sync，测试数据库、Workspaces 使用临时目录，隔离 `.env`；不提交本地默认业务库、密钥或用户上传内容。Ruff/TS Build 每段执行。

## A：Todo 写入真实 Graph State + SQL + 最小前端

**文件到实现的逐一对应**：

| 文件 | 交付函数与限制 |
|---|---|
| `agents/state.py` 新 | `TodoItem(todo_id,title,status,position)`、`P04AgentState(AgentState)` 的 `todos` 字段，额外字段不在模型工具 JSON 中；状态替换而非 append |
| `agents/context.py` 新 | 冻结 `AgentRunContext(WorkspaceContext)`：本阶段仅 `todo_service/event_sink`（为 B/C 预留 task_dispatcher，可选依赖）；父真实 run/thread 赋值，保留 P03 isinstance 语义 |
| `runtime/db.py` 改 | 新增 `run_todos`、`subtasks` DDL + 约束与索引，不破坏老表；为 B 建 subtasks 表但 A 不伪造 task 行 |
| `runtime/plan_repository.py` 新 | `replace_todos(run_id,items)`：事务确认 Run RUNNING、原子比较老 id 与状态/上限、保留 position；`list_todos(run_id)`；`list_subtasks(run_id)` 可在 A 空返回；GET Run 404 规则复用原 Repository |
| `runtime/plan_service.py` 新 | `write_todos(context,items,runtime_state)`：验证 ToolCall 批次冲突→SQLite 提交→可选 `todo_updated` 事件回调；返回真已存储列表；公共错误统一 `TODO_*` |
| `tools/todo_tool.py` 新 | `write_todos(items,runtime:ToolRuntime[AgentRunContext,P04AgentState])->Command`。正常 Command 同时更新 `todos` 和匹配 `runtime.tool_call_id` 的 ToolMessage；失败以仅含安全 ToolMessage 的 Command 或稳定 Tool error 形式返回，不更新 todos；工具 JSON Schema **只有 items** |
| `agents/lead.py` 改 | 可选 `state_schema`/P04 专用提示词后缀；默认 P01/P02/P03 工厂行为不变，P04 应教模型简单问题直接回答、复杂目标先写 Todo 并据真实执行更新 |
| `runtime/streaming.py` 改 | 可选 `initial_state_extra={"todos":[]}` 合并当前 HumanMessage 输入；只在 P04 Run 使用；保留原消息采集/ToolTrace 流式逻辑；不要把历史 run 的 todos 带入新 Run |
| `runtime/runner.py` / `main.py` 改 | 在 P04 持久 Run 的实际 context 下装配 `write_todos`，创建 PlanRepository/Service 并注册可信依赖；P01 无状态工具继续只有 calculate |
| `api/tasks.py` 新 | `GET /api/runs/{run_id}/todos`；可顺带实现 GET subtasks 空列表，后续 B 补真实内容，200/404 明确 |
| `frontend/src/api/runtime.ts` / `components/TodoPanel.tsx` / `components/RunStatus.tsx` / `components/ChatPanel.tsx` | Run 初始化 GET Todos；SSE `todo_updated` 即时覆盖同 Run Todo 快照；刷新/切换/结束 GET 权威历史；无计划显示“未使用规划” |
| `backend/tests/test_todos.py` / `test_tasks_api.py` | Fake + 临时 SQLite Saver/业务库；测试真实 ToolRuntime→Command→Checkpoint 和 HTTP/UI 数据契约 |

**A 最小可运行验证**：现有模型仍能普通问答、计算、P03 文件工具；Fake 模型直接发两个 `write_todos` ToolCall（不同图步骤），修改同一 todo_id status/标题后数据库和 State 只有一条；SSE 真实更新；另起 Run 后新 Graph State.todos=[]，上次 Run 的 GET 历史不丢。重复并行写→冲突，失败不更新。每段 test_todos + test_tasks_api + 直接影响的 P02 tests / Ruff / TS build。通过后 `feat(p04-a): persist todo state and run snapshots` 独立提交 A SHA，前端真实可看计划，**无需先实现子代理**。

## B：串行真实子 Agent、角色工具白名单、历史任务 UI

| 文件 | 具体行为 |
|---|---|
| `agents/subagents/config.py` | 常量 `general/research` 两 Spec（角色 prompt、工具名 allowlist、每 child 35s、recursion_limit14）；research 只能基于上传材料不联网 |
| `agents/subagents/models.py` | `TaskStatus/TaskRecord/TaskResult` Pydantic/Enum；完整摘要最多1600，`truncated` 标记，来源文件ID从真实工具消息索引 |
| `agents/subagents/executor.py` | `execute_child(spec,description,child_context,model_factory)` 单次独立 `create_agent(checkpointer=None)`，新 `{"messages":[{"role":"user","content":description}]}`，不复制 parent messages/id/Checkpoint；按实际返回消息验收工具结果和最后 AIMessage，安全摘要和来源 ID |
| `agents/subagents/dispatcher.py` | `dispatch(parent_context,agent_type,description,todo_id?)`，角色白名单与父允许工具交集；创建 DB 任务和真实 child 上下文；成功/失败写任务终态并返回 ToolMessage 可以序列化的 JSON/ERROR；B 阶段一次仅执行一个 |
| `tools/task_tool.py` | `task(agent_type,description,todo_id=None,runtime=...)`，模型 JSON 只能包含上述三个业务字段，不能包含 run_id/thread_id/权限；ToolRuntime 校验并调 dispatcher；不允许二次委派 |
| `runtime/plan_repository.py` | `create_subtask/transition_subtask/list_subtasks/reconcile_orphaned_subtasks`，所有状态更新受业务 SQLite 事务和真实 run/thread 约束；主 Runner 运行中才能创建 |
| `runtime/runner.py` / `agents/context.py` | 注册父 task，构造 Trusted AgentRunContext；ChildContext 只保留 P03 基础身份与可读工具；P01 single-turn 不能调用 task |
| `api/tasks.py` / `frontend/src/api/runtime.ts` / `components/TaskPanel.tsx` | GET Subtasks 持久化，RunStatus/ChatPanel 可展示每个真实子任务、角色、摘要、来源 file ID，失败有明确状态；仍无手动派发按钮 |
| `backend/tests/test_subagents.py` / `test_tasks_api.py` | 真 ToolRuntime→真实 Child Agent/Fake 模型、P03 权限/ToolMessage 结果、错误码与消息隔离 |

**B 必测**：子模型看不到父完整历史；子 Agent schema 没有 task/write_todos/write_text；general 有 calculate、research 无 calculate 也无网络搜索；读当前 Thread 真实 file_id，别的 Thread 文件 ID 拒绝；伪造身份/缺可信 Context 报错；子任务短摘要来自实际 child AIMessage，不能从模型文案中猜 source UUID；不能因子工具失败自动标 COMPLETED 且输出“已处理”。提交 B 后按用户对连续执行的授权继续 C。

## C：有限并发、超时、异常和 SSE

| 文件 | 行为 |
|---|---|
| `runtime/task_registry.py` 新 | per Run Semaphore(3)，同 Run 包括失败不超过4次委派，全部 Task 强引用；超时 `asyncio.timeout(35)`、正常完成/timeout/cancel/异常均收尾并释放；禁止生成无约束后台离线任务 |
| `agents/subagents/dispatcher.py` | 并发 `dispatch` 互不写父 Graph State；每 child 唯一 Task ID，Task SQL 从 PENDING→RUNNING→终态；父 Run 超时/关闭先确认 child Task 都取消回收 |
| `runtime/runner.py` / `config.py` | 独立 `run_timeout_seconds=150` 供持久 P04 复杂 Run，P01 单轮45秒保持；父 Runner 终态前 await 清理 child；永久无后台遗留。对 settings 值设上界和测试 |
| `runtime/events.py` / `api/runs.py` | 不换 EventBus 或 SSE 格式，新增事件仍用原 id 和缓冲。plan_service/dispatcher 只在 SQL 成功后 `publish`，事件发不出不反向伪造业务失败 |
| `runtime/plan_repository.py` / `main.py` | 启动对遗留 PENDING/RUNNING 子任务标 FAILED/SUBTASK_INTERRUPTED；不能自动重放已可能产生外部副作用的 child |
| `frontend/src/api/runtime.ts` / `components/TodoPanel.tsx` / `TaskPanel.tsx` / `ChatPanel.tsx` | 注册 todo_updated/subtask_created/started/completed/failed 的 EventSource 自定义事件；同一 Run 快照覆盖，断线/Run结束 GET Run+todos+subtasks；切换清理订阅/历史不丢 |
| `tests/test_task_registry.py` / `test_subagents.py` / `test_tasks_api.py` / `test_events.py` | Fake 并发峰值3，第四个排队、总次数4上限，第5拒绝；child 超时、parent timeout、worker shutdown、SSE不串事件，重启孤儿标记 |

**C 固定含义**：`task` 是同步等待子代理结果的工具调用；即使 Python 内部是 asyncio，也不是能在 parent 图结束后继续跑的独立任务。父图失败/取消先回收所有已登记子代理。多 child 并行可以异步执行，但所有子代理**没有父 Checkpointer 的写权限**。事件 `todo_updated` 和各 `subtask_*` 均来自真实 SQL 状态而非模型输出。提交 C SHA 后才执行 D。

## D：完整真实 Demo、异常与重启、交付记录

1. 假模型/临时资源完整链路：上传 notes.md → 父 Agent 第一步调用 write_todos → 第二步同一个 AIMessage 调用两个 task（角色 general/research）→ 子代理在自己消息列表中读到当前 Thread 已上传内容，不见父完整历史 → 父收到两条有效 ToolMessage 后更新 todos → 用 P03 write_text 创建 summary.md → 校验真实 bytes、Artifact SQL/SHA、Run 终态和 SSE tool trace → 前端依次可见真实 Todo、两条子任务及产物。
2. 简单问答/计算不强制 write_todos/task；单轮 P01 和 P02/P03 原 API 兼容；不同 Thread 和同 Thread 不同 Run 的历史 Todo/Task 隔离；刷新/重启只从 SQLite 权威 GET 恢复历史，不依赖 SSE 10分钟窗口。遗留子任务重启后为 FAILED/SUBTASK_INTERRUPTED，父遗留 Run 沿 P02 保守恢复。
3. 故障注入：5th delegate、无效 role、超长描述、Graph final 为空、Child tool error、超时、取消、parent shutdown、并发的 write_todos 冲突；不可泄露另一 Thread 或宿主路径，真正未执行的任务不得 COMPLETED。
4. 使用临时 Fake 模型运行 HTTP+浏览器，证据截图/日志只记结果不记用户文件或密钥；本地有支持 Tool Calling 的可用真实模型时再独立验证一次复杂 Todo/两个 Task（模型可能不执行计划，必须真实说明）、上传合成文本与实际下载，不能用 Fake 代替真模型。还要单独记真实模型调用额度/是否阻塞。
5. 后端局部测试 P04新增测试及本次直接改的 P02/P03 消费者；`uv run ruff check src tests` / `uv run ruff format --check src tests`；前端 `npm ci && npm run build`；不做无关全量 P05–P09 回归。所有实际命令和结果分别写入 `docs/progress/P04.md`，B/C/D 分别有独立 SHA，最终状态 `PENDING_REVIEW` 供用户亲自验收，**不得自动进入 P05**。
6. 中文注释：每个非平凡类/函数写精简 docstring；状态转移、同 Run 并发、context 和 ToolCall ID 匹配、父子取消回收按 `# 1./2./3.` 中文说明；Tool Schema 的英文描述不能为了中文化导致模型调用协议变化。

## 最终统一汇报标准

每段 A/B/C/D 的 Commit SHA、文件/职责、前端新增真实能力、局部测试命令/数量；Todo Checkpointer 与 SQLite Run 快照的一致性、子代理隔离/工具白名单/并发/超时/取消/真实工具轨迹；模拟和真实模型的结果分开；剩余风险和用户可执行的 P04 Demo 操作；Git 远端推送若失败据实说明，不 force push、不伪造。真正未执行的事项必须列为未验证。
