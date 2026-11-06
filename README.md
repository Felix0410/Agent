# Mini DeerFlow

轻量级通用多智能体任务执行系统。**独立从零开发，按模块参考 DeerFlow 2.0，不 Fork 原仓库。**

状态：**P01/P02 后端和 React 代码已实现；P02 仍为 PENDING_REVIEW，尚未在此确认用户手动验收。P03 Workspace / File Tools / Artifact 已启动并完成详细设计，目前仅 PLAN_READY、业务代码尚未实现。** 本仓库此前的 PaperWeave 设计已终止，旧文档仅可从 Git 历史中查阅。

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
| [代码可读性与 Codex 规则](AGENTS.md) | 中文注释、复杂逻辑编号分段、只测本次变更、同步前端 |
| [阶段进度记录](docs/progress/) | P00–P09 每阶段独立记录真实代码变更、局部测试、Commit 与审核结论 |

**执行原则**：逐阶段落实并记录真实测试与 Git SHA；每次开发任务同步 Web 验证台。P02 A/B/C/D 已交付并等待最终用户手动验收；用户请求启动 P03，详细规格和逐文件 Codex 清单已提交到 P03 开发分支。P03 按 A→B→C 逐项运行局部测试和提交，若出现文件安全/权限边界问题立刻停止。

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

PyCharm GUI断点和用户最终Demo验收待人工完成。开发使用的临时Fake/真实Smoke服务不是正常启动配置；完成后会关闭并删除临时库，用户需自行启动后端。详细SHA、真实命令、失败修复与推送状态见 [P02进度](docs/progress/P02.md)。不合并 main；P03 已获准开始设计，P02 尚不标为已手动验收。


## P03 Workspace 与 Artifact（设计已完成、等待代码）

当前 [P03 开发方案](docs/DEVELOPMENT.md) 与 [Codex 执行清单](docs/tasks/P03-ABC.md) 仅定义**待开发**功能：当前 Thread 上传 UTF-8 TXT/MD/CSV/JSON 或原样存储 PDF；Agent 通过可信 LangChain ToolRuntime 上下文访问已登记的文件，执行 `list_files/read_text/write_text`，把生成文件登记为 Artifact 后由浏览器下载；文件系统以不跟随符号链接、UUID 存储名、文件描述符及无覆盖原子发布保证本地范围的文件访问安全。限制为文本上传 2 MiB、PDF 10 MiB、每 Thread 50 文件共 30 MiB；PDF 解析留到 P08。

阶段实施：P03-A 安全存储/上传/前端文件列表，P03-B File Tools/Artifact 下载/前端联动，P03-C 重启/异常测试与 Demo 收尾。**目前没有 P03 的运行成果、上传记录或通过的测试。** `docs/progress/P03.md` 用于逐任务记录真实提交及结果。P01/P02 原有功能应始终保留。

## P03-A 文件上传（本次增量）

当前Thread可上传 UTF-8 txt/md/csv/json（2MiB）或PDF（10MiB，仅存储不解析）；总50项/30MiB。`WORKSPACE_ROOT_PATH`默认backend/data/workspaces，相对路径从backend解析。实际存储只用内部UUID，显示名不参与磁盘路径。上传和文件列表不需要模型配置；本地 `.env` 保持原样。

新增POST/GET `/api/threads/{thread_id}/files`；浏览器FormData字段file单文件，201返回已登记FileRecord，无宿主机路径。只支持安全POSIX本地存储，目录symlink/替换、非法内容和配额等错误会拒绝。P03-A尚无文件工具或Artifact下载；原P01/P02功能保留。
