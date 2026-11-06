# P02-B/C/D · 连续开发与统一交付任务书

> **状态：READY_FOR_CODE · 批量执行授权（2026-11-06）**  
> 依据：`docs/DEVELOPMENT.md` 中 P02 正式实施合同、`docs/progress/P02.md` 的真实 P02-A 记录。用户明确允许本次将 **P02-B、C、D 一起设计并连续完成**。A 的最终人工验收可并入 D；这不代表 A 的未实测项目自动通过。  
> **Codex 执行方式**：同一次会话顺序实施 **B → B 局部验证/提交 → C → C 局部验证/提交 → D → 最终验证/提交**；不需要三次人工批准，但任何关键验证失败、协议不兼容、无法安全提交或无法满足已确定合同都必须停止并报告。**禁止跳过测试、把旧测试记录当本轮结果或提前开始 P03。**

## 0. 起点：只接续现有 P02-A

从仓库本地真实工作树开始，先检查 `git status --short --branch`、`git log -8 --oneline`、`git branch -vv` 和远端 `feat/p02-runtime-web` 的差异。不要 reset、clean、force push、覆盖未提交的私有文件或盲目 `git pull`。用户已告知 A 已提交；远端可见 P02-A 实现（`fd120e5d...`），包括：
- `runtime/db.py` 的 `RuntimeDatabase`、事务 Lock、SQLite 外键、WAL、部分唯一索引；
- `runtime/repository.py` 的 `RuntimeRepository.create_run/get_run/list_runs/transition_run/complete_run/reconcile_orphans` 与 `RepositoryError`；
- `runtime/models.py` 中 `RunStatus/ThreadDto/RunDto/RunEvent/RunAccepted`；
- `runtime/checkpoints.py` 的 `open_checkpointer` 与 `thread_config`；`agents/lead.py` 的 optional Checkpointer；
- `main.py` 的 lifespan（DB → Saver → 孤儿核查）；
- `api/threads.py` 的 Thread 创建、列表及历史 Run 查询；
- `frontend/src/components/ThreadList.tsx` 内部持有 `selectedId`，已经调用真实 Thread API；`frontend/src/api/runtime.ts` 有 Thread/Run DTO；
- P01 `agents/service.py` 的 `run_agent_once`、`ToolTrace`、`validate_message`、`agents/lead.py`、`core/model.py`、`tools/calculator.py`、`api/demo.py`；
- 根目录 `AGENTS.md` 强制中文关键注释、长逻辑按 1、2、3 分段。P02-A 已在本地验证 22 个新测试和 67 个受影响测试，但不作为 B/C/D 的测试证明。

基于实际签名添加代码，不平行复制 Repo、Checkpointer、ModelFactory。注意仓库可能仍有根目录 `pyproject.toml/uv.lock`：这不是本期要使用的第二套 Python 环境；不要擅自覆盖或删除。Python 工作目录始终是 `backend/`。

## 1. 统一目标与职责边界

用户在 React 选择 Thread → 发送消息 → HTTP 202 立即返回 RunAccepted → 有界后台 Task 执行同 Thread 的 `create_agent` → `AsyncSqliteSaver` 保留上下文 → 通过 LangGraph `astream` 发送流式文本/工具调用 → SQLite 原子提交最终 Run 状态与真实工具结果 → SSE `run_end` → Web 通过 `GET Run` 核验权威状态；刷新或重启能从 `list_runs` 恢复历史，已成功保存的 Checkpoint 可继续追问。

**禁止**：自行实现 Agent while 循环、从 Run 表拼模型历史、在 Router 中同步等待模型完成、引入 Redis/RabbitMQ/ORM/WebSocket/Redux、写假 Token/工具轨迹、将 `.env` 或 SQLite 数据提交、实现 P06 取消/自动恢复、跳到 P03。

### 1.1 文件清单（必须对号入座）

| 文件 | B | C | D |
| --- | --- | --- | --- |
| `backend/src/minideerflow/runtime/runner.py`（新） | 有界 Queue、2 workers、HTTP 提交与终态事务、shutdown | 注入 EventBus 并真实 publish | 重启/关闭、超时与失败收尾联调 |
| `backend/src/minideerflow/runtime/streaming.py`（新） | 统一 Graph 执行与本轮最终答复/真实 Tool Trace | 映射 `astream` 消息 Token/工具开始/结束 | 处理历史隔离、消息重复与版本签名边界 |
| `backend/src/minideerflow/runtime/events.py`（新） | 不创建假 EventBus；B 通过轮询即可 | `EventBus` 订阅/缓冲/缺口/过期 | 复核终态和重连 |
| `backend/src/minideerflow/api/runs.py`（新） | POST Run、GET Run | GET events SSE + Last-Event-ID | 错误一致性复核 |
| `backend/src/minideerflow/main.py`（改） | 生命周期挂载 Runner、启动 workers、注册 Run Router | EventBus 注册/关闭、SSE | 按反依赖顺序 shutdown、孤儿恢复 |
| `backend/src/minideerflow/agents/service.py`（仅必要时改） | 共用消息验收/工具回执检查，保留单轮 API | 提取可复用解析函数，避免前后两个版本的 ToolTrace | P01 兼容性检查 |
| `backend/src/minideerflow/runtime/repository.py`（仅必要时改） | 只补实际缺失的查询/原子恢复方法 | 不修改数据库协议 | 孤儿/恢复标志/读历史一致性 |
| `backend/src/minideerflow/api/threads.py`（按需） | 原列表与历史接口直接复用 | 无多余接口 | 分页/404 复核 |
| `frontend/src/api/runtime.ts`（改） | `startRun`、`getRun` | `subscribeRunEvents`、SSE 解析/类型 | API 重连异常/状态 |
| `frontend/src/components/ThreadList.tsx`（改） | **提升选中 Thread 状态**到 App 或向 ChatPanel 传可控 selectedId；去掉禁用“P02-B 尚未实现”的按钮，接入可运行聊天 | 将历史、流事件与选中会话一致关联 | 切换、刷新、恢复标志联调 |
| `frontend/src/components/ChatPanel.tsx`（新） | 用户消息、历史 Run、发送、轮询最终状态 | 流式文本、最终覆盖、EventSource 关闭/切换清理 | 刷新历史、错误与交互体验 |
| `frontend/src/components/RunStatus.tsx`（新） | 展示真实 CREATED/RUNNING/终态与保存的工具结果 | 展示真实工具开始/结果及错误提示 | 终态/断线/冲突状态展示 |
| `frontend/src/App.tsx` / `styles.css`（改） | 组合已有 P01 调试区与 Thread 聊天，不重建页面 | 流式区域、响应式布局 | 收尾、能力文案与页面恢复 |
| `backend/tests/test_runner.py`、`test_runs_api.py`（新） | 202、队列、同 Thread 冲突、任务终态、失败/超时、同 Thread 多轮 | 扩展 SSE 真实测试 | 重启/生命周期 |
| `backend/tests/test_events.py`（新） | 无 | 缓冲/重连/慢订阅/关闭/过期/事件序号 | 边界复核 |
| `backend/tests/test_checkpoint.py`、`test_repository.py`、`test_lead.py` 等 | 仅直接受影响部分 | 必要时新增对应断言 | 局部兼容，不无边界跑全套 |
| `README.md`、`docs/progress/P02.md` | 更新真实 B 交付与 SHA | 更新真实 C 交付与 SHA | P02 Demo 验收说明、未验证项与最终 SHA |

### 1.2 API 与错误（沿用已批准合同）

- `POST /api/threads/{thread_id}/runs`：JSON `{"message":"请计算 (12+8)*3"}`，合法成功 **202** `{"run_id":"<uuid>","thread_id":"<uuid>","status":"CREATED"}`；响应时**不等待模型结束**。请求空/超长 422，Thread 不存在 404 `THREAD_NOT_FOUND`，已有活动 Run 409 `THREAD_BUSY`，需恢复 409 `THREAD_REQUIRES_RECOVERY`，缺模型配置 **503 `MODEL_NOT_CONFIGURED`** 且不能插入 Run，等待队列满 **429 `RUN_QUEUE_FULL`** 且不能插入 Run。
- `GET /api/runs/{run_id}`：200 `RunDto`，404 `RUN_NOT_FOUND`。其中 status/answer/tool_calls/error_code 来自业务库权威结果，不能从流消息猜测终态。
- `GET /api/runs/{run_id}/events`（C 实现）：`text/event-stream`，未知 Run 404；保留窗口消失 410 `EVENT_STREAM_EXPIRED`；首订阅回放本次 Run 的窗口事件，重连仅从对应 `Last-Event-ID` 之后补发。
- 旧的 `GET /health` 与 `/api/demo/*` 保持不变；`GET /api/threads/{thread_id}/runs?limit=50` 继续按已规定次序显示最近历史。
- 异步执行后的模型失败 **不得反向修改之前的 HTTP 202**：数据库 Run 标为 FAILED，错误码稳定脱敏，并通知前端。原始 Provider 响应/堆栈/Key 不可上送。

## 2. P02-B：有界后台 Runner、Run API 与轮询式 Web

### 2.1 Runner 生命周期与队列

1. `RunService` 由 FastAPI lifespan 只创建一次，持有 `RuntimeRepository`、Checkpointer、Settings、一个 `asyncio.Queue(maxsize=8)`、2 个 worker Task、accepting 标志以及本地准入 Lock；通过 `app.state.runner` 注入 Router。worker 内部每次调用当前 P01 ModelFactory + `build_lead_agent(model,[calculate],checkpointer)`，并用 `thread_config(thread_id)` 限制 Graph 轮次；不可把模型在应用启动时强制初始化（健康/Thread API 无 Key 仍能使用）。
2. **必须原子处理容量与持久记录**：收到 Run POST 后按顺序做输入校验→Thread 存在/恢复/活动状态检查→模型配置前置校验→获取准入锁检查可排队容量→Repository 写入 CREATED→`queue.put_nowait(run_id)`。因为两个步骤分属 SQLite 和内存，无法跨进程原子化，所以 **在同一个准入锁内先预留容量**，后插入并入队；任何入队失败必须立即将 CREATED 转 FAILED，且不可返回 202。保持已存在 Thread 忙的 409 优先于排队满 429。进程内 queue 8 等待 + 2 workers 执行；关闭时拒绝新提交，前端不显示不真实的排队承诺。
3. worker 从 queue 中取 Run：`CREATED → RUNNING` 事务提交后才实际开始 Agent；独立 `asyncio.timeout(settings.model_timeout_seconds)` 限制整轮执行；Graph 的响应和工具消息必须通过标准 `astream`，并用 P01 的 ToolTrace 一致性检验。**不要对整份历史消息提取本轮工具结果**，历史由 Checkpointer 保留；需提取当前 Run 新消息/当前消息 ID 或以最终 Graph State 与运行前快照做边界区分。
4. Graph 正常结束、最后 AIMessage 有效、所有工具调用都有匹配 ToolMessage 后，才调用 `complete_run(...,status=SUCCEEDED,answer=...,tool_calls=...)`。发生超时/上游/图错误，转换为稳定脱敏错误码 `MODEL_TIMEOUT/MODEL_UPSTREAM_ERROR/AGENT_EXECUTION_FAILED`，`complete_run(...FAILED,error_code=...,needs_recovery=graph_started)`；图运行前错误不得误把已有成功 Thread 标成需恢复。失败时不能用部分 token 伪造最终 answer。
5. 任务必须是进程内受管理的 worker Task，所有 Task 有强引用。shutdown 停止准入→尽可能有限地等待任务正常结束→清理未启动排队 Run（FAILED/RUN_INTERRUPTED）→取消超时中的 workers（捕获 `CancelledError` 并回滚/终结未完成 Run，Graph 已开始则标需恢复）→关闭数据库之前确认 Task 已回收。不得先关闭 Saver/SQLite 再取消运行 Task，不留没人处理的异常 Task。已成功/失败终态不能再被后续清理覆盖。
6. Python `asyncio.Queue` 空间检查只保护本地单进程，不能假装分布式容量或进程崩溃后的可靠消息队列；启动现有 Repository 的 `reconcile_orphans()` 负责标记遗留运行中 Run 为 FAILED/RUN_INTERRUPTED。

### 2.2 Graph 数据准确性（B 阶段先收集，C 阶段再 publish）

- 使用 `create_agent(...,checkpointer=app.state.checkpointer)`，真正通过 `astream(input,config=thread_config(thread_id),stream_mode=["messages","updates"])` 运行。检查当前 **LangChain/LangGraph 已锁版本** 实际返回 tuple 的结构；不要照着新版本示例猜字段。
- `runtime/streaming.py` 对 LangGraph 输出构造本轮消息索引；以 AIMessage.tool_calls ID / ToolMessage.tool_call_id 配对，多个工具调用可以返回不同顺序，以实际 ToolMessage 完成顺序生成 ToolTrace；错误内容 `ERROR[...]` 或 ToolMessage.status=error 使 ok=false。
- 最终回答从真实最后 AIMessage 提取，不以 `assistant_delta` 文本拼接为数据库成功答案。Graph 结束后需要用 `aget_state(config)` 或当前本轮的真实最终状态确认**本轮已经产生**终态消息；验证没有未回执工具；普通问答允许无工具。已有 P01 `run_agent_once` 原有 API 不改变。
- 服务与 Stream 转换器共用可抽取的纯函数（工具轨迹和最终答复），但不得为复用而改变旧 Agent 的模型系统提示词、工具描述或工具行为。
- **B 阶段暂不实现 SSE**；前端以有限周期 `GET Run` 轮询刷新，必须有停止条件、会话切换保护、卸载清理、同 Thread 运行中防重复提交。后台执行失败也要停止轮询并显示真正的服务端错误。

### 2.3 B 提交门槛

局部测试至少包含：HTTP 202 快速返回、创建真实 CREATED Run、同 Thread 409、队列满 429 且不遗留 CREATED、缺配置 503 且没有 Run、不同 Thread 并发、CREATED→RUNNING→成功/失败、模型超时、工具失败的轨迹 ok=false、无最终文本拒绝成功、同 Thread 第二轮能从真实 Checkpointer 读取首轮上下文、独立 Thread 不串消息、Runner shutdown 不丢活动 Task。Fake 模型与临时 DB，不消费真实额度。前端 `npm ci && npm run build`，附真实可用的轮询 UI。测试通过后 **提交 B** 并记录 SHA，继续 C，无需人工中途审核。

## 3. P02-C：EventBus、SSE 和实时 Web（不得独立再造 Runner）

### 3.1 EventBus 与控制流程

1. `EventBus.ensure_run(run_id,thread_id)` 在 Run 成功创建后、worker 开始前执行；对每个 Run 用单调递增 sequence 产生 `event_id="<run_id>:<seq>"`；`publish()` **先写入最多 512 条 deque** 再通知订阅者；每订阅者最多 64 条通知；全部动作受同一异步临界区保护，避免“快照回放与实时订阅之间丢事件”。
2. SSE 首次无 cursor 必须明确回放保留的开头事件；如果已有事件早于 buffer 丢失，则返回控制 `stream_gap` 后关闭流，不静默拼接半段。重连 `Last-Event-ID` 只允许格式正确且属于当前 run_id，继续回放 cursor 之后序号更大的事件；cursor 落在已遗失区域返回 `stream_gap` 并终止订阅。不能重放其他 Run、不能让慢客户端无限堆内存。
3. 终态事件缓冲保留 10 分钟，过期后前置检查返回 HTTP 410 + `EVENT_STREAM_EXPIRED`；历史 Graph 和最终 Run 仍可通过其他 API 查询。应用退出可以清理 EventBus 内存，不承诺跨进程 SSE 历史重放。
4. 订阅 slow queue 溢出时不能阻塞 worker / Runner 的 `publish`，向订阅返回 `stream_gap` 并停止；订阅任务结束时取消订阅，不向 Runner 传递取消。服务端提供定期心跳注释 `: ping\n\n`（心跳不计业务事件序列），不把网络保活当 Run 状态。
5. SSE Router 在返回 `StreamingResponse` **前**完成 Run 存在性、过期/cursor 前置验证；实际流按 `id:...\nevent:...\ndata:<RunEvent JSON>\n\n` 格式；设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`。`Last-Event-ID` 缺失时从当前 Run 缓冲头开始；浏览器 `EventSource` 原生自动重连适用，但前端收到 `run_end` 或 `stream_gap` 后关闭连接并 GET Run。

### 3.2 事件来源（只能来自 Graph 消息）

| type | 产生条件和 payload |
| --- | --- |
| `run_start` | 已完成 DB RUNNING 迁移，payload 有 status |
| `assistant_delta` | 真实模型消息的增量文本：`{message_id,text}`；过滤工具调用 chunk、重复历史节点及非文本块；不得混入 ToolMessage |
| `tool_start` | 当前 Run 模型 AIMessage.tool_calls：`{tool_call_id,name,args}`；实际收到完整调用信息后再发 |
| `tool_end` | 同一 tool_call_id 的真实 ToolMessage：`{tool_call_id,name,result,ok}`；允许工具失败 ok=false |
| `assistant_final` | 最终消息验证成功且完整回答已取得：`{answer}`；前端**覆盖**临时 delta |
| `error` | 任务失败稳定错误码与短消息：`{code,message}` |
| `run_end` | DB 已提交 SUCCEEDED 或 FAILED：`{status}`；前端 GET Run 强校验 |
| `stream_gap` | 订阅过慢/历史已缺失：`{code:"EVENT_STREAM_GAP"}`；不算常规持久业务事件 |

`streaming.py` 需要根据锁定版本的 `messages` / `updates` chunk 实际结构映射；可能会看到模型用于 Tool Calling 的中间 AIMessage、相同消息的 final/update、多个工具回执，不能重复发送工具结果。按真实 message ID / tool_call_id 去重；运行时每轮的消息与上一轮 Checkpoint 历史严格区分。出现不完整/未匹配工具消息应 FAILED，不许伪造成功。

**事件顺序必须满足**：RUNNING 入库 → `run_start`；Graph 有效结束 → `assistant_final`（可先发；不是成功承诺）；业务 SQLite 终态写成功 → `run_end`。数据库写终态失败不得发 `run_end: SUCCEEDED`，必须记录安全错误供核查；SSE 无法提供永久 Exactly-Once。

### 3.3 C 前端

- `frontend/src/api/runtime.ts` 使用浏览器 `EventSource` 订阅；把解析后的 RunEvent 传给 ChatPanel，强校验 run_id 和 event_id 并去重（`Last-Event-ID` 由原生浏览器自动处理，不要求 fetch polyfill）。EventSource 的事件为自定义 `event:` 时要用 `addEventListener` 注册各事件，不能只依赖 `onmessage`。错误重连不代表模型失败。
- ChatPanel 以当前 selected Thread/active Run 为作用域；切换会话或卸载时关闭 EventSource/清理定时器。通过 `message_id` 管理多个模型临时片段，**assistant_final 覆盖**而非接在旧片段后；GET Run 的持久终态覆盖本地推断。
- `tool_start` 显示调用中，`tool_end` 显示真实 ID/参数/结果/ok；只读本次 Event，不混用以前 Thread 的工具状态。
- `run_end` 立即关闭 EventSource、GET Run（并刷新历史）；`stream_gap` 立即停止增量拼接并 GET Run/有限轮询直到终态；断线时使用状态轮询作为兜底，不把 SSE 关闭传递为后端取消。不可无限重连或累计多条活动连接。

### 3.4 C 提交门槛

`test_events.py`：event_id 连续、Run 隔离、先发布后订阅不漏 `run_start`、Last-Event-ID 不重复、初始缓冲缺口、落后订阅者显式 gap、非法/跨 Run cursor、终态保留与过期 410、心跳不触发停止、断开不取消 worker；`test_runs_api.py`：合法 SSE 帧 / 404 / 410、成功/失败先提交终态再发 `run_end`；`test_runner.py`：单次/多轮工具事件来自真实消息、重复和无效回执失败。React 构建与浏览器真实交互（不消费私有密钥）通过。**提交 C** 并记录 SHA，继续 D。

## 4. P02-D：重启恢复、端到端复核与交付

1. 使用临时真实 SQLite 文件，先创建 Thread 并成功执行两轮 Fake 模型对话；结束 app lifespan、完全关闭 Saver 和 DB，再重新创建 app，核对 Thread、历史 Run、Checkpoint 中的消息都仍在；不同 Thread 不串历史。P01 demo /health /calculator /agent / CLI 的接口和原 Prompt 不能退化。
2. 在数据库里人为遗留 CREATED/RUNNING，重启执行已有 Repository 的 `reconcile_orphans()`，要求两种状态均 FAILED `RUN_INTERRUPTED`、受影响 Thread `needs_recovery=true`、新建 Run 409，正常 Thread 仍可使用。Agent 在 Tool/Checkpoint 中途失败也要进入保守恢复，不自动调用可能有副作用的工具。
3. 前端刷新页面恢复已完成聊天，显示真实历史 Run、失败 Run 与恢复状态；选择 Thread、加载历史、订阅已有 Run 的窗口事件、刷新或中断连接后最终 GET Run 查询；不能从已过期 EventBus 期望恢复完整事件。所有 P01 诊断区仍存在。
4. 运行 P02 本次新增/直接受影响的 pytest、Ruff check/format、TS build，以及用无 Key 的 HTTP/SSE/浏览器临时服务做真实最小演示。如本地已有支持 Tool Calling 的 Key，可在**不输出/保存任何 Key** 的条件下另做真实模型两轮记忆和一次 calculate 调用 + SSE Tool Trace；若条件不成立明确标记 `REAL_MODEL_SMOKE_BLOCKED`，不能把 Mock 当真。
5. `README.md` 写真实启动（PyCharm 直接运行后端 + Vite 本地），前后端配置、HTTP 创建 Thread/Run/SSE、刷新/重启、已知限制；`docs/progress/P02.md` 逐条记录 B/C/D 的真实 SHA、文件、前端同步、命令与结果、失败修复/阻塞。同步 README 中状态，不要宣称 P03 能力。
6. **交付停点**：全部关键局部测试通过且 Demo 最小链路可用后将 P02 标记 `PENDING_REVIEW`；用户确认才 `ACCEPTED`。没有关键条件时标 `BLOCKED`、保留已验证 B/C 提交，不伪造完成。不合并到 main、不开始 P03。

## 5. 单次连续 Codex 执行约束与最终回报格式

- **唯一任务输入**：本文件 + `docs/DEVELOPMENT.md` P02 章节 + `AGENTS.md` + 当前实际 P02-A 代码/测试。Codex 只负责按文件编码和验证，不重新设计或改变范围。
- 每阶段先同步当次前端、再执行该阶段局部测试，完成 B/C/D 分别提交，最终一个统一汇报；中途仅在阻塞时打断。提交信息建议 `feat(p02-b): ...` / `feat(p02-c): ...` / `test(p02-d): ...`。
- 新修改的重要 Python/TS 函数必须有简短中文职责说明；事务/并发/消息匹配/事件重连等长流程使用 `# 1.`、`# 2.`、`# 3.`（TS 用 `//`）。不要写逐行翻译式冗余注释。
- 所有测试和模拟运行用临时文件、Fake 模型，隔离用户真实 `.env` / 密钥；不得提交敏感内容、`data/` 或用户本机成果。不要重写 A 已正确工作的 Repository/DB 和原 ThreadList，改动必须精确、必要。
- 如果一个子任务失败：停止接下来的任务，报告失败命令、错误归因、可复现环境、已完成提交和修复建议；不把未实现的下个阶段标记通过。
- 完成时一次性汇报：
  1. B/C/D 各自实现文件、关键机制和前端新能力；
  2. B/C/D 各自实际测试命令/通过数量/失败及修复；
  3. SQLite 持久化/同 Thread 多轮/Tool Trace/SSE 重连与缺口/失败隔离/重启核查的证据；
  4. Fake 与真模型 Smoke 的区分，未知项/非目标范围；
  5. 三个提交 SHA、远端分支推送结果、P02 当前状态；
  6. 对照 `AGENTS.md` 的中文注释自查结果。
