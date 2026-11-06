# Mini DeerFlow

轻量级通用多智能体任务执行系统。**独立从零开发，按模块参考 DeerFlow 2.0，不 Fork 原仓库。**

状态：**P01–P05 的实际 Python/React 代码已在开发分支实现；P02/P03/P04/P05 均为 PENDING_REVIEW，等待用户最终手动验收。P06 Run预算、上下文压缩、取消与恢复已完成详细设计，当前仅 PLAN_READY、业务代码尚未开发。** 本仓库此前的 PaperWeave 设计已终止，旧文档仅可从 Git 历史中查阅。

## 要做成什么

一个能在 Web 中使用的任务型 Agent：用户给出目标，主 Agent 直接答复或动态制定 Todo、调用工具、委派 Sub-Agent；系统管理会话、工具权限、文件工作空间与运行状态，最终交付回答或可下载文件。

三个最终演示场景：

1. **Deep Research**：多轮联网检索、多视角子任务、证据汇总、生成带来源的报告。
2. **文档 RAG**：上传 PDF / Markdown / TXT、解析索引、跨文档检索、带原文定位的回答。
3. **文件任务**：按计划操作受控文件工具，生成真正可下载的 Markdown / CSV / JSON 产物。

## 开发方案已固定

- **后端**：Python 3.12、uv、FastAPI、Pydantic、LangChain + LangGraph。
- **模型**：先接入一个验证通过的 OpenAI 兼容聊天模型提供方，统一 ModelFactory。
- **状态**：SQLite + LangGraph SQLite Checkpointer，单 Worker；Run 状态与图状态分离。
- **前端**：React + TypeScript + Vite，薄 Web 工作台；SSE 流式输出。
- **扩展**：统一工具注册、MCP Adapter、按需加载的 SKILL.md。
- **文档知识库**：Docling（文本型 PDF）+ Embedding + Chroma 本地向量索引；先做基础检索，验证后再升级。
- **测试**：**每次只运行本次新增/修改功能的测试，以及直接受影响接口的必要测试；不做每阶段全量回归。**
- **交付**：单机部署，后期 Docker Compose；暂不引入 Redis、RabbitMQ、微服务、K8s、复杂权限体系。

上述技术方向固定；第三方库具体小版本在 P00 实际验证并锁定，如存在兼容性问题需记录调整原因。

## 主文档与阶段进度

| 文档 | 作用 |
|---|---|
| [总体业务与系统架构](docs/ARCHITECTURE.md) | 功能范围、真实业务流程、模块边界、状态、接口、技术栈、DeerFlow 源码参考 |
| [完整开发方案](docs/DEVELOPMENT.md) | P00–P09 增量开发任务、局部测试规则、每阶段验收、Codex 协作 |
| [P02-A Codex 执行清单](docs/tasks/P02-A.md) | 可按文件实施的 SQLite / Checkpointer / Thread API 与前端同步任务 |
| [P02-B/C/D 联合执行任务书](docs/tasks/P02-BD.md) | 一次性交给 Codex，按 B→C→D 连续实现、分别测试提交并同步前端 |
| [P03-A/B/C 实施任务书](docs/tasks/P03-ABC.md) | 本阶段 Workspace / ToolRuntime / Artifact 三任务的逐文件编码、局部测试与安全约束 |
| [P04-A/B/C/D Codex 任务书](docs/tasks/P04-ABCD.md) | P04 Todo 状态、受限子代理、并发/事件与 Demo 的逐文件任务及测试 |
| [P05-A/B/C/D Codex 任务书](docs/tasks/P05-ABCD.md) | ToolRegistry/ToolGuard、本地 MCP Server、Skills 与前端测试的精确文件/接口/验证要求 |
| [P06-A/B/C/D Codex 任务书](docs/tasks/P06-ABCD.md) | 父子共享Run预算、真实/估算Usage、长工具输出引用、Graph历史压缩、取消与恢复逐文件实现 |
| [代码可读性与 Codex 规则](AGENTS.md) | 中文注释、复杂逻辑编号分段、只测本次变更、同步前端 |
| [阶段进度记录](docs/progress/) | P00–P09 每阶段独立记录真实代码变更、局部测试、Commit 与审核结论 |

**执行原则**：逐阶段落实并记录真实测试与 Git SHA；每次新增用户可见功能同步 Web 验证台。P02–P05 已有代码与局部验证记录，但用户最终手动验收状态不自动改变；P06 已完成设计并在独立分支形成 A→B→C→D 实施任务书，**本期尚未编码或测试**。关键失败需停止，不自动进入 P07。

## P00 本地开发

已验证环境：macOS、uv 0.11.7、Python 3.12.13；项目要求 Python 3.12，环境位于 `backend/.venv/`。在仓库根目录进入后端后执行：

```bash
cd backend
uv sync --group dev
uv sync --locked --group dev
uv run python -c "import minideerflow; from minideerflow.main import app; print(app.title)"
uv run pytest -q tests/test_health.py tests/test_config.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run uvicorn minideerflow.main:app --host 127.0.0.1 --port 8000
```

另一个终端进入 `backend/` 后执行 `curl -i http://127.0.0.1:8000/health`，实测返回 HTTP 200 和 `{"status":"ok"}`。终端按 Ctrl+C 停止服务。P00 当时局部测试实测 4 passed、1 条 TestClient 弃用警告（详见 P00 进度）；P01 新增传递依赖 httpx2 后该警告消失。

基础配置为 `APP_ENV`（默认 `development`）和 `LOG_LEVEL`（默认 `INFO`）。后端自动读取仓库根目录 `.env`（UTF-8），不依赖启动工作目录；文件不存在时使用默认值。同名进程环境变量（终端 `export` 或 PyCharm Environment Variables）优先。修改 `.env` 后需重启后端。P01 模型配置见下文。

PyCharm 打开整个仓库，将解释器设为 `<仓库>/backend/.venv/bin/python`，右键 `backend/src/minideerflow/main.py` → Run 或 Debug 即可启动后端。Run/Debug 配置使用 Script path `<仓库>/backend/src/minideerflow/main.py`、Working Directory `<仓库>/backend`，无需 Parameters。直接运行入口监听 `127.0.0.1:8000`，不启用 reload，支持在 health 返回行设置断点；**图形界面配置和断点命中待用户实测**。原来的 Uvicorn Module 启动方式仍可用。

当前 `/health` 只表示进程存活；P02 已支持会话记忆、后台 Run 与 SSE，多 Agent、Todo、文件与 RAG 尚未实现。

## P01 本地 Demo

实测 Node.js 24.13.0、npm 11.6.2；后端沿用 Python 3.12。根目录开两个终端：

首次配置：复制根目录 `.env.example` 为 `.env`，填写模型名称、密钥和接口地址。已有 `.env` 时直接编辑，不覆盖；`.env` 已被 Git 忽略。

```bash
cp -n .env.example .env
```

后端可直接在 PyCharm 右键 `main.py` → Run/Debug；也可以在终端启动（无需模型密钥即可使用健康检查与计算器）：

```bash
cd backend
uv sync --locked --group dev
uv run uvicorn minideerflow.main:app --host 127.0.0.1 --port 8000
```

终端二启动页面：

```bash
cd frontend
npm ci
npm run build
npm run dev
```

打开 http://127.0.0.1:5173 。Vite 将 `/health` 与 `/api` 代理到后端，无需 CORS；只监听回环地址。P01 调试区可检查健康、直接计算，并提交独立 Agent 请求、展示最终答复与实际工具轨迹；该调试区不写会话历史，普通问答不调用工具时轨迹为空。上方 P02 会话工作台负责持久化多轮对话。未配置模型时 Agent 清晰返回 503，不影响计算器。

已通过真实 HTTP 和浏览器验证：

```bash
curl -i http://127.0.0.1:5173/health
curl -i -H 'Content-Type: application/json' -d '{"expression":"(12+8)*3"}' http://127.0.0.1:5173/api/demo/calculate
curl -i -H 'Content-Type: application/json' -d '{"message":"hello"}' http://127.0.0.1:5173/api/demo/agent
```

分别返回 200/`ok`、200/`60`、503/`MODEL_NOT_CONFIGURED`。直接计算仅支持数字、括号、`+ - * /` 与一元正负，最长 128 字符，数值及中间值绝对值不超过 10^12；计算错误返回 422。

使用真实 Agent 前，在**仓库根目录 `.env`** 配置 `MODEL_NAME`、`MODEL_API_KEY`，按提供方需要配置 `MODEL_BASE_URL`。基础地址通常以 `/v1` 结尾，不要包含 `/chat/completions`，SDK 会自动追加端点。提供方必须支持 Tool Calling；密钥仅留在后端，不放进前端。默认单次请求超时 45 秒、无 SDK 重试、图递归限制 12。初次交付时真实模型未配置；后续修正本地基础地址后，已通过 AgentService 实测普通问答及 calculate 工具调用（结果 60）。运行中的后端需重启以读取新配置。

CLI 与 HTTP 复用同一 AgentService。在 `backend/` 执行：

```bash
uv run python -m minideerflow.cli "请计算 (12+8)*3"
```

本次只实测无配置时输出 `MODEL_NOT_CONFIGURED` 并以退出码 1 结束；配置后的真实答复待验证。模型上游错误会映射为脱敏的 502/504；工具计算失败会返回错误 ToolMessage，让模型解释。

P01 局部验证（后端在 `backend/`，前端在 `frontend/`）：

```bash
uv run pytest -q tests/test_calculator.py tests/test_lead.py tests/test_demo_api.py tests/test_config.py tests/test_health.py
uv run ruff check src tests
uv run ruff format --check src tests
```

P01 初次交付实测 **59 passed**，Ruff 通过；`npm ci` 与 `npm run build` 通过。Mock 验证框架内模型→工具→模型链路，不能替代真实模型 Smoke；后续 P02 真实 HTTP/SSE 工具调用验证见下文。详细记录见 [P01 进度](docs/progress/P01.md)。PyCharm 可直接运行/调试 main.py，模型配置填写根目录 `.env`；图形界面断点命中待人工验证。

参考上游：[bytedance/deer-flow v2.0.0](https://github.com/bytedance/deer-flow/tree/v2.0.0)，固定 commit 为 `7e7f0410797693cf882594555ba414e0361d4c6f`。参考实现不等于复用全部源码；实际复制或改编受许可代码时保留适用的 MIT 版权与许可声明。


## P02 会话 / 后台 Run / SSE Demo

后端沿用 PyCharm 直接 Run/Debug `backend/src/minideerflow/main.py`：**解释器务必选择 `backend/.venv/bin/python`，不是根目录 `.venv`**；工作目录 backend，无参数、无 reload、单 Worker。安装与终端启动：

```bash
cd backend
uv sync --locked --group dev
uv run python src/minideerflow/main.py
```

另一个终端运行前端：

```bash
cd frontend
npm ci
npm run build
npm run dev
```

打开 http://127.0.0.1:5173 ，新建/选择会话并发送消息。根目录 `.env` 自动读取模型配置（支持 Tool Calling）；无密钥时健康/计算/会话列表可用，Run 提交503且不残留任务。未改动用户 .env；默认两库在 backend/data 下、彼此独立。自定义相对路径以 backend 为基准，修改配置后重启。

- POST 返回202仅表示已接收；2个worker、8个排队，同Thread只允许一个活动Run。满队列429，同会话忙/需恢复409。
- 页面显示真实流式文字与工具开始/结果；最终文本覆盖临时片段，只有GET Run的持久化终态才确认成功。
- 浏览器只在localStorage保存最近Thread ID；刷新后从服务端重新读取会话与最近50条Run历史（接口最多100条），不把Run文本拼成模型上下文。模型历史来自官方SQLite Checkpointer。
- 同Thread正常多轮共享记忆，不同Thread隔离；正常关机先等待有限时间再取消并回收worker，然后关闭事件内存和两库。重新启动可以续接成功会话的Checkpoint。
- 异常/超时可能留下部分Graph状态，Thread会标记需恢复，请新建会话继续。遗留CREATED/RUNNING在启动时FAILED/RUN_INTERRUPTED；不提供手动清除恢复标志、取消或无损续跑。
- P01健康、计算器、一次性Agent和CLI全部保留，与P02会话工作台独立。

API 操作：

```bash
curl -i -H 'Content-Type: application/json' -d '{"title":"测试会话"}' http://127.0.0.1:8000/api/threads
# 用上一步返回的 id 替换 THREAD_ID
curl -i -H 'Content-Type: application/json' -d '{"message":"请调用calculate计算(12+8)*3"}' http://127.0.0.1:8000/api/threads/THREAD_ID/runs
# 用202返回的 run_id 替换 RUN_ID
curl -N http://127.0.0.1:8000/api/runs/RUN_ID/events
curl -i http://127.0.0.1:8000/api/runs/RUN_ID
```

SSE是有限内存窗口：512条/Run、64条/订阅者，终态后保留10分钟。Last-Event-ID可补发同Run后续事件；窗口缺口/过慢消费者明确stream_gap，过期410。页面至多三次原生重连，并以最多180次状态查询兜底；切换会话清理旧订阅，断线不取消后台Run。重启后事件窗口消失，但最终Run与Graph历史仍在。两库无跨库原子事务，不承诺Exactly-Once或永久事件回放。仅本机回环服务，无多用户鉴权。

P02 本次局部验证（在 backend/）：

```bash
uv run pytest -q tests/test_runner.py tests/test_runs_api.py tests/test_events.py tests/test_repository.py tests/test_checkpoint.py tests/test_lead.py tests/test_demo_api.py tests/test_health.py tests/test_config.py tests/test_calculator.py
uv run ruff check src tests
uv run ruff format --check src tests
```

B 72 passed；C 94 passed；D最终136 passed（0 failed）。每一部分分别提交与记录，各阶段数量不能直接累加为独立用例总数。依赖锁检查、Ruff与TypeScript/Vite构建通过。Fake+临时两库验证重启恢复、消息隔离、工具ID/错误回执、SSE重连/gap、失败/队列与shutdown；真实浏览器验证创建/提交/工具轨迹/执行中刷新与历史恢复。

真实模型独立Smoke：deepseek-flash，临时两库，三次HTTP202、SSE200、GET Run均SUCCEEDED。首轮记住测试口令、第二轮正确回答 Cedar-482；第三轮实际calculate(expression="(12+8)*3")返回60，SSE的tool_start/tool_end ID匹配，三轮收到真实文本增量。未记录密钥/认证头/模型隐藏内容；真实模型的重启后记忆和故障注入仅通过Fake覆盖，未额外消费额度。

PyCharm GUI断点和用户最终Demo验收待人工完成。开发使用的临时Fake/真实Smoke服务不是正常启动配置；完成后会关闭并删除临时库，用户需自行启动后端。详细SHA、真实命令、失败修复与推送状态见 [P02进度](docs/progress/P02.md)。不合并 main；P03 实现与验证见下节，P02 尚不标为已手动验收。


## P03 文件 Workspace 与 Artifact

启动仍沿用上述 PyCharm + Vite：先在 `backend/` 执行 `uv sync --locked --group dev`（新增 python-multipart 0.0.33），解释器选择 **backend/.venv/bin/python**，Run/Debug `src/minideerflow/main.py`；前端 `npm ci && npm run dev`，打开 http://127.0.0.1:5173 。已有后端需重启以加载新代码；本地 `.env` 未被修改。

操作闭环：新建/选择Thread → 在“会话文件”上传 `notes.md` → 会话聊天输入“读取我上传的notes.md，生成summary.md并让我下载” → 观察真实list_files/read_text/write_text轨迹 → Run结束自动刷新“实际产物” → 点击下载。刷新后仍读取真实列表；重启后的元数据、文件与Run历史保留。PDF仅存储，暂不解析；无模型时上传、列表和已有产物下载仍可用。

| 约束 | 本期行为 |
| --- | --- |
| 上传类型 | UTF-8 txt/md/csv/json，最多2MiB；PDF最多10MiB，只检查基本签名并原样存储 |
| Thread额度 | 所有已登记上传与产物合计50项、30MiB |
| 文件工具 | list_files仅当前Thread；read_text只接受file_id，完整返回最多64KiB；write_text仅安全显示名和UTF-8文本，最多128KiB |
| 同名 | 上传原文件可同名并存，以file_id区分；同Thread产物显示名唯一，禁止覆盖 |
| 身份 | Thread/Run由Runner的ToolRuntime Context注入，不在模型schema中；P01单轮Agent/CLI仍只有calculate |
| 路径 | `WORKSPACE_ROOT_PATH`默认backend/data/workspaces，内部Thread/磁盘名都由后端UUID决定，显示名不参与寻址 |
| 下载 | 只有已登记Artifact ID + Thread归属匹配，安全fd读取后复核size/sha，再返回bytes；不使用FileResponse重新开路径 |

`WORKSPACE_ROOT_PATH` 相对路径以backend为基准，两库不能位于Workspace中。根目录及Thread目录须属于当前用户且权限0700；新文件0600。拒绝所有目录路径组件中的symlink、非预期硬链接/文件类型、目录/文件替换与哈希变化；不支持安全dir_fd/O_NOFOLLOW/no-clobber link的平台拒绝启动，不能退化为不安全路径打开。默认目录在Git忽略的backend/data下；自定义项目内路径需自行忽略，勿提交实际文件或DB。

API（以下为手工操作示例，ID换成实际返回值）：

```bash
curl -F 'file=@notes.md' http://127.0.0.1:8000/api/threads/THREAD_ID/files
curl http://127.0.0.1:8000/api/threads/THREAD_ID/files
curl http://127.0.0.1:8000/api/threads/THREAD_ID/artifacts
curl --get --data-urlencode 'thread_id=THREAD_ID' http://127.0.0.1:8000/api/artifacts/ARTIFACT_ID -o summary.md
```

文件系统与SQLite没有联合事务：登记前失败清理本次UUID；提交边界取消会等待事务确定结果，已提交上传精确补偿，已提交Artifact即使Run后续FAILED也保留可下载。提交结果不可确认时仅尽力清理，可能保留不公开的孤立文件；API不会扫描磁盘将孤立文件当成资源。没有删除、覆盖、Shell、RAG、PDF解析、多租户权限。P04能力见下节。仅本机单用户运行，不宣称可以抵御能任意修改本进程数据目录的同OS用户。

真实验证：A局部78 passed，B局部111 passed，C最终214 passed、0 failed；不将重叠测试数相加。Ruff、uv锁一致性、TypeScript/Vite构建通过。最终局部命令（backend/）：

```bash
uv run pytest -q tests/test_workspace.py tests/test_file_tools.py tests/test_files_api.py tests/test_config.py tests/test_repository.py tests/test_checkpoint.py tests/test_runner.py tests/test_runs_api.py tests/test_lead.py tests/test_demo_api.py tests/test_health.py tests/test_events.py tests/test_calculator.py
uv run ruff check src tests
uv run ruff format --check src tests
```

Fake/临时资源覆盖安全路径、上传配额、Context与ToolMessage、跨Thread、原子同名竞争、SQL回滚、取消/失败、两库+Workspace完整重开和下载校验。真实 **deepseek-flash** 另用专门临时样例，经实际浏览器上传→list/read/write→SSE与SUCCEEDED→自动产物列表→下载与刷新再下载通过；生成summary.md 576 bytes，读取内容SHA与上传登记一致，写入参数与下载字节一致。未记录密钥、原始认证头或私人文档。

当前实测平台为macOS；其它POSIX平台和PyCharm GUI断点未直接验证，能力缺失会fail closed。完整重启/故障注入用Fake验证，没有额外使用真实模型注入故障。开发Smoke使用独立端口/临时两库与Workspace，完成后关闭并清理；用户原8000服务未停止，验收时请自行重启以加载新代码。详细文件、SHA、命令及推送结果见 [P03进度](docs/progress/P03.md)。


## P04 Todo 与 Sub-Agent（PENDING_REVIEW）

已按 [正式设计](docs/DEVELOPMENT.md) 和 [A/B/C/D合同](docs/tasks/P04-ABCD.md) 实现；P02/P03的待审核状态保持。模型按复杂度选择 `write_todos` 和 `task`，普通问答/计算不强制规划。

- Todo同时写真实LangGraph State/Checkpoint和每Run SQLite完整快照；同ID覆盖，最多8条，不允许删除旧ID或从completed回退，同一步多个write_todos全部拒绝。下一Run重置Graph.todos，历史SQL保留。
- `general`只有calculate/list_files/read_text，`research`只有list_files/read_text（**仅已有材料，无联网**）。每child独立messages、checkpointer=None，无父完整历史，无task/write_todos/write_text；Lead可汇总后用write_text生成Artifact。
- 每父Run最多3并发、4次委派；child默认35秒/14个图节点步，父持久Run150秒/36个图节点步。P01独立单轮仍45秒/12步。次数包含失败/超时；超时、取消与关闭先回收child，再终结父Run。次数/并发可降低，不能提高合同上限。
- Subtask真实状态持久化：PENDING/RUNNING→COMPLETED/FAILED/TIMED_OUT/CANCELLED；未启动取消为FAILED。重启遗留任务标FAILED/SUBTASK_INTERRUPTED，不自动重放。子任务完成只认实际最终消息/成功工具回执，文件来源只认真实read_text，不相信模型自报UUID。
- 子任务最多1600字符摘要，截断明确标记；完整子对话/Token不拼回父图。Todo/Task页面从真实SSE更新，Run结束/断流/缺口/刷新/重启GET补齐，切换会话不串记录。

新增只读接口（不提供前端写计划或手动派发API）：

```text
GET /api/runs/{run_id}/todos
GET /api/runs/{run_id}/subtasks
```

未知Run返回404，无计划/委派返回空数组。沿用P02的SSE接口，新增todo_updated/subtask_created/subtask_started/subtask_completed/subtask_failed；事件窗口过期不影响SQL历史。Todo的SQL与Graph Checkpoint仍是两个库，没有跨库原子事务；SQL已提交而图后续失败时保留SQL，父Run按P02保守恢复策略处理。

启动方式保持：

```bash
# 在 backend/ 执行
uv sync --locked --group dev
uv run python src/minideerflow/main.py
# 另一个终端，在 frontend/ 执行
npm ci
npm run dev
```

PyCharm解释器用`backend/.venv/bin/python`，入口`backend/src/minideerflow/main.py`，工作目录`backend`，无参数。根目录已有.env会自动读取，无须改.env即可使用P04默认预算；修改配置/更新代码后重启后端。GUI断点待人工验证。

手动Demo：新建会话→上传一份UTF-8 notes.md→发送“先写Todo，将文档核心观点和风险分别委派general/research读取分析，再创建summary.md并更新计划”。检查Todo、两条真实Task和来源文件ID、下载产物；刷新与切换会话后应恢复各自历史。模型可能选择其它执行顺序，实际任务状态与工具轨迹才是执行证据。

本轮局部验证（在backend/执行）：

```bash
uv lock --check
uv sync --locked --group dev
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q tests/test_planning_demo.py tests/test_todos.py tests/test_subagents.py tests/test_task_registry.py tests/test_tasks_api.py tests/test_config.py tests/test_repository.py tests/test_checkpoint.py tests/test_runner.py tests/test_runs_api.py tests/test_lead.py tests/test_demo_api.py tests/test_health.py tests/test_events.py tests/test_calculator.py tests/test_file_tools.py tests/test_workspace.py tests/test_files_api.py
```

最终 **253 passed，0 failed**，仅P04与直接受影响P01–P03消费者；Ruff/前端TypeScript+Vite构建通过。Fake使用临时两库/Workspace覆盖完整文件任务、重启、失败、并发与取消；ego-browser实际UI验证历史恢复及下载。

真实模型deepseek-flash独立验证：3项Todo、general/research两次实际task、真实文件读取、summary.md落盘下载、刷新/跨会话隔离均通过。复杂Run约15.80秒、12次模型调用、19,797 tokens；另测普通问候/实际calculate=60，不产生Todo/Task。本轮真实验证合计15次模型调用、30,823 tokens（提供方usage，未获得实际账单金额）。真模型与Fake结果分别记录，不以模型宣称代替工具证据。

Smoke使用隔离8004后端/5174 Vite与合成文档；测试服务已关闭，临时库/Workspace已清理，未动用户原服务和本地.env。实际模型跨进程重启、故障注入由Fake覆盖；其它OS和PyCharm GUI尚未直接验证。完整SHA/测试命令/推送结果见 [P04进度](docs/progress/P04.md)。等待用户手动验收，不合并main、不进入P05。

## P05 ToolRegistry / MCP / Skills（PENDING_REVIEW）

已按 [正式方案](docs/DEVELOPMENT.md) 与 [A/B/C/D合同](docs/tasks/P05-ABCD.md) 分别实现和提交。保留P01独立单轮、P02 Run/SSE/Checkpoint、P03文件和P04 Todo/Task；P02/P03/P04的待审核状态不改为已验收。

- ToolRegistry在启动期构造固定工具快照，ToolPolicy由可信Run上下文生成，默认拒绝。官方`awrap_tool_call` Middleware复核真实Run/Thread、权限与公开Schema，单次handler执行、独立工具时限、保留ToolMessage与Command；不会截断P03的64KiB读取结果。写操作超时结果未知，不自动重试。
- 默认8个父工具：六个原有内置工具，加`list_skills/read_skill`。MCP默认禁用；显式配置且工具原名/描述/输入Schema/注解SHA256均批准后才加入`mcp_demo_lookup_fact`。Child仍仅general三个只读工具、research两个文件读取工具，没有MCP/Skills/写文件或再次委派。
- MCP仅精确`http://127.0.0.1:<port>/mcp`的Streamable HTTP，最多2个Server、各4个批准工具；拒绝stdio、其它地址、跳转、环境代理、凭据字段及远端Schema引用。输入最多2KiB、输出最多8KiB且纯文本，异常和isError保留真实失败语义。
- MCP状态来自启动发现与实际调用。实际断连后停止该来源后续准入；已知不可用状态会在目录显示，builtin/Skill继续可用。服务/配置恢复需重启后端重新发现，刷新按钮只GET目录，不重连或批准工具。
- Skill固定在`backend/skills/public/<directory>/SKILL.md`，最多10个，文件16KiB/正文12KiB；逐级无symlink读取、UTF8/YAML白名单、拒绝锚点/别名/重复key，按需读取复核inode与摘要。`allowed_tools`是前置要求，不是授权；不在System Prompt注入正文，不执行Skill代码。

前端“可用工具与Skills”展示实际来源、权限、状态与Skill简介；只有刷新，没有执行或授权按钮。只读接口：

```text
GET /api/tools
GET /api/skills
```

默认运行无需MCP配置：在backend执行`uv sync --locked --group dev`、`uv run python src/minideerflow/main.py`；前端在frontend执行`npm ci`、`npm run dev`。根目录.env继续自动加载，更新代码后重启后端。

### 测试本机MCP示例

先在backend目录启动一个独立终端：

```bash
uv sync --locked --group dev
uv run python examples/mcp_readonly_server.py
```

它只监听127.0.0.1:8765，工具`lookup_fact(topic)`仅查询langgraph/mcp/skills固定字典，没有文件读取、网络检索、Shell或凭据操作。可在另一终端核验实际Schema pin：

```bash
# 同样在backend目录；只发现并打印原名与摘要，不修改配置
uv run python -m minideerflow.tools.mcp_adapter
```

本轮SDK的实际pin为`bb4d0dd3eb360c06d10f7c9b59a01324cd9435f32722da5d12fc5f0e5167e2c3`，已填写`backend/config/mcp_servers.example.json`。摘要以name/description/input_schema/annotations四字段，sort_keys、UTF8、无多余JSON分隔空格计算SHA256。若变更，应先审核服务源码/真实元数据，再人工更新配置；不能自动接受新pin。

显式启用示例后端：

```bash
# backend目录；该环境变量只影响当前命令，不改本地.env
MCP_CONFIG_PATH=config/mcp_servers.example.json uv run python src/minideerflow/main.py
```

PyCharm仍用`backend/.venv/bin/python`，入口`backend/src/minideerflow/main.py`、工作目录backend、无参数；在该Run Configuration的环境变量中加入`MCP_CONFIG_PATH=config/mcp_servers.example.json`即可启用。未设置则不连接任何MCP。不要同时在8000端口启动两份后端。

### 手动Demo

启动上述两个后端进程及前端，检查能力目录出现`mcp_demo_lookup_fact`和`file-analysis`。新建会话，上传一份合成notes.md，再发送：

> 请实际查询本机MCP的langgraph固定事实，读取file-analysis Skill，按指南分析上传文档，最后创建summary.md供我下载；工具失败时请明确说明。

检查真实工具轨迹、文件读取及实际下载；刷新/切换会话后历史和产物应恢复。关闭MCP示例服务后，要求重新实际调用该工具并计算`(12+8)*3`：MCP应失败，calculate仍可返回60；刷新能力目录看到不可用，重启MCP和后端后恢复。正常任务由模型按需选择工具，不强制每轮规划/委派/Skill/MCP调用。

### 验证与限制

锁定`mcp 1.30.0`、`langchain-mcp-adapters 0.3.2`、`PyYAML 6.0.3`，只新增本期依赖及必要传递项，既有依赖未无关升级。OSV查询前两个精确版本未返回已知漏洞记录；这是本次查询结果。MCP Server本身须可信，readOnlyHint不是操作系统沙箱。

在backend目录执行：

```bash
uv lock --check
uv sync --locked --group dev
uv run ruff check src tests examples
uv run ruff format --check src tests examples
uv run pytest -q tests/test_tools_demo.py tests/test_tool_registry.py tests/test_tool_guard.py tests/test_mcp.py tests/test_skills.py tests/test_capabilities_api.py tests/test_planning_demo.py tests/test_todos.py tests/test_subagents.py tests/test_task_registry.py tests/test_tasks_api.py tests/test_runner.py tests/test_file_tools.py tests/test_config.py tests/test_runs_api.py tests/test_events.py tests/test_lead.py tests/test_files_api.py tests/test_workspace.py tests/test_demo_api.py tests/test_health.py tests/test_calculator.py tests/test_repository.py tests/test_checkpoint.py
```

本轮最终结果和每段SHA见 [P05进度](docs/progress/P05.md)。Fake+真实本机MCP/临时数据库验证完整文件、委派隔离、重启与故障；真实浏览器验证目录、下载及历史恢复。deepseek-flash另行实际调用MCP、Skill和文件工具创建2136-byte产物，约9.48秒；MCP下线后的真实错误与calculate=60也通过，合计7次模型调用、12,898 tokens，未获得账单金额。复杂Run的旧SSE回放出现stream_gap，页面通过GET恢复历史；未扩大事件窗口或进入P06。

所有Smoke使用独立8005/5175和临时两库/Workspace、合成文档，已关闭清理，不改本地.env或用户原服务。PyCharm GUI断点、其它OS、真实模型下的子代理委派本轮未再实测（委派由真实Graph+Fake回归覆盖）；不是对任意不可信MCP服务的沙箱保证。当前PENDING_REVIEW，等待用户手动验收，不合并main、不进入P06。


## P06 Run预算、上下文压缩与取消（设计就绪，尚未编码）

[正式实施设计](docs/DEVELOPMENT.md) 与 [P06-A/B/C/D 逐文件 Codex 任务书](docs/tasks/P06-ABCD.md) 已同步到 `feat/p06-context-budget-cancel` 分支，独立 [进度](docs/progress/P06.md)。**当前仅继承 P05 完整代码，P06 功能未实现，不存在 P06 测试通过结果或取消按钮。**

本阶段分四步：A 在现有 LangChain Middleware 中加入父 Agent+所有 Child 共享模型/工具次数预算与独立 Usage/Token 估算统计，Web 出现实际 UsagePanel；B 安全压缩 Graph 旧对话（保留当前目标、P04 Todo、ToolMessage配对和文件/Artifact引用），超长工具结果保留已登记file ID或真实Artifact来源；C 添加幂等的 `POST /api/runs/{run_id}/cancel`，区别“请求取消中”与真实CANCELLED，不杀死整个Worker队列；D 联合故障/Checkpoint/重启/UI 与短真实模型验证。

设计默认父Run最长600秒、最多40次模型调用和30次工具调用（模型预算父子共享，Graph仍各自有节点步上限），单请求上下文估算12k触发压缩、18k硬阈值；**估算Token不是准确模型账单**。前端180次轮询与后端150秒时限会作为一组升级，不会只改单边。旧SQLite无破坏迁移，`cancel_requested_at` 持久表示“请求收到”，真正清理完成后才落CANCELLED；未知外部副作用保守 FAILED/OUTCOME_UNKNOWN，绝不自动重试。

用户手动验收P02–P05状态仍然是 `PENDING_REVIEW`；P06 完成后再根据真实代码和测试记录发布新Demo步骤，不能提前宣称已可用。
