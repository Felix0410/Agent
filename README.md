# Mini DeerFlow

轻量级通用多智能体任务执行系统。**独立从零开发，按模块参考 DeerFlow 2.0，不 Fork 原仓库。**

状态：**P02-A SQLite / Checkpointer / Thread API 与会话列表已实现并局部验证；P02-B/C/D 已完成联合设计、授权连续编码，尚未实现。P01/P02 最终 Demo 仍待用户人工验收。** 本仓库此前的 PaperWeave 设计已终止，旧文档仅可从 Git 历史中查阅。

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
| [代码可读性与 Codex 规则](AGENTS.md) | 中文注释、复杂逻辑编号分段、只测本次变更、同步前端 |
| [阶段进度记录](docs/progress/) | P00–P09 每阶段独立记录真实代码变更、局部测试、Commit 与审核结论 |

**执行原则**：逐阶段落地并记录真实测试与 Git SHA；每次开发任务同步 Web 验证台。P02-A 已交付；用户现已授权 B/C/D 一次性交给 Codex 顺序实现，B/C/D 各自局部测试与独立提交，关键失败则停止，最终仍待用户验收。

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

当前 `/health` 只表示进程存活；已增加本地数据库与会话列表，后台 Run、SSE、多 Agent、Todo、文件与 RAG 尚未实现。

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

打开 http://127.0.0.1:5173 。Vite 将 `/health` 与 `/api` 代理到后端，无需 CORS；只监听回环地址。页面可检查健康、直接计算，并提交一次独立 Agent 请求、展示返回的最终答复与实际工具轨迹。没有会话历史，普通问答不调用工具时轨迹为空。未配置模型时 Agent 清晰返回 503，不影响计算器。

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

最终实测 **59 passed**，Ruff 通过；`npm ci` 与 `npm run build` 通过。Mock 验证框架内模型→工具→模型链路，不能替代真实模型 Smoke；页面中的成功 Agent 回答/轨迹也尚未在真实提供方验证。详细记录见 [P01 进度](docs/progress/P01.md)。PyCharm 可直接运行/调试 main.py，模型配置填写根目录 `.env`；图形界面断点命中待人工验证。

参考上游：[bytedance/deer-flow v2.0.0](https://github.com/bytedance/deer-flow/tree/v2.0.0)，固定 commit 为 `7e7f0410797693cf882594555ba414e0361d4c6f`。参考实现不等于复用全部源码；实际复制或改编受许可代码时保留适用的 MIT 版权与许可声明。


## P02-A 会话与持久化

沿用上面的 PyCharm 或 Uvicorn 启动方式和 `npm run dev`。先在 `backend/` 执行 `uv sync --locked --group dev` 安装新增的 SQLite 依赖。启动自动创建默认 `backend/data/runtime.sqlite3` 和 `backend/data/checkpoints.sqlite3` 的父目录；业务表由项目初始化，检查点表由官方 Saver 按需建立，实际消息写入等待 B 接入。单 Worker 运行，不加 `--reload`。

根目录 `.env` 可配置 `RUNTIME_DB_PATH`、`CHECKPOINT_DB_PATH`；相对路径以 `backend/` 为基准，不受 PyCharm 工作目录影响，两者必须不同。默认数据库目录已被 Git 忽略，修改成项目内其它路径时请相应忽略；不要提交实际库。`RUN_MAX_CONCURRENCY=2`、`RUN_QUEUE_SIZE=8` 已校验，但 A 尚无后台执行与排队能力。本地 `.env` 不会被模板覆盖。

页面新增“会话工作台”：真实新建、刷新、切换会话，查看最近 Run 历史（A 新会话返回空数组），需恢复的会话会提示新建继续。会话聊天按钮禁用并明确标记 B 未实现；P01 单轮 Agent 仍是独立调试入口，不会写入所选 Thread。

已通过临时数据库的真实 HTTP 与浏览器验证：

```bash
curl -i -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/threads
curl -i http://127.0.0.1:8000/api/threads
```

分别返回 201 的 ThreadDto 和 200 的真实列表。`GET /api/threads/{thread_id}/runs?limit=50` 返回 200 历史数组，不存在的 Thread 返回 404 `THREAD_NOT_FOUND`。默认 50 条、最多 100 条，截取最近 N 条后按时间正序返回；标题最多 100 字，空白标题拒绝。A 没有 Run 创建/查询单条/SSE API。

P02-A 验证命令（后端在 `backend/`）：

```bash
uv sync --locked --group dev
uv run pytest -q tests/test_repository.py tests/test_checkpoint.py
uv run pytest -q tests/test_config.py tests/test_health.py tests/test_lead.py tests/test_demo_api.py tests/test_calculator.py
uv run ruff check src tests
uv run ruff format --check src tests
```

本次新增持久化/API/Checkpoint 测试 **22 passed**，配置与 P01 直接受影响复验 **67 passed**；Ruff 与前端 `npm ci` / `npm run build` 通过。测试隔离本地 `.env` 和实际数据库，不调用真实模型。Fake 模型已证明 Checkpoint 关闭重开仍保留消息、同 Thread 连续对话、跨 Thread 隔离，以及真实工具消息 ID 的持久化；不能当作已交付后台多轮会话聊天。

资源由 lifespan 管理，退出反向关闭连接；业务库的遗留活动 Run 保守标记为 `FAILED/RUN_INTERRUPTED`，所属 Thread 标记需恢复，不宣称无损续跑。两库没有跨库原子事务。完整合同见 [P02 设计](docs/DEVELOPMENT.md)，实际进度见 [P02 记录](docs/progress/P02.md)；仅 A 待审核，不进入 B/C/D。


## P02-B/C/D 联合开发（等待编码）

已完成联合设计：[P02-B/C/D 连续执行任务书](docs/tasks/P02-BD.md) 详细规定后台 Run、Graph SSE、页面流式聊天、历史和崩溃后保守恢复的逐文件编码、接口、状态一致性、假模型/真模型验证与验收。用户已授权 B→C→D 在同一次 Codex 会话中连续执行；**此处仅表示设计与授权，当前尚无 B/C/D 业务代码、测试或 Demo 结果**。
