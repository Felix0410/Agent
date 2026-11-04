# 开发方案、任务顺序与局部测试规则

**方案版本**：v1.3 · 2026-11-04  
**当前状态**：设计确定；P00 尚未开始。各阶段真实进度独立记录在 `docs/progress/Pxx.md`，本文件只维护计划与执行规则。  
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

## 4. 固定的实现合同与文件规划（Codex 不得自行重设计）

> 本节与后续 P00–P09 共同构成**编码实施规格书**。总体业务目标以 ARCHITECTURE.md 为准；本文件规定具体的文件、函数、输入输出与实现顺序。以下路径为正式目标，Python 代码全部相对 \`backend/src/minideerflow/\`，测试全部相对 \`backend/tests/\`，Web 文件相对 \`frontend/src/\`。**不要求 P00 一次建齐**；只在实现当前阶段时创建其文件。

### 4.1 开发责任边界

- **ChatGPT / 本方案负责**：产品与技术选型、模块职责、接口结构、关键算法/流程、异常语义、开发阶段任务拆解、验收条件与技术取舍。
- **Codex 负责**：检查实际版本 API、按指定文件编码、补本次局部测试、调试执行、记录真实结果与 commit；不得“根据自己的判断”引入新的 Agent 框架、数据库、缓存、微服务或重构整仓库。
- **允许 Codex 决定的细节**：变量名、局部函数拆分、日志措辞、合适的 Pydantic 类型标注、当前官方 API 的小差异、适量内部异常类；不能改变外部合同、业务边界、状态语义或依赖方向。
- **发生冲突时**：如果锁定版本中的 API 与本规格不兼容，先采取最小等价方案并记录确切差异；若需要更改协议、核心模块边界、技术选型或阶段范围，**停止该部分开发，提交证据等待审核**。禁止悄悄绕过。
- **一次性任务包**：每阶段按本文件列出的 A/B/C... 子任务逐项实施；Codex 本次只接受其中一个子任务，除了当前调用链必要文件，不读取整个上游或整个仓库；每次只测试当前新改内容及直接受影响接口。
- **文件可裁剪规则**：列表中的文件为内容及职责的归属指引，而不是鼓励为 10 行代码硬拆 5 个文件。如果两个文件实际只包含一行调用，可保留在现有文件并记录；但禁止合并不同状态/安全边界以省文件。

### 4.2 固定数据/接口名称

| 对象 | 必须有的字段或方法 | 约束 |
| --- | --- | --- |
| \`Thread\` | \`id, title, created_at, updated_at\` | 仅会话身份；不当成一次执行 |
| \`Run\` | \`id, thread_id, status, started_at, finished_at, error_code\` | 一次请求；服务端终态是真实来源 |
| \`AgentState\` | \`messages\`，P04 新增 \`todos\`，后续只存 artifact/evidence ID | 使用 LangGraph/LangChain state，不能无限堆子任务文本 |
| \`TaskRecord\` | \`task_id, run_id, kind, status, result_ref, error\` | 与父图状态独立；首次在内存执行，不宣称跨进程恢复 |
| \`ToolResult\` | \`ok, content, error_code?, artifact_ids?, source_ids?\` | 错误/副作用未知另有执行元数据；禁止工具只返回无法解析的异常文字 |
| \`Artifact\` | \`id, thread_id, run_id?, name, path_internal, size, sha256\` | 外部只能传 artifact_id 或虚拟路径 |
| \`Evidence\` | \`id, source_type, url_or_document_id, location, excerpt\` | 只有真实抓取/解析获得的才能标来源 |
| \`RunEvent\` | \`event_id, run_id, thread_id, type, timestamp, payload, task_id?\` | SSE 实时展示；服务端 Run 状态最终裁决 |
| \`SkillMeta\` | \`name, description, path, allowed_tools?\` | SKILL.md 指令不能绕过执行权限 |

统一 API 前缀 \`/api\`；P02 规定 \`POST /api/threads\`、\`GET /api/threads\`、\`POST /api/threads/{thread_id}/runs\`、\`GET /api/runs/{run_id}\`、\`GET /api/runs/{run_id}/events\`。P03 增加上传、文件列表与产物下载，P06 补完善取消。新增字段只能在真实阶段实现，不得在 P00 把所有领域模型先空建一遍。

### 4.3 一致的工程约定

1. 后端包名永远是 \`minideerflow\`；包内目录按 \`api/\`、\`core/\`、\`agents/\`、\`tools/\`、\`runtime/\`、\`workspace/\`、\`research/\`、\`knowledge/\` 逐步生成。API 不执行底层 SQL，也不直接读取用户上传路径；Harness 通过注入 Tool/Service 获取业务能力。
2. Async 优先：FastAPI 异步路由、LangChain \`ainvoke/astream\`、受控协程任务；阻塞型 PDF 解析/CPU 操作应放线程而不是阻塞事件循环。首版只运行一个应用 Worker。
3. ModelProvider 统一首选 \`langchain-openai\` 中 \`ChatOpenAI\`，通过 \`MODEL_NAME\`、\`MODEL_API_KEY\`、\`MODEL_BASE_URL\` 配置，当前只保证**一个经 P01 实测支持工具调用的提供方**；其它“OpenAI 兼容”服务不自动宣称都支持 Tool Calling。
4. 时间均用 UTC ISO-8601，ID 用 UUID 字符串。SQLite 业务库 \`data/runtime.sqlite3\`，Checkpoint 可使用单独 \`data/checkpoints.sqlite3\`；目录属于 Git 忽略内容，路径通过配置统一传入。**所有状态迁移由 Runtime 服务写入，不由前端或模型文本推测。**
5. 局部测试文件名 \`test_<module>.py\` 对应被修改模块；跨接口改动才补直接消费者测试。Mock 与真实云端 Smoke 分开，不因一个阶段完成自动跑全套 E2E。
6. 参考上游一律基于 \`https://github.com/bytedance/deer-flow/blob/v2.0.0/\` 的具体源码路径；**参考调用链与不变量，不复制整仓，也不把上游源码全文输入 Codex**。

## 5. 每阶段逐文件实施规格（先做本阶段，审查后继续）


### P00 — 工程初始化（完整执行计划，未开始）

**任务编号**：P00  
**目标**：从现有只有文档的 GitHub 仓库，建立一个能在 PyCharm 中启动、断点调试、单独测试的最小 FastAPI 后端。P00 的交付是“可复现的工程基线”，**不是 Agent 产品功能**。  
**执行者**：本地 Codex；在专用分支操作；完成后等待人工验收，不进入 P01。  
**技术定案**：Python 3.12、uv、FastAPI、Pydantic、Uvicorn、pytest、httpx、ruff。当前不需要连接模型 API。

#### P00.1 现状检查与 Git 安全

1. 在 PyCharm 中打开克隆的 https://github.com/Felix0410/Agent 仓库根目录；本地若尚未克隆，先通过 PyCharm 的 Clone Repository 完成，不再新建一个嵌套 Python Project。
2. 查看 Git remote、当前分支、状态、已有文件和未提交改动。保留 README、docs/ARCHITECTURE.md、docs/DEVELOPMENT.md；遇到未知文件或本地修改先报告，不能覆盖或重置。
3. 在干净 main 基础上创建 feat/p00-bootstrap 开发分支；如果分支已存在，先核查再沿用，不强行覆盖。不得直接把业务代码推到 main。
4. 查看 macOS、Git、Python、uv 的版本；如缺少 Python 3.12 或 uv，再安装到用户环境。不修改系统 Python，不使用全局 pip 给这个项目装依赖。
5. P00 不需要克隆 DeerFlow。仅参考其 Agent 工厂的分层思想，必要时查看固定 v2.0.0 的 backend/packages/harness/deerflow/agents/factory.py；不搬运整套源码。

**交付**：记录 Git 基线 SHA、系统与工具版本、环境问题。无法安装或运行时明确标记 BLOCKED，不用伪造成功。

#### P00.2 最小工程布局

项目名称为 mini-deerflow，Python 包名定为 minideerflow。使用 src 布局和 backend 独立的 uv 项目；目录按实际需求创建：

~~~text
Agent/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT.md
├── .gitignore
├── .env.example
└── backend/
    ├── pyproject.toml
    ├── uv.lock
    ├── src/
    │   └── minideerflow/
    │       ├── __init__.py
    │       ├── main.py
    │       └── config.py
    └── tests/
        ├── test_health.py
        └── test_config.py
~~~

虚拟环境由 uv 管理，放在 backend/.venv 并忽略提交。config.py 只放必要配置，如果最终没有值得独立的配置逻辑，可以在代码审核中简化。不要提前创建空的 agents、subagents、tools、mcp、skills、runtime、knowledge、frontend 等模块。

#### P00.3 依赖与版本管理

- Python 3.12；使用 uv 管理项目及 lockfile，提交 backend/pyproject.toml 和 backend/uv.lock。
- 本阶段运行依赖仅 FastAPI、Uvicorn 和实际需要的 Pydantic 配置库（如 pydantic-settings）；开发依赖为 pytest、httpx、ruff。
- 使用 pyproject.toml 的 dev dependency group，按照实际配置运行 uv sync --group dev；不要混淆 dependency group 与 optional extra 参数。
- 本阶段不安装 LangChain、LangGraph、MCP SDK、Docling、Chroma、Node.js、Redis、RabbitMQ、数据库驱动或 Docker。这些在对应阶段引入。
- 依赖小版本由 Codex 在本机确认安装成功、生成锁文件后锁定。不把尚未验证的版本组合写成“已通过”。

实际命令以 backend 为工作目录，开发时预期：

~~~bash
cd backend
uv sync --group dev
uv run python -c "import minideerflow"
uv run uvicorn minideerflow.main:app --reload --host 127.0.0.1 --port 8000
~~~

请实际验证这些命令；如因项目打包方式调整，README 应使用真正验证过的命令，不得保留失效示例。

#### P00.4 应用入口、配置与运行

**健康检查**：GET /health 无需密钥和数据库；HTTP 200，返回 JSON 对象：

~~~json
{"status":"ok"}
~~~

这是进程存活接口，不代表 LLM、MCP 或知识库就绪。暂不实现 /chat、/threads、/runs、SSE、Tool Calling、前端和 Agent 框架。

**配置**：只需要 APP_ENV（默认 development）和 LOG_LEVEL（默认 INFO）等当前会用到的配置。可使用 pydantic-settings 统一加载并校验；没有 .env、没有 MODEL_API_KEY 时仍应正常启动。根目录 .env.example 只包含空值/示例值，不能提交真实 .env 或密钥；日志不可输出敏感环境变量。

**实现原则**：一个简洁的 FastAPI 应用和配置对象即可。可保留以后扩展的导入边界，但不要提前构建复杂的依赖注入容器、全局异常树、中间件工厂和十几个无实际用途的模块。

**PyCharm 配置**：直接打开 Agent 仓库；Python Interpreter 指向 backend/.venv/bin/python；Uvicorn Run/Debug Configuration 使用 backend 作为工作目录，模块 uvicorn，参数 minideerflow.main:app --host 127.0.0.1 --port 8000。能在入口/配置代码中设置断点；如果 Codex 不能操作本机 IDE，应明确把 PyCharm 手工验证列为“待用户确认”，不能虚称已经测试。

#### P00.5 局部测试范围（不得全量测试）

本阶段只验证 P00 本次新增的应用入口、配置、包管理及安全忽略规则：

| 局部验收项 | 最小验证方法 | 必须看到的结果 |
| --- | --- | --- |
| Python 包可安装 | 在 backend 运行 uv sync --group dev | 依赖安装成功，锁文件存在 |
| 包导入 | uv run python -c "import minideerflow" | 无导入错误 |
| 健康接口 | pytest 的 FastAPI TestClient | GET /health 为 200，JSON 严格为 status=ok |
| 配置默认值 | 不设置 .env 运行配置测试 | 无模型 Key 时成功读取默认环境 |
| 配置错误 | 如有受校验的字段，输入非法值 | 明确校验失败而非静默忽略 |
| 静态检查 | uv run ruff check src tests | 无当前代码错误 |
| 真实服务启动 | uv run uvicorn，再 curl 127.0.0.1:8000/health | 真正返回 200 与 JSON |
| Git 安全 | git status 与 git check-ignore | .env、.venv、缓存不被跟踪 |

P00 只运行 tests/test_health.py 和 tests/test_config.py（如果确实创建）；无须执行 Research、RAG、Sub-Agent 或后续模块测试。若版本/环境导致测试命令与上表不同，以实测结果为准并解释。TestClient 与真实 Uvicorn curl 结果应分别报告，不混为一谈。

不要为了“测试完整”临时创建没有业务意义的测试框架；**当前新增/修改内容及直接影响范围之外不做重复测试**。

#### P00.6 Codex 工作步骤与提交规则

按以下顺序完成：核查仓库/环境 → 建立最小 Python 包和 uv 依赖 → 写 main.py/config.py 和健康检查 → 写局部测试、.gitignore、.env.example → 实际安装和运行测试 → 更新 README 的真实启动方法 → 检查 Git 变更 → 提交专用分支。

Git 提交例：chore: bootstrap minimal FastAPI backend with uv。只能提交计划内源代码、测试、锁文件和文档更新；不提交虚拟环境、密钥、个人资料或运行产物。

如果已配置 GitHub 访问，可以把 feat/p00-bootstrap 分支推送到远端，方便人工审核；不自动合并 main、不改其他分支。如果认证失败，仅报告本地 commit 与错误，不强制改认证方式。

开发完成后，仅更新 `docs/progress/P00.md` 为 PENDING_REVIEW，并记录 Git SHA、测试命令、结果与未验证项。审核通过后才标 ACCEPTED。**当前仅提交本计划书时，P00 仍为 PLAN_READY（未开发）**。本文件作为开发计划，不记录执行日志。

#### P00.7 必须满足的验收标准

- [ ] 从既有仓库安全建立开发分支，没有改坏用户未提交内容。
- [ ] Python 3.12、uv、backend/pyproject.toml、backend/uv.lock 配置可复现。
- [ ] 后端包 minideerflow 可导入；无多余空模块或复杂架构。
- [ ] 无 .env 与模型密钥也能启动 GET /health，HTTP 200，返回 status=ok。
- [ ] 本阶段健康接口、配置、导入、ruff、真实 Uvicorn/curl 验证有执行证据。
- [ ] .env、虚拟环境和临时缓存不会被提交。
- [ ] README 说明真正可用的安装、启动、测试与 PyCharm 解释器。
- [ ] Codex 给出变更文件、命令和结果、未测试项及原因、Commit SHA 与风险。
- [ ] PyCharm Run/Debug 由本机实测或如实记录待人工确认。
- [ ] 没有引入模型调用、LangGraph、SQLite、RAG、MCP、前端、Docker；没有自动启动 P01。

**P00 完成定义**：一台干净的 macOS Python 3.12/uv 开发机可安装项目，在 PyCharm 中查看并调试一个真正运行的 FastAPI 服务，/health 返回预期结果；这一阶段不要求 AI 对话。

#### P00.8 交给 Codex 的执行指令

> 请先阅读 README.md、docs/ARCHITECTURE.md 以及 docs/DEVELOPMENT.md 的“P00 — 工程初始化”章节。这次**只完成 P00**，从当前 GitHub 仓库创建/复用 feat/p00-bootstrap 分支，先核查已有文件和未提交改动；使用 Python 3.12 + uv 创建最小 FastAPI 后端（src/minideerflow 包、/health、极简配置、uv.lock、.gitignore、.env.example、pytest/ruff）。不复制 DeerFlow，不提前开发 Agent、LangGraph、数据库、MCP、RAG、前端或 Docker。仅运行 P00 新增/修改内容及直接受影响接口的测试，再验证真实 Uvicorn 健康接口。更新 README 与 `docs/progress/P00.md`，提交当前开发分支并汇报测试命令、结果、未测项和完整 SHA。不要合并 main，也不要开始 P01，提交后等待我审核。

### P01 — 最小可运行 Agent（Model → Tool → Model）

**业务链**：用户给出文本 → \`LeadAgent\` 收到消息 → 模型自行决定直接答复或调用 \`calculate\` → 工具执行 → ToolMessage 回模型 → 返回答复。此阶段 CLI 验证即可，不加 Thread/Run/数据库。

**固定技术**：\`langchain\`（\`create_agent\`）、\`langchain-openai\`（\`ChatOpenAI\`）、LangGraph 由 Agent 内部使用；不要自己画固定 Planner/Executor 图。使用环境变量 \`MODEL_NAME\`、\`MODEL_API_KEY\`、\`MODEL_BASE_URL\`。模型不支持 Tool Calling 则 Smoke 标记 BLOCKED，不能假装工具运行成功。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`core/model.py\` | \`build_chat_model(settings) -> BaseChatModel\`。只负责配置 \`ChatOpenAI\`（model/key/base_url/timeout）；缺 key 或 model 时抛出可读配置错误；不在 import 阶段读取/连接模型。 |
| \`agents/lead.py\` | \`build_lead_agent(model, tools, checkpointer=None)\`：调用 \`langchain.agents.create_agent\`，配置简短系统提示、工具集合与可选 Checkpointer；返回框架可运行 Agent，不手写第二套 Agent 循环。 |
| \`tools/calculator.py\` | \`calculate(expression: str)\`：只允许数字、小数、四则、括号、有限一元正负，使用显式 AST 白名单解析，**禁止 eval、exec 与任意函数调用**。结果为字符串或结构化 ToolResult；非法表达式返回确定性错误。 |
| \`cli.py\` | 从终端读取一个输入，构造模型与工具，\`agent.ainvoke({"messages":[...]})\`，输出最终 assistant 内容；隐藏 key，错误返回非零退出码。 |
| \`core/config.py\` | 基于 P00 配置对象增补模型参数与校验，保留无模型 Key 仍可运行 \`/health\` 的性质；只有调用 Agent 时才必须提供密钥。 |
| \`tests/test_calculator.py\` | 正常算式、除零、非法字符、函数调用、超长表达式。 |
| \`tests/test_lead.py\` | Mock ChatModel 验证一次无工具回答和一次 Tool Call/ToolMessage 循环；不依赖网络。 |
| \`README.md\` | 加入仅 P01 实际成功验证过的 CLI 用法与模型配置，不声称尚未实现 Web。 |

**实现次序**：P01-A 添加 ModelFactory 与一个工具 → P01-B build_lead_agent/CLI 与 Mock 测试 → P01-C 有真实 Key 时做一次合法 Tool Calling Smoke。按 P01-A、B、C 小任务逐个交付，不得一次性引入 MCP 或 Sub-Agent。

**局部验收**：实际看到模型产生的 \`tool_call\`、工具执行结果和最终答复；\`uv run pytest tests/test_calculator.py tests/test_lead.py\`，以及受影响的 config 测试。健康检查没有因新增配置被破坏时只补直接受影响测试。**P01 代码接口的 Tool 类型/Agent 构造以已安装依赖的实际签名为准，必要的兼容修正须报告，不授权改变架构。**

**DeerFlow 参考**：\`backend/packages/harness/deerflow/agents/factory.py\`、\`agents/lead_agent/agent.py\`（两路径均以前缀 \`backend/packages/harness/deerflow/\` 为根）。

### P02 — Thread / Run / SQLite Checkpoint / SSE / 极简 Web

**业务链**：浏览器创建 Thread → POST Run 获取 run_id → 后端在受管任务中运行 \`lead_agent.astream\` → 发布 SSE token/tool/status → SQLite 持久化图历史及 Run 终态 → 浏览器查看对话。**API 不能直接在 HTTP 请求内等待整个长任务结束。**

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`runtime/models.py\` | Pydantic \`ThreadDto\`、\`RunDto\`、\`RunStatus\`、\`EventEnvelope\`；明确 CREATED/RUNNING/SUCCEEDED/FAILED/CANCELLED 状态；ID 为 UUID。 |
| \`runtime/db.py\` | SQLite 数据源初始化及关闭（\`aiosqlite\` 或等价，应用 lifespan 托管）；建 \`threads\` / \`runs\` 最小表，独立于 Checkpointer。SQLite 写入序列化，避免并发事务锁冲突。 |
| \`runtime/repository.py\` | \`create_thread/list_threads/get_thread/create_run/get_run/transition_run\`；终态不能重新 RUNNING，同一 Thread 不能有两个运行中的 Run。用 SQLite 事务保证检查/写入在同一并发边界。 |
| \`runtime/checkpoints.py\` | 单独创建、关闭 \`AsyncSqliteSaver\`（来自经验证的 \`langgraph-checkpoint-sqlite\`），以 \`thread_id\` 配置 \`configurable\`，把 saver 注入 P01 Agent 工厂；启动/关闭绑定 FastAPI lifespan。 |
| \`runtime/events.py\` | \`EventBus.publish(run_id,event)\` 和 \`subscribe(run_id)\`；Run 内事件序号递增，用有界内存环形缓冲区解决 POST Run 之后才连接 SSE 导致的初始事件丢失；不承诺持久历史回放。消费者慢时有明确 buffer/丢失策略。 |
| \`runtime/runner.py\` | \`start_run(thread_id, text)\` 创建 Run、管理后台 asyncio Task，使用 \`agent.astream\` 归一化消息/工具事件；在 \`try/except/finally\` 中准确写入终态并发布对应事件，模型说“完成了”不能当作 SUCCEEDED。 |
| \`api/threads.py\` | \`POST /api/threads\`、\`GET /api/threads\`；只调用 repository，不导入图或模型逻辑。 |
| \`api/runs.py\` | \`POST /api/threads/{thread_id}/runs\` 返回 run_id；\`GET /api/runs/{run_id}\` 查询服务端状态；\`GET /api/runs/{run_id}/events\` 使用 \`text/event-stream\` SSE。 |
| \`main.py\` | 保留 P00 /health，在 lifespan 中创建/关闭 Runner、SQLite、Checkpointer、事件服务并 include_router；默认只在 localhost、单 worker。 |
| \`frontend/package.json\`、\`frontend/src/main.tsx\` | 使用 Vite + React + TypeScript 建最小 Web 入口；不引入 Next.js、Redux、复杂 UI 设计系统。 |
| \`frontend/src/api/client.ts\` | \`createThread/startRun/getRun\`，\`subscribeRunEvents\` 统一封装 HTTP/SSE 处理（POST 和 GET 为两个请求）。 |
| \`frontend/src/App.tsx\` | 最小聊天输入/消息列表/等待状态；按实际 RunEvent 更新流式显示，最终以 \`GET /api/runs/{id}\` 为状态权威。 |
| \`tests/test_runtime.py\`、\`tests/test_runs_api.py\` | Thread/Run 状态迁移、互斥、Graph Checkpoint 读写、SSE 事件顺序、Agent 失败不报成功；Mock 模型运行即可。 |

**确定性 API**：\`POST /api/threads\` 返回 \`thread_id\`；\`POST /api/threads/{id}/runs\` 接收 \`{"message":"..."}\` 返回 \`{"run_id":"...","status":"CREATED"}\` 或真实的初始状态；\`GET /api/runs/{id}\` 返回明确终态；SSE 每条有 \`event_id,run_id,thread_id,type,timestamp,payload,task_id?\`。事件不等于数据库交易记录，重连只能在**本次 Run 的保留窗口**回看；超出窗口时要求用户重新拉取 Run 状态，不得无条件承诺无损回放。

**实现次序**：P02-A Repository/Checkpointer → P02-B Runner/API/SSE → P02-C 前端薄聊天界面。若模型执行需要持久化长 Run，P02 先单进程托管任务，不引入 Redis/MQ。P06 再完善 Cancel 和崩溃后核查。

**局部验收**：创建 Thread、Run、流式事件到终态；服务重启能读回历史 Checkpoint；事件不漏发订阅前的开始事件；同 Thread Run 冲突被拒绝；错误 Run 不显示完成。只测 \`tests/test_runtime.py\`、\`tests/test_runs_api.py\` 和当前 Web API 消费逻辑。

**DeerFlow 参考**：\`runtime/runs/manager.py\`、\`runtime/runs/worker.py\`、\`runtime/checkpointer/async_provider.py\`、\`app/gateway/routers/runs.py\`（路径根据架构文档里的上游根目录定位）。

### P03 — Workspace、文件安全与 Artifact

**业务链**：上传 → 获取 \`file_id\` → Agent 使用白名单文件工具读取/写出新文件 → 保存 \`artifact_id\` → 浏览器下载。文件数据进入 Thread 隔离目录，不进入 Git，不传宿主机绝对路径给 LLM。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`workspace/models.py\` | FileRecord、ArtifactRecord、文件操作错误类型；文件记录包含 thread_id、run_id?、相对路径、sha256、size、mime、kind。 |
| \`workspace/storage.py\` | \`save_upload/open_text/write_text/list_files/get_artifact\`：使用 \`data/workspaces/{thread_id}/\` 隔离，先校验归属和安全路径，原子写入、限制文件大小和类型；使用 no-follow/目录句柄或等价安全策略防符号链接/TOCTOU，而非只靠字符串前缀。 |
| \`workspace/repository.py\` | SQLite 中新增 files/artifacts 表，记录来源、归属、文件大小与内部存储名，下载只能查登记过的 artifact_id。 |
| \`tools/file_tools.py\` | \`list_files/read_text/write_text\` 三项工具；工具只能访问授予 Thread 的虚拟目录，不开放 Path 对象、绝对地址、Shell 或通用 Python 解释器。 |
| \`api/files.py\` | \`POST /api/threads/{thread_id}/files\` 上传、\`GET /api/threads/{thread_id}/artifacts\` 列表、\`GET /api/artifacts/{artifact_id}\` 下载，校验文件归属和下载 MIME。 |
| \`frontend/src/components/FilesPanel.tsx\` | 上传、文件列表、下载；请求失败/文件过大有明确提示。 |
| \`tests/test_workspace.py\`、\`tests/test_files_api.py\` | 上传/读/写/下载、文件大小/路径穿越、符号链接、跨 Thread 访问、并发写冲突和失败清理。 |

**关键实现固定**：初版只接受 \`.txt/.md/.csv/.json\` 等可安全解码的文本格式作为 \`read_text\`，PDF 只保存上传而不宣称可以读取（P08 才解析）。\`write_text\` 使用临时文件加原子替换，默认禁止覆盖已存在产物，返回 Artifact ID。单用户也要做 Thread 归属判断，因为工具不应跨会话访问。文件工具的权限必须在 Python 执行层检查。

**实现次序**：P03-A Storage/路径安全 → P03-B Tool + SQLite Metadata/API → P03-C 文件面板及下载。局部测试只测新增文件链路和直接调用方，不重测所有 Agent。

**DeerFlow 参考**：\`sandbox/security.py\`、\`sandbox/local/local_sandbox.py\`、\`app/gateway/routers/uploads.py\`。本地 Sandbox 不等于不可信命令安全沙箱，不复制 Host Bash。

### P04 — Todo 规划、任务委派与 Sub-Agent

**业务链**：复杂目标 → 模型调用 \`write_todos\` 更新结构化计划 → \`task\` 工具指定角色和任务目标 → Dispatcher 限制并发、裁剪上下文、构造子 Agent → 子 Agent 调用允许的 Tool → 返回短摘要+证据/文件引用 → Lead 汇总。简单问题不需要强制规划。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`agents/state.py\` | 基于实际 LangChain AgentState 扩展 \`todos\`；字段为 \`todo_id,title,status\`，合并规则必须保证更新同 ID 而非无限追加；并发更新先在父 Agent 串行归并。 |
| \`tools/todo_tool.py\` | \`write_todos(items)\` 验证状态 \`pending/in_progress/completed\`、合法 ID 和一次更新数上限；写入真实 State 并发布 todo_updated，禁止只输出自然语言 Todo。 |
| \`agents/subagents/config.py\` | 固定 general、research 两种 \`SubAgentSpec\`：name/system_prompt/allowed_tools/max_steps/timeout；初版禁止子 Agent 继续使用 task。 |
| \`agents/subagents/dispatcher.py\` | \`dispatch(spec,input,parent_context)->TaskResult\`；\`asyncio.Semaphore(3)\` 限制每 Run 总并发；使用子代理独立 messages，不拷贝父完整聊天日志；工具集取父授权与角色 allowlist **交集**。 |
| \`agents/subagents/executor.py\` | 使用 P01 Agent 工厂构建 child Agent，**不复用父 Checkpointer**（可设 False/None，以已锁版本实际语义为准），执行 asyncio 超时和错误归一；返回摘要、状态、证据/产物 ID，不能把完整子代理对话塞回父状态。 |
| \`tools/task_tool.py\` | 模型可调用的 \`task(agent_type,description)\`，由当前 Runtime 注入 task_id/run_id/权限上下文，不读取随意的全局单例；返回可序列化任务摘要。 |
| \`runtime/task_registry.py\` | 进程内 TaskRecord 生命周期 PENDING/RUNNING/COMPLETED/FAILED/CANCELLED/TIMED_OUT，输出对应 run 事件；默认无跨重启保证。 |
| \`frontend/src/components/TodoPanel.tsx\`、\`TaskPanel.tsx\` | 按 todo_updated/subtask_* 更新视图；不靠模型文本判断子任务终态。 |
| \`tests/test_todos.py\`、\`tests/test_subagents.py\` | 同 ID Todo 更新、非法转移、实际委派、角色权限、并发上限、超时、任务失败、父子 Checkpointer 隔离。 |

**默认约束**：\`MAX_SUBAGENT_CONCURRENCY=3\`、\`MAX_DELEGATION_DEPTH=1\`，每个子任务有 \`max_steps\` 和超时；子 Agent 默认只读 Workspace，写文件需要单独明确授权以避免并发覆盖。子任务结果未知要标记 UNKNOWN/FAILED 类别，不因为父模型在报告中写“已完成”就更改真实状态。

**实现次序**：P04-A Todo Tool/State → P04-B 一个串行子代理 → P04-C 三个并发以内、超时/取消/事件 → P04-D UI 与受影响合同测试。禁止把调度改成大型任务队列或随意扩展角色列表。

**DeerFlow 参考**：\`agents/middlewares/todo_middleware.py\`、\`tools/builtins/task_tool.py\`、\`subagents/executor.py\`，注意这些文件根路径均为 \`backend/packages/harness/deerflow/\`。父图 Checkpoint 不保证进程内子任务精确恢复。

### P05 — 统一 ToolRegistry、MCP 适配器与 Skills

**业务链**：Lead 请求可用工具 → Registry 合并内置工具与经批准的 MCP 工具 → ToolExecutor 统一校验权限/超时/异常 → 模型按需选择工具；当任务需要某种工作方法时，\`list_skills/read_skill\` 只加载对应 SKILL.md 的正文。**MCP 是工具来源，Skill 是执行说明，二者不是同一套运行机制。**

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`tools/registry.py\` | \`ToolRegistry.register/get/list_allowed\`：按唯一名字注册工具（重名直接拒绝，不静默覆盖）；每项含 ToolSchema、权限级别、超时与来源；合并 P01、P03、P04 工具及 MCP Tool。 |
| \`tools/executor.py\` | \`execute(tool_name,arguments,policy,context)\`：先检查名字、权限、参数，再执行指定工具；按工具声明区分 read/write，超时、错误统一封装；未来网络有副作用操作遇未知结果不得盲重试。若 LangChain 的 tool lifecycle 与调用链不匹配，使用框架支持的 Middleware 包裹执行，避免另造与框架竞争的工具主循环。 |
| \`tools/mcp_adapter.py\` | 用 \`langchain-mcp-adapters\` 的现成 Client/工具转换接入配置好的 MCP Server，映射工具名/Schema/说明，执行统一转交 ToolExecutor；MCP 连接失败分类为 \`MCP_UNAVAILABLE\`，不能影响内置工具。 |
| \`core/mcp_settings.py\` | 使用明确的本地配置（如 \`MCP_SERVERS\` 或单个受控配置文件）声明 server_id、transport、URL/command、timeout、allowlist；第一版只允许用户预先配置的只读 Server，禁止模型自动新增任意 stdio command。 |
| \`skills/models.py\` | \`SkillMeta(name,description,path,allowed_tools)\`，记录必要元信息，不将所有正文常驻系统 Prompt。 |
| \`skills/loader.py\` | \`discover_skills(root)\` 读取受控本地 Skills 目录，\`load_skill(name)\` 使用安全 YAML 解析（需要时加入 PyYAML），验证名称唯一、正文大小上限、所需工具是否存在；禁止从任意 URL 自动下载安装 Skill。 |
| \`tools/skill_tools.py\` | \`list_skills()\` 输出名称/简介，\`read_skill(name)\` 返回本地 Skill 必要正文；模型只在需要时加载，激活不改变执行器 allowlist。 |
| \`skills/public/example-research/SKILL.md\` | 一个实际可执行的最小模板：输入目标、检索步骤、来源标注、输出规范；当前不实现 P07 的全部 Research 业务。 |
| \`tests/test_tool_registry.py\`、\`tests/test_mcp.py\`、\`tests/test_skills.py\` | 重名、拒绝越权、参数错误、超时、MCP 断开、坏 YAML、Skill 工具不存在、超长 Skill、只读权限下执行写工具被拒绝。 |

**固定权限策略**：工具默认 \`DENY\`，按 Run/角色显式构造 \`allowed_tools\`；子 Agent 可用工具是“父权限 ∩ 角色权限 ∩ 本次任务授权”，任何 Skill 提示都无权提升权限。ToolExecutor 对工具的名字和参数做可复验的检查，输出有明确错误代码、脱敏 Trace 和长度上限。不允许把远程 MCP 返回文本当成系统指令。

**实现次序**：P05-A Registry/Executor → P05-B 单个只读 MCP Server/失败处理 → P05-C Skill Parser/Tool → P05-D 权限与直接受影响的 Agent Tool Calling 测试。

**局部验收**：不改 Lead Agent 的核心循环即可注册一个新的 MCP Tool 与一个 Skill；连通实际可用的只读 MCP Server 或如实说明环境无法连接；工具不可通过 Skill/委派绕过授权。仅测对应的 registry/mcp/skills 测试及直接 Tool 集成。

**DeerFlow 参考**：\`backend/packages/harness/deerflow/tools/tools.py\`、\`mcp/tools.py\`、\`skills/parser.py\`、\`skills/tool_policy.py\`、\`agents/middlewares/skill_activation_middleware.py\`，所有均位于 \`backend/packages/harness/deerflow/\` 根下。

### P06 — 上下文压缩、预算、取消与恢复边界

**业务链**：Run 启动时设置模型/工具/时间预算 → 每次调用前后记录用量 → 长工具输出进入 Artifact，仅把短摘要/ID 注入消息 → 接近上下文限制时压缩旧消息并保护用户目标、Todo、引用与文件 ID → 任务结束时准确结算 Run；取消或服务重启走独立的 Runtime 状态逻辑。**上下文压缩不替代 Checkpoint，Checkpoint 不替代 RunService。**

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`runtime/budget.py\` | \`RunBudget(max_steps,max_tool_calls,max_seconds,max_input_tokens_estimate)\`；\`BudgetTracker.before_model/before_tool/record_usage\`，触发上限后返回 \`BUDGET_EXCEEDED\` 与统计。估算 token 与提供方真实 usage 分开标记，禁止把估算说成实际账单。 |
| \`agents/context.py\` | \`ContextManager.prepare(messages,todos,refs,budget)\`：保留最近交互和关键用户约束；将旧消息摘要化，必要时调用已配置模型进行 summary；保护当前 Todo、真实 source_ids、artifact_ids，不丢失未完成步骤。 |
| \`agents/middleware.py\` | 通过官方 \`AgentMiddleware\` 或当前 \`create_agent\` 支持的中间件装配预算、工具输出长度、异常转换、摘要策略；**不重新实现模型/工具循环**。对支持的官方 Middleware 优先直接配置，仅对缺少的行为实现小型自定义包装。 |
| \`runtime/usage.py\` | \`UsageRecord(run_id,task_id?,model,input_tokens?,output_tokens?,estimated)\`，统计模型/子任务/工具耗时；缺失供应商 usage 时保留 unknown/estimated 标志，不虚构 0 成本。 |
| \`runtime/runner.py\`（修改） | 添加取消信号（\`asyncio.Event\` 或等价）与 \`request_cancel(run_id)\`；新工具执行前检查取消；已经开始的外部副作用不能假定立即停止或自动撤销；按真实结果写终态。 |
| \`runtime/repository.py\`（修改） | 增加 \`CANCELLING\`、\`INTERRUPTED/UNKNOWN\` 状态需要时迁移；启动时检查旧 RUNNING 并标记 \`INTERRUPTED/UNKNOWN\`，不自动重新执行未知副作用动作。 |
| \`api/runs.py\`（修改） | \`POST /api/runs/{run_id}/cancel\`：幂等请求，返回当前真实状态；已终结 Run 不重新启动。 |
| \`tests/test_budget.py\`、\`tests/test_context.py\`、\`tests/test_cancel_recovery.py\` | 超限停止、摘要保护、真实/估算区分、取消后不启动新工具、服务重启孤儿标记和外部写工具 UNKNOWN 不被盲重试。 |

**算法/约束固定**：
- 每 Run 默认 \`max_steps=40\`、\`max_tool_calls=30\`、\`max_seconds=600\`（可在配置中调整），保护系统不进入无限循环。模型使用量若不支持精确记录，标 \`estimated\`。
- 工具结果文本超过建议阈值 12 KB 时存入 Artifact 并给模型短摘要和引用 ID；裁剪不能破坏引用可定位性。
- ContextManager 只摘要较旧、已完成的交互；当前用户指令、尚未完成 Todo、关键证据/文件 ID 以结构化方式单独注入；摘要失败则按预算安全退出，不能静默丢上下文后继续。
- 重启时只恢复已经落盘的 Thread/Graph 数据与标记 Run，**不自动恢复进程内并发 Sub-Agent**；有副作用操作的结果 UNKNOWN 不重试。
- 对同一个 run_id 重复 cancel 应返回确定状态；若仍在调用外部工具，显示 CANCELLING/UNKNOWN 而不是提前声称 CANCELLED。

**实现次序**：P06-A Budget/Usage → P06-B Summary + Tool Output → P06-C Cancel/Restart 核查 → P06-D 局部故障注入。测试只测当前 Budget/Context/Runner/API 的直接影响，不重跑 Research/RAG 全量评测。

**DeerFlow 参考**：\`agents/middlewares/summarization_middleware.py\`、\`tool_output_budget_middleware.py\`、\`loop_detection_middleware.py\`、\`runtime/runs/manager.py\`、\`runtime/runs/worker.py\`（均在 Harness 根下）。

### P07 — Deep Research 的完整业务实现

**业务链**：用户给出研究题 → Lead 加载 \`deep-research\` Skill → Todo 分主题 → \`search_web\` 检索 → \`fetch_webpage\` 获取页面内容 → Sub-Agent 做独立分析 → \`EvidenceStore\` 汇总真实来源 → \`ReportWriter\` 输出 Markdown Artifact → 用户下载。**不重写一套固定 Deep Research Graph**，复用既有 Lead + Task + Tools + Skills。

**联网供应商固定**：首选 **Tavily Search API** 作为单一搜索适配器；通过 \`TAVILY_API_KEY\` 环境变量配置，搜索结果必须携带真实 URL、标题、片段。若账户不可用，任务标记外部依赖阻塞并告知用户，不由 Codex 擅自扩展为多个搜索框架。网页正文抓取走受限 \`httpx\`，只允许 http/https，限制大小/时长/重定向，并显式防 SSRF（拒绝 loopback、私有、链路本地地址和 DNS 重绑定风险）。不必自行编写复杂浏览器自动化。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`research/models.py\` | \`ResearchRequest(topic,scope?,report_format)\`、\`SearchHit(title,url,snippet,retrieved_at)\`、\`EvidenceRecord(id,url,excerpt,source_status)\`、\`ResearchReport(markdown,source_ids,artifact_id)\`；来源未访问/抓取失败必须标注状态。 |
| \`research/search.py\` | \`TavilySearchProvider.search(query,max_results=5)\`：调用当前 Tavily SDK/HTTP API，转换为 SearchHit；过滤空 URL、去重、限制单次结果数；保留查询与检索时间及错误类别。 |
| \`research/fetch.py\` | \`fetch_webpage(url)\`：\`httpx.AsyncClient\` 有界超时、响应大小、Content-Type 与 SSRF/跳转检查；提取可阅读的网页文本并截断，不允许读取内网或本地文件。仅 HTTP 标题/摘要不足时明确“正文未核验”。 |
| \`research/evidence.py\` | \`EvidenceStore.add/list/get\`：保存 search/fetch 工具真实返回的 URL、片段、检索时间、状态及来源 ID；相同 URL 规范化去重。严禁模型自己生成新的“已检索来源”ID。 |
| \`research/report.py\` | \`render_markdown_report(title,findings,evidence_ids,limitations)\`：生成标题、研究方法、核心结论、对比、局限与来源清单；引用只能指向 EvidenceStore 中已经存在且满足引用条件的记录。将最终文本通过 P03 Workspace 保存为 Artifact。 |
| \`tools/research_tools.py\` | \`search_web\`、\`fetch_webpage\`、\`save_research_report\` 包装上述服务，加入 Registry 并声明超时/权限；工具的大返回内容存 Artifact/证据而非无限推给模型。 |
| \`skills/public/deep-research/SKILL.md\` | 明确输入、计划、分主题、搜索→核对、反向检索、合并、引用与停止标准；要求事实区分 verified/unverified，输出本项目支持的 Markdown 报告。 |
| \`frontend/src/components/ResearchReport.tsx\` | 展示报告、来源链接、无法验证提示和下载按钮；复用 P02 流事件、P03 Artifact API。 |
| \`tests/test_research_search.py\`、\`test_research_evidence.py\`、\`test_research_report.py\` | Mock 搜索结果转换、URL 去重、抓取失败、SSRF、虚假引用被拒绝、报告实际生成与 Artifact 下载。 |

**固定研究策略**：先由 Lead 评估问题范围，复杂任务创建 Todo；单个问题默认搜索不超过 5 条候选结果，每个 Run 总工具/Token/时间预算继承 P06；多个研究方向可由 P04 允许的 Research 子 Agent 并行检索；子 Agent 回传 **Findings + Evidence IDs + Missing** 而非全量网页文本。报告中没有真实证据的主张不得以确定性语气编成引用。只依靠搜索摘要的结论必须标记摘要级来源，不当作已精读正文。

**实现次序**：P07-A 搜索与抓取 → P07-B Evidence/引文 ID → P07-C Research Skill + 子任务报告 → P07-D UI 和一个真实网络 Smoke。测试只跑本次 research tests 和直接使用的 Tool/Artifact 接口，真实模型报告人工抽查主要来源。

**DeerFlow 参考**：\`skills/public/deep-research/SKILL.md\`、\`skills/public/systematic-literature-review/SKILL.md\`、\`backend/packages/harness/deerflow/tools/builtins/task_tool.py\`。Skill 负责工作方法而不是替代实际搜索工具。

### P08 — Docling + Chroma 多文档 RAG

**业务链**：用户从 P03 上传 PDF/Markdown/TXT → \`DocumentService\` 识别格式并调用 Parser → 保留真实页码/章节/文本结构 → Chunk → Embedding → Chroma 本地索引 → \`search_knowledge(scope,query,top_k)\` 返回真实 Evidence → Lead 生成带证据 ID 的回答；上传/解析失败或没有可用片段时拒答或标记不足。

**Embedding 决策**：使用 \`langchain-openai.OpenAIEmbeddings\` 的一个经测试支持的服务（独立 \`EMBEDDING_MODEL\`、\`EMBEDDING_API_KEY\`、\`EMBEDDING_BASE_URL\` 配置，允许明确继承模型配置但不能假定 ChatModel 与 Embedding API 一致）；不用额外部署大型本地 Embedding 推理服务。调用失败则标记索引 FAILED，不写“已建库”。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`knowledge/models.py\` | \`DocumentRecord(id,thread_id,filename,content_sha256,parser_version,index_status)\`；\`ChunkRecord(id,document_id,index_version,source_text,page?,section?,offset?)\`；\`KnowledgeHit(chunk_id,document_id,excerpt,page?,score)\`。页码无法可靠获得时为 null，不猜测。 |
| \`knowledge/parser.py\` | \`parse_document(file_ref)->ParsedDocument\`：文本直接解码；PDF 使用 Docling \`DocumentConverter().convert(path)\`，检查转换状态，提取结构化文档、页码/章节与原文。使用结构元素/provenance 保留真实位置；不要仅 export_to_markdown 后通过正则假推页码。重型同步解析放入线程，不阻塞 Async API。 |
| \`knowledge/chunker.py\` | \`chunk_document(parsed,max_chars=1200,overlap=150)\`：优先章节/段落边界，超长文本定长切片；产生稳定 \`chunk_id=hash(document_id,index_version,position,source_hash)\`，记录原文与真实位置。源文和用于召回的可选文本分开。 |
| \`knowledge/embedding.py\` | \`EmbeddingProvider.embed_documents/embed_query\`：单一模型与 API 适配，控制 batch/超时，记录 embedding model/version/dim；不把用户文档写进日志。 |
| \`knowledge/vector_store.py\` | \`ChromaIndex.upsert/delete_document/search\`：\`chromadb.PersistentClient\` 存 \`data/chroma\`，每条记录含 document_id、thread_id、chunk_id、index_version、page（可空时按驱动规则处理）；检索时强制使用 scope 过滤，返回 score/distance 的含义需准确声明。更新版本需先写新数据验证，再切换可见版本，不能混查新旧。 |
| \`knowledge/service.py\` | \`ingest_document(file_id)\`：P03 受控读取→解析→分块→Embedding→Chroma upsert→索引状态 READY；失败写 FAILED 并清理不完整版本。 \`search_knowledge(thread_id,document_ids,query,top_k)\`：校验归属和索引版本，只返回实际检索到的原文片段与引用位置。 |
| \`knowledge/repository.py\` | SQLite \`documents\`、\`index_versions\` 元数据，支持查看处理状态、重新建索引、删除过期索引；文件存储与 Chroma 不能假设有跨库事务，需要失败补偿。 |
| \`tools/knowledge_tools.py\` | \`search_knowledge\` Tool Schema、scope 白名单和 Evidence ID，不允许模型给出任意用户路径；只允许当前 Thread 已授权文档。 |
| \`api/knowledge.py\` | \`POST /api/threads/{id}/documents/{file_id}/index\`、\`GET /api/threads/{id}/documents\` 等最小接口（异步建索引可查询状态）；不能把耗时 Docling 解析直接堵塞事件循环。 |
| \`frontend/src/components/DocumentPanel.tsx\` | 上传后索引按钮/状态、文档选择、可跳转的来源页码或片段；不承诺具备完整 PDF 阅读器。 |
| \`tests/test_parser.py\`、\`test_chunker.py\`、\`test_vector_store.py\`、\`test_knowledge_api.py\` | 一份文本型 PDF/MD 解析、Chunk 位置一致性、索引检索、文档 Scope、无命中拒答、重建版本清理和失败恢复。 |

**固定检索逻辑**：V1 先 \`top_k=5\` 向量检索，命中片段附 \`document_id/chunk_id/page/section\` 及证据 ID；无可靠页码时只引用文件和片段，不伪造 PDF 页码。答案只能引用真实返回的 Evidence ID，禁止把生成摘要或虚构元数据当作原文事实。暂不做 Hybrid/Rerank、多级知识图谱和复杂智能路由，后续需有独立评测收益才扩展。

**实现次序**：P08-A Docling Parser/Chunk → P08-B Embedding/Chroma → P08-C Ingest/Search Tool 与引用 → P08-D 文档 UI 与局部金标 QA。只测 \`knowledge\` 当前模块及直接 Tool/API 消费者，不重跑 Deep Research 全套任务。

**参考**：DeerFlow 的 Workspace/Tool/Skill 接入形式；RAG 内部是我们独立实现，不把其 \`deep-research/SKILL.md\` 当向量数据库实现。Docling 官方从 \`DocumentConverter\` 返回 \`ConversionResult\`，应检查 \`result.status\` 并利用 \`result.document\` 的 provenance 信息，具体 API 用锁定版本实测。

### P09 — UI 完善、部署、定版评测与最终交付

**业务链**：在干净开发机按 README 启动 FastAPI + React → Web 创建/继续 Thread → 运行一个真实 Research 任务并下载报告 → 上传至少两份真实文档做跨文档问答 → 用 Workspace 工具生成真实文件 → 展示任务状态/错误/局部指标。这个阶段交付真实演示和可重复测量，不引入全新大功能。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| \`frontend/src/components/RunTimeline.tsx\` | 统一展示 Run 状态、Todo、Task、Tool 与 Artifact 事件，使用真实 EventEnvelope，不能从自然语言猜测进度。 |
| \`frontend/src/App.tsx\`、\`frontend/src/api/client.ts\` | 整理已有组件和异常状态、断线后的 \`GET /api/runs/{id}\` 同步；不引入复杂全站状态库。 |
| \`backend/src/minideerflow/core/logging.py\` | 统一 run_id/thread_id/task_id 的结构化摘要日志，敏感参数脱敏，不存 API Key、PDF 原文和私有响应。 |
| \`eval/cases/research.json\`、\`eval/cases/rag.json\`、\`eval/cases/files.json\` | 小型固定任务集与人工检查要求；包含明确真实来源/文档范围或确定性输出标准，不填伪造成绩。 |
| \`eval/run_eval.py\` | 调用本项目已有 API/Service 运行指定样本，记录 \`git_sha/model/config/dataset_version/latency/token_usage/error\` 与产物引用，原始结果写入 Git 忽略目录；报告标明无法运行和失败项。 |
| \`Dockerfile\` / \`backend/Dockerfile\`、\`frontend/Dockerfile\`、\`compose.yaml\` | 两个服务的单机启动；映射 Python 数据卷和必需的环境变量，不硬编码 Key；容器非 root，API 默认不无认证暴露公网。根据真实依赖控制体积。 |
| \`README.md\` | 安装、配置、PyCharm/终端启动、Docker、三条业务真实 Demo、已知局限和 DeerFlow 参考/源码许可；只列实际已实现功能。 |
| \`tests/test_release_smoke.py\`、前端对应组件测试 | 只验证本次新增部署/时间线/日志/发布合同；另实际运行三条**完整最终 Demo**，属于交付阶段约定而非每阶段全量回归。 |

**实施次序**：P09-A 前端体验/错误状态 → P09-B 定版样本和 Eval Runner → P09-C 单机 Docker/环境复现 → P09-D 三条真实 Demo、来源归属与安全复核。若没有模型/搜索/Embedding Key，明确将对应真实 Demo 标记 BLOCKED 或 NOT_RUN，不编造演示结果。

**固定评测口径**：Research 报告中实际引用有效性与人工支持度；RAG 的 Hit@K、引用可定位率、无命中拒答；文件任务实际产物校验；记录调用次数、时间和 Token（提供方返回或标 estimated）。不用 LLM 自评冒充人工真值。实测数据不足时不强行给 P95 等指标下结论。

**验收**：新环境可按 README 启动；三条演示分别拥有输入、脱敏 Run 记录、真实文件/引用、版本与失败说明；能证明工具限额、安全文件规则和外部不可用时的真实失败行为。最终是否执行全量历史 pytest/E2E 由用户另行决定，Codex 不自动扩大测试范围。

**DeerFlow 参考**：\`frontend/src/components/workspace/\`、\`frontend/src/core/tasks/context.tsx\`、\`backend/packages/harness/deerflow/runtime/runs/manager.py\`；只参考事件/界面组织，不复制完整界面与复杂运行时。

## 6. Codex 执行规则：让本地 AI 用最少上下文开发

每次仅交给 Codex：
- 本次任务 ID 与验收要求；
- 本项目当前涉及的少量源码/测试（通常 2–5 个文件）；
- 对应 DeerFlow 1–3 个明确参考文件；
- 当前真实功能摘要（`docs/progress/Pxx.md` 中的当前阶段进度与对应提交）。

先说明业务主流程，再选择框架/实现，再完成最小主链，然后处理本次功能的边界。新技术第一次出现时，说明“是什么、为什么现在引入、核心机制、替代方案”；不要为了美观创建空模块或无用设计模式。

完成后必须报告：**改动文件、真实运行命令、仅本次改动的测试及结果、未测试范围、Git SHA、发现的问题、下一步依赖**。在当前阶段 `docs/progress/Pxx.md` 中追加真实记录并标记 PENDING_REVIEW，等待用户与 Codex 审查；用户明确说开始下一阶段才继续。禁止擅自修改其他阶段的进度。

## 7. 决策与风险（本文件集中维护，不再另建决策/测试文档）

**已固定：** 独立新建项目、模块化单体、Python/FastAPI/LangGraph、React/Vite、SQLite、少量 Tools/MCP/Skills、Docling+Chroma、P00–P09 顺序、局部增量测试、逐阶段审核。

**可依据事实调整：** 锁定的具体依赖小版本、首个可用模型、联网搜索供应商；调整要写出触发原因与替代方案，不得影响架构主线。

**需警惕：** Run 状态不等于 Checkpoint；Sub-Agent 不会因为父任务落库就自动精确续跑；本地文件路径映射不是不可信代码沙箱；网页/PDF/MCP 返回不能作为高优先级指令；编排越复杂不代表任务成功率越高。

**重要取舍：** 没有当前业务/实测瓶颈，不引入 Redis、RabbitMQ、PostgreSQL、K8s、多租户、复杂权限和全能 Coding Agent。

## 8. 各阶段进度文档（唯一进度来源）

规划、技术取舍与任务步骤只保留在本文件；每个阶段单独维护一份执行记录，不重复粘贴开发任务书。**Codex 只更新当前正在执行的阶段**，其他阶段保持原样。

- [P00 进度记录](progress/P00.md)
- [P01 进度记录](progress/P01.md)
- [P02 进度记录](progress/P02.md)
- [P03 进度记录](progress/P03.md)
- [P04 进度记录](progress/P04.md)
- [P05 进度记录](progress/P05.md)
- [P06 进度记录](progress/P06.md)
- [P07 进度记录](progress/P07.md)
- [P08 进度记录](progress/P08.md)
- [P09 进度记录](progress/P09.md)

记录标准：实际执行日期、任务 ID、分支/提交 SHA、修改文件、仅本次变更涉及的测试命令与真实结果、未测/失败项、阻塞或设计偏差、人工审核意见。禁止根据“计划已写好”自动把开发状态改为完成。阶段状态为 `NOT_STARTED / PLAN_READY / IN_PROGRESS / PENDING_REVIEW / ACCEPTED / BLOCKED / DEFERRED`；未经人工验收不得设置 `ACCEPTED`。

每个阶段进度文件是该阶段状态与执行证据的唯一来源；README 与本文件不再维护一张需要同步的状态总表。
