# Mini DeerFlow

轻量级通用多智能体任务执行系统。**独立从零开发，按模块参考 DeerFlow 2.0，不 Fork 原仓库。**

状态：**P01 单 Agent + 极简 Web 验证台已实现，待审核；计算器/页面和 Mock Agent 已验证，真实模型 Smoke 因未配置 MODEL_* 而阻塞。** 本仓库此前的 PaperWeave 设计已终止，旧文档仅可从 Git 历史中查阅。

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
| [阶段进度记录](docs/progress/) | P00–P09 每阶段独立记录真实代码变更、局部测试、Commit 与审核结论 |

**执行原则**：逐阶段落地并记录真实测试与 Git SHA；P01 起每次开发任务都同步更新极简 Web 测试台（内部改动无前端可见行为时记录原因）；最小可执行 Demo 完成后再由用户手动测试。P01 等待审核，不进入 P02。

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

PyCharm 打开整个仓库，将解释器设为 `<仓库>/backend/.venv/bin/python`；创建 Python Run/Debug 配置，Module 为 `uvicorn`，Parameters 为 `minideerflow.main:app --host 127.0.0.1 --port 8000`，Working Directory 为 `<仓库>/backend`，不加 `--reload`。在 `main.py` 的 health 返回行设断点，再发起上述 curl 请求验证；**图形界面配置和断点命中待用户实测**。

当前 `/health` 只表示进程存活；数据库、会话、SSE、多 Agent、Todo、文件与 RAG 尚未实现。

## P01 本地 Demo

实测 Node.js 24.13.0、npm 11.6.2；后端沿用 Python 3.12。根目录开两个终端：

首次配置：复制根目录 `.env.example` 为 `.env`，填写模型名称、密钥和接口地址。已有 `.env` 时直接编辑，不覆盖；`.env` 已被 Git 忽略。

```bash
cp -n .env.example .env
```

终端一启动后端（无需模型密钥即可使用健康检查与计算器）：

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

使用真实 Agent 前，在**仓库根目录 `.env`** 配置 `MODEL_NAME`、`MODEL_API_KEY`，按提供方需要配置 `MODEL_BASE_URL`。提供方必须支持 Tool Calling；密钥仅留在后端，不放进前端。默认单次请求超时 45 秒、无 SDK 重试、图递归限制 12。本次未提供真实模型配置，**REAL_MODEL_SMOKE_BLOCKED：未验证任何真实提供方或真实模型工具调用**。

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

最终实测 **59 passed**，Ruff 通过；`npm ci` 与 `npm run build` 通过。Mock 验证框架内模型→工具→模型链路，不能替代真实模型 Smoke；页面中的成功 Agent 回答/轨迹也尚未在真实提供方验证。详细记录见 [P01 进度](docs/progress/P01.md)。PyCharm 仍沿用上面的 Uvicorn 配置，模型变量填入其 Environment Variables；图形界面断点命中待人工验证。

参考上游：[bytedance/deer-flow v2.0.0](https://github.com/bytedance/deer-flow/tree/v2.0.0)，固定 commit 为 `7e7f0410797693cf882594555ba414e0361d4c6f`。参考实现不等于复用全部源码；实际复制或改编受许可代码时保留适用的 MIT 版权与许可声明。
