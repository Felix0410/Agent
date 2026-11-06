# 开发方案、任务顺序与局部测试规则

> **代码可读性规范**：所有阶段代码同时遵循仓库根目录 [AGENTS.md](../AGENTS.md)：中文关键注释、较长逻辑按 1/2/3 分段、注释重点解释机制与边界，保持既定 API 和业务逻辑不变。每次 Codex 任务必须执行代码可读性自查。

**方案版本**：v1.8 · 2026-11-06  
**当前状态**：P00 代码已在 main；P01 实现在 `feat/p01-single-agent-web` 开发分支、待用户最终验收；P02 详细方案已批准并写入 `feat/p02-runtime-web`，仅设计就绪（PLAN_READY），尚未编码。各阶段真实进度独立记录在 `docs/progress/Pxx.md`，本文件只维护计划与执行规则。  
**原则**：从零构建 Mini DeerFlow，逐步增加能力。**每个阶段开始前，必须先核对真实代码、形成详细实施合同并由用户审核。** 默认一个子任务完成后停下等待审核；**用户于 2026-11-06 明确授权 P02 已有 A 之后的 B/C/D 一次性设计与连续执行**，因此本次按 [docs/tasks/P02-BD.md](tasks/P02-BD.md) 在同一次 Codex 会话中顺序完成 B→C→D，分阶段提交和局部测试，关键失败立即停止。该授权仅针对 P02 B/C/D，不能推导为 P03 以后阶段自动放行。

## 0. 阶段设计先行：每次只最终确定当前阶段

**强制执行流程（优先于下文预设文件清单）：**

1. **当前阶段现状审查（ChatGPT）**：确认 GitHub 实际代码、分支、前一阶段审核结果和 `docs/progress/Pxx.md`；检查已经存在的类、接口、测试、锁定依赖版本及本阶段实际需要参考的 DeerFlow 固定源码。不得假定先前规划的目标文件已经实现。
2. **当前阶段方案设计（ChatGPT）**：按照下面的“阶段方案交付合同”，将当前阶段真正需要做的业务主线、模块接口、逐文件职责、关键机制、编码顺序、异常与测试全部定下来。发现原先分阶段规划与实际代码冲突，先解释差异、给出最小调整建议。对重要技术选择说明为什么使用它、与替代方案的差异和引入时机。
3. **用户审核设计**：先在对话中讲清楚这阶段要做什么、每个执行文件干什么、为什么这样实现和如何验收；用户明确认可后，才将**本阶段最终可执行规格**更新到本文件对应章节并同步 GitHub。用户在 2026-11-05 已要求继续推进 P01，并追加最小 Demo 后人工测试、每任务同步前端规则；据此形成当阶段实施合同，编码完成仍需用户验收。状态为 `PLAN_READY`，**这只表示方案通过，不等于编码完成**。
4. **Codex 按规格编码**：给 Codex 的输入严格限于当前阶段已批准的细化方案、当前阶段进度文档、必要的现有源码/测试及 1–3 个准确的上游参考文件；Codex 只编码、执行当前新增或修改内容的局部测试、提交变更。它不得自主重新规划架构、改变技术选型、扩大任务范围或开始下一阶段。
   - **P02 B/C/D 单次批量执行例外**：用户已明确放行三个子任务连续编码，中途仍必须 B/C/D 各自真实测试和独立提交，B 未通过不可执行 C、C 未通过不可执行 D；不要再逐个等待人工作出“下一步”确认，除非出现阻塞或要求变更已批准合同。
5. **用户审核实现**：Codex 报告真实修改、命令、局部测试结果与 SHA，更新 `docs/progress/Pxx.md` 为 `PENDING_REVIEW`；用户根据代码和执行证据决定 `ACCEPTED` 或 `BLOCKED`。通过后才能设计下一个阶段。

**阶段方案交付合同**：每次开展 Pxx 之前，必须提供这些内容，且不能只列模块名：

| 项目 | 必须写清楚什么 |
| --- | --- |
| 本阶段业务目标和边界 | 一个从用户输入到可验证输出的最小链路、已有依赖、明确不做的功能 |
| 现有工程基线 | 已实现文件、实际调用链、上个阶段留下的限制、依赖与接口版本 |
| DeerFlow / 官方参考 | 对应**准确路径、相关函数/关键逻辑**、我们保留与舍弃的设计 |
| **逐文件设计** | 要新增/修改的**每个文件**、类/函数名称、核心职责、输入/输出、错误处理及跨文件调用 |
| **关键实现机制** | 重要数据模型、控制流程、并发/状态/持久化/安全策略，必要时给伪代码和时序 |
| 编码子任务顺序 | A/B/C... 小任务，每个任务的修改范围、依赖、成功路径与可验证结果 |
| **局部测试与验收** | 本次新增/修改内容和直接受影响接口的测试、可复现命令、必要真实 Smoke、失败或未运行的如实记录 |
| 交付与停止条件 | 文件变更、提交分支和 SHA、进度文档更新、阻塞时如何处理、需用户批准才能继续的边界 |

**当前架构文档和 P00–P09 的逐文件规划属于“全局参考基线”，不等于未来每个阶段已完成最终审核。** 在启动 P01、P02……之前，需以最新代码重新复核对应章节、细化和必要时修正，先取得用户同意。禁止让 Codex 根据大纲自行决定各种尚未确认的实现细节，也禁止因为已有详细预案就跳过当阶段设计。

**阶段与任务的区别**：阶段设计通过后，在同一阶段内部按批准的子任务 A/B/C 顺序开发，每个子任务执行局部测试并提交；若出现合同变更、库版本冲突或新增复杂风险，回到 ChatGPT 设计和用户审核，而不是让 Codex随意改实现。**不要求每个小任务重新设计整个阶段**，但关键决策变化必须重新审核。

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
| P01 单 Agent + 极简 Web | 模型→工具→模型 + 健康/计算/问答/工具轨迹页面 | 真 Tool Call、参数/失败、当前 UI | Lead Agent、factory |
| P02 会话/Run/SSE | 在 P01 极简 Web 上增加 Thread、Run、SQLite Checkpoint、SSE | 新 Run/Thread API、当前 SSE 和状态保存 | runtime/runs、checkpointer、Gateway |
| P03 Workspace | 上传、受控读写、Artifact 下载 | 当前文件工具与路径安全 | sandbox、uploads/artifacts |
| P04 Todo / Sub-Agent | 动态 Todo、有限并发委派与汇总 | 当前 Todo/Task、超时/隔离 | todo、task_tool、executor |
| P05 MCP / Skills | 外部工具注册、SKILL.md 按需加载 | 新 MCP/Skill 和工具权限 | tools/mcp/skills |
| P06 长任务可靠性 | 上下文压缩、预算、取消、Run 孤儿检查 | 改动的 Summary/Run 路径 | middleware、RunManager |
| P07 Deep Research | 搜索、多子任务、带引用研究报告 | 新 Research 业务案例和引用 | deep-research SKILL.md |
| P08 文档 RAG | Docling、Chroma、跨文档检索、引用 | 新解析/检索与局部金标问题 | 上游工具/文件接口 |
| P09 交付 | UI 完善、Docker、固定评测与演示 | 本次交付相关测试 + 三条真实 Demo | 上游 Web/运行接口 |

阶段是开发顺序和依赖，不是承诺工期；每阶段再次拆小任务以控制 AI 上下文。任何功能如果已经稳定，不因为新阶段开始就做无关重构。

## 4. 全局接口合同与预设文件规划（当前阶段审核后才最终执行）

> 本节与后续 P00–P09 提供全项目的实现基线与逐文件参考规格，**不是对尚未开始阶段的不可更改任务指令**。开始某阶段时，必须先核对实际代码及对应上游文件，并通过“阶段设计先行”流程确认本阶段最终文件、函数及实现顺序。总体业务目标以 ARCHITECTURE.md 为准。以下 Python 代码路径默认相对 `backend/src/minideerflow/`，测试相对 `backend/tests/`，Web 文件相对 `frontend/src/`。**不要求 P00 一次建齐**；只在实现当前阶段时创建其文件。

### 4.1 开发责任边界

- **ChatGPT / 本方案负责**：在**每个阶段开始前**重新核对已实现代码、上游源码与依赖；完成该阶段的产品/技术取舍、模块职责、逐文件函数和接口结构、算法/流程、异常语义、子任务拆分、验收与停止条件；先给用户审核，批准后才形成 Codex 任务书。
- **Codex 负责**：检查实际版本 API、按指定文件编码、补本次局部测试、调试执行、记录真实结果与 commit；不得“根据自己的判断”引入新的 Agent 框架、数据库、缓存、微服务或重构整仓库。
- **允许 Codex 决定的细节**：变量名、局部函数拆分、日志措辞、合适的 Pydantic 类型标注、当前官方 API 的小差异、适量内部异常类；不能改变外部合同、业务边界、状态语义或依赖方向。
- **发生冲突时**：如果锁定版本中的 API 与本规格不兼容，先采取最小等价方案并记录确切差异；若需要更改协议、核心模块边界、技术选型或阶段范围，**停止该部分开发，提交证据等待审核**。禁止悄悄绕过。
- **一次性任务包**：仅在当前阶段具体方案经用户批准后，才依照批准的 A/B/C... 子任务逐项实施；Codex 每次只接受其中一个子任务，除了当前调用链必要文件，不读取整个上游或整个仓库；每次只测试当前新改内容及直接受影响接口。
- **文件可裁剪规则**：列表中的文件为内容及职责的归属指引，而不是鼓励为 10 行代码硬拆 5 个文件。如果两个文件实际只包含一行调用，可保留在现有文件并记录；但禁止合并不同状态/安全边界以省文件。

### 4.2 固定数据/接口名称

| 对象 | 必须有的字段或方法 | 约束 |
| --- | --- | --- |
| `Thread` | `id, title, created_at, updated_at` | 仅会话身份；不当成一次执行 |
| `Run` | `id, thread_id, status, started_at, finished_at, error_code` | 一次请求；服务端终态是真实来源 |
| `AgentState` | `messages`，P04 新增 `todos`，后续只存 artifact/evidence ID | 使用 LangGraph/LangChain state，不能无限堆子任务文本 |
| `TaskRecord` | `task_id, run_id, kind, status, result_ref, error` | 与父图状态独立；首次在内存执行，不宣称跨进程恢复 |
| `ToolResult` | `ok, content, error_code?, artifact_ids?, source_ids?` | 错误/副作用未知另有执行元数据；禁止工具只返回无法解析的异常文字 |
| `Artifact` | `id, thread_id, run_id?, name, path_internal, size, sha256` | 外部只能传 artifact_id 或虚拟路径 |
| `Evidence` | `id, source_type, url_or_document_id, location, excerpt` | 只有真实抓取/解析获得的才能标来源 |
| `RunEvent` | `event_id, run_id, thread_id, type, timestamp, payload, task_id?` | SSE 实时展示；服务端 Run 状态最终裁决 |
| `SkillMeta` | `name, description, path, allowed_tools?` | SKILL.md 指令不能绕过执行权限 |

统一 API 前缀 `/api`；P02 规定 `POST /api/threads`、`GET /api/threads`、`POST /api/threads/{thread_id}/runs`、`GET /api/runs/{run_id}`、`GET /api/runs/{run_id}/events`。P03 增加上传、文件列表与产物下载，P06 补完善取消。新增字段只能在真实阶段实现，不得在 P00 把所有领域模型先空建一遍。

### 4.3 一致的工程约定

1. 后端包名永远是 `minideerflow`；包内目录按 `api/`、`core/`、`agents/`、`tools/`、`runtime/`、`workspace/`、`research/`、`knowledge/` 逐步生成。API 不执行底层 SQL，也不直接读取用户上传路径；Harness 通过注入 Tool/Service 获取业务能力。
2. Async 优先：FastAPI 异步路由、LangChain `ainvoke/astream`、受控协程任务；阻塞型 PDF 解析/CPU 操作应放线程而不是阻塞事件循环。首版只运行一个应用 Worker。
3. ModelProvider 统一首选 `langchain-openai` 中 `ChatOpenAI`，通过 `MODEL_NAME`、`MODEL_API_KEY`、`MODEL_BASE_URL` 配置，当前只保证**一个经 P01 实测支持工具调用的提供方**；其它“OpenAI 兼容”服务不自动宣称都支持 Tool Calling。
4. 时间均用 UTC ISO-8601，ID 用 UUID 字符串。SQLite 业务库 `data/runtime.sqlite3`，Checkpoint 可使用单独 `data/checkpoints.sqlite3`；目录属于 Git 忽略内容，路径通过配置统一传入。**所有状态迁移由 Runtime 服务写入，不由前端或模型文本推测。**
5. 局部测试文件名 `test_<module>.py` 对应被修改模块；跨接口改动才补直接消费者测试。Mock 与真实云端 Smoke 分开，不因一个阶段完成自动跑全套 E2E。
6. 参考上游一律基于 `https://github.com/bytedance/deer-flow/blob/v2.0.0/` 的具体源码路径；**参考调用链与不变量，不复制整仓，也不把上游源码全文输入 Codex**。

## 5. 分阶段逐文件参考规格（启动阶段时先复核、确认、再交 Codex）


### P00 — 工程初始化（2026-11-05 当前阶段正式编码方案）

**阶段状态：P00 代码已完成并进入 main；以下保留当时已批准的实施规格供历史复核。**  
**阶段范围**：仅从仓库文档创建可安装的 Python 3.12 后端包，启动 FastAPI `GET /health`，配置本地环境、依赖锁、局部测试、Git 安全及 PyCharm 调试。**不调用 LLM，不安装 LangGraph，不做数据库/前端/MCP/Agent**。  
**重要约束**：本节是经当前仓库实态复核的 P00 最终实施规格；后续阶段的逐文件规划仍须届时重新设计审核。Codex 按本节落地，不重新进行技术选型。

#### P00-A. 环境、仓库与分支

远程仓库：https://github.com/Felix0410/Agent 。核对时，main 只有 README.md、docs/ARCHITECTURE.md、docs/DEVELOPMENT.md、docs/progress/P00.md～P09.md，尚无 backend/。后续 Codex 应在本地再次确认现状；出现差异不能覆盖文件。

1. 如用户本地尚无仓库，在 PyCharm 欢迎页使用 Clone Repository，URL 为 `https://github.com/Felix0410/Agent.git`，建议保存到 `~/Projects/Agent`；打开整个仓库为一个 PyCharm 项目，不要再创建嵌套项目。若本地已经克隆则直接打开现有仓库。
2. 在 PyCharm Terminal 执行 `git remote -v`、`git status --short --branch`、`git branch -a`。发现未提交修改、未知分支或已有 backend 目录，先报告；**不得 reset、clean、force push、覆盖或删除本地用户工作**。
3. 在工作区干净且 main 为基础的情况下 `git fetch origin` → `git switch main` → `git pull --ff-only origin main` → `git switch -c feat/p00-bootstrap`。如果该分支已存在，检查分支代码和分叉情况后复用，绝不强制重建。
4. 检查 `git --version`、`uv --version`、`uv python list`。uv 未安装可使用 Mac Homebrew 安装；Python 3.12 不存在则用 `uv python install 3.12`。不改系统 Python，不用全局 pip。
5. 后续所有 uv/python/pytest/ruff/uvicorn 命令以 `backend/` 为工作目录；Git 则在仓库根目录执行。

**完成条件**：正确分支和版本可用；如有缺失工具或未保存变更，报出阻碍，不猜测其状态。

#### P00-B. 固定文件清单（一次只实现这里列出的文件）

~~~text
Agent/
├── README.md                             # 维护已验证的本地命令与文档导航
├── .gitignore                            # 忽略本地配置/缓存/数据
├── .env.example                          # 无密钥的环境变量模板
├── docs/
│   ├── ARCHITECTURE.md                   # 不改业务目标
│   ├── DEVELOPMENT.md                    # 当前批准的实现规格，不由 Codex改设计
│   └── progress/P00.md                   # 只写 P00 真实开发记录
└── backend/
    ├── .python-version                   # 3.12
    ├── pyproject.toml                    # 可安装的 src 包、依赖与工具配置
    ├── uv.lock                           # uv 真实生成的版本锁
    ├── src/minideerflow/
    │   ├── __init__.py
    │   ├── config.py
    │   └── main.py
    └── tests/
        ├── test_health.py
        └── test_config.py
~~~

`backend/.venv/` 仅本地生成，不提交 Git。P00 不建空的 agents、tools、runtime、knowledge、workspace、frontend、Docker 等未来模块。**新文件尽量少、职责明确，不用过度封装。**

#### P00-C. 逐文件代码规范与参考实现

以下核心代码是**确定的业务合同和实现方式**；Codex 应将其转为可运行文件并处理必要导入/格式，不另选架构。

**1）`backend/pyproject.toml`：项目元数据、依赖、构建规则、测试和 lint**

使用单一可安装 Python 包 `minideerflow`，项目分发名 `mini-deerflow`，选择 `hatchling` 作为构建后端并显式指定 src 路径，避免只因当前工作目录偶然正确而导入成功。最小内容：

~~~toml
[project]
name = "mini-deerflow"
version = "0.1.0"
description = "Lightweight general-purpose multi-agent task execution system"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic-settings",
]

[dependency-groups]
dev = [
    "pytest",
    "httpx",
    "ruff",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/minideerflow"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
~~~

`uv.lock` 必须由 uv 真实安装/解析生成；第三方版本由当日求解成功的 lock 决定，**不要手工填未验证的版本号、不要单纯依赖环境已安装的包**。不要加 ORM、LangChain、LangGraph、异步数据库、Redis、Chroma、Docling、前端依赖。

`backend/.python-version` 只写 `3.12`，不强制修改系统级解释器。

**2）`backend/src/minideerflow/config.py`：精简、可校验的环境配置**

实现 `Settings(pydantic_settings.BaseSettings)`，仅下列字段：
- `app_env: Literal["development","test","production"] = "development"`
- `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"] = "INFO"`

通过 `SettingsConfigDict(extra="ignore")` 读取进程环境变量（Pydantic Settings 会对这两个字段匹配 APP_ENV、LOG_LEVEL）。`get_settings() -> Settings` 用 `functools.lru_cache(maxsize=1)` 延迟读取。测试用 `get_settings.cache_clear()` 消除环境缓存影响。非法 LOG_LEVEL 等产生明确 `ValidationError`，不吞异常、不打印环境或密钥。

**P00 明确不自动读取 .env 文件**；`.env.example` 只是模板，实际设置由 PyCharm Run Configuration 的 Environment Variables 或终端 `export APP_ENV=...` 完成。P01 才讨论模型 Key 加载。未设置变量时使用安全默认值。避免根据 Python 文件所在位置推导多级 .env 路径。

**3）`backend/src/minideerflow/main.py`：最小应用入口**

按下面的契约实现，不另建 Web 框架：
~~~python
import logging

from fastapi import FastAPI

from minideerflow.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.getLogger("minideerflow").setLevel(settings.log_level)
    app = FastAPI(title="Mini DeerFlow", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
~~~

P00 不创建依赖注入容器和启动钩子，不连接模型/数据库，`GET /health` 只代表进程存活，不代表其它服务 ready。若未来使用别的入口模式，必须有直接理由并不破坏 `minideerflow.main:app` 导入路径。

**4）`backend/src/minideerflow/__init__.py`**：空文件即可，导入无副作用。

**5）`backend/tests/test_health.py`：只验证新的 HTTP 接口**

~~~python
from fastapi.testclient import TestClient

from minideerflow.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
~~~

不连接真实网络，不测 Agent，不因为测健康检查顺便引入大量测试 Fixture。

**6）`backend/tests/test_config.py`：只验证当前真正实现的配置**

测试场景：
- 在清除 `APP_ENV`、`LOG_LEVEL` 且清空 `get_settings` 缓存后，默认值是 development/INFO；
- 设置 `APP_ENV=test`、`LOG_LEVEL=DEBUG` 后，新读取值正确；
- `LOG_LEVEL=INVALID` 能产生 Pydantic 的验证错误。
使用 pytest `monkeypatch`，每个测试前后通过 Fixture 或显式调用 `get_settings.cache_clear()` 隔离缓存。不能依赖用户真实的本地环境变量。

**7）仓库根目录 `.env.example`**：仅写 `APP_ENV=development`、`LOG_LEVEL=INFO`，注释说明 P00 需将值导入进程环境才能生效。不写真实模型提供商密钥、不写未来没实现的配置。

**8）仓库根目录 `.gitignore`**：忽略 `**/.venv/`、`**/__pycache__/`、`**/.pytest_cache/`、`**/.ruff_cache/`、`*.py[cod]`、`**/.env`、`**/.env.*`、`!**/.env.example`、`/data/`、`/backend/data/`、`.idea/`、`.DS_Store`。**不能忽略 `uv.lock` 或源码、测试与规划文档。**

**9）`README.md`**：保留 Mini DeerFlow 的项目目标、架构与进度文档导航，仅新增一小节“P00 本地开发”：uv/Python 环境、从 backend 运行、PyCharm 解释器、健康检查、局部测试与当前尚未实现功能。所有命令必须真实验证后才称可运行。

**10）`docs/progress/P00.md`**：只更新真实记录、执行日志的简明事实与状态；不要复制任务书或大段源码，不要更改其它阶段进度文档。

#### P00-D. 唯一允许的执行顺序

P00 是一个小型工程任务，Codex 可以在**一次会话中**按下面四个有界步骤实现，不能顺便开始 P01。

| 子步骤 | 修改范围 | 成功信号 |
| --- | --- | --- |
| P00-A 环境/Git | 仅检查本地工具和分支 | 正确的 origin / Python 3.12 / uv / feat/p00-bootstrap |
| P00-B 包/依赖 | backend/.python-version、pyproject.toml、src 包、uv.lock | `uv sync --group dev` 与包导入成功 |
| P00-C 运行/局部测试 | config/main、tests、.env.example/.gitignore | TestClient 测试、Ruff、真实 curl 200 |
| P00-D 文档/提交 | README、progress/P00.md、本次分支 | 内容与执行结果一致；给出真实 Commit SHA |

如在 B 阶段发现 uv/环境错误，仅修复当前环境或报告 BLOCKED；不得重建整个项目、换用 poetry/pipenv 或擅自扩大技术栈。必要的小版本兼容修正允许处理并记录原因。

#### P00-E. 精确验收命令与测试边界

这些命令均在 `backend/` 目录执行；uv 首次解析生成 lock 后，用 `--locked` 验证锁一致：

~~~bash
uv sync --group dev
uv sync --locked --group dev
uv run python -c "import minideerflow; from minideerflow.main import app; print(app.title)"
uv run pytest -q tests/test_health.py tests/test_config.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run uvicorn minideerflow.main:app --host 127.0.0.1 --port 8000
~~~

Uvicorn 启动后**在另一个终端**执行：
~~~bash
curl -i http://127.0.0.1:8000/health
~~~

预期 HTTP 200、JSON `{"status":"ok"}`。运行 Uvicorn 时不要求 `--reload`，PyCharm 断点调试首选不带 reload 的方式，避免多进程调试干扰。

Git 检查在仓库根目录执行：`git status --short`、`git check-ignore backend/.venv/some-file backend/.env backend/data/some-file` 等核对忽略；确认 `backend/uv.lock` 仍可被 Git 跟踪（比如 `git check-ignore -v backend/uv.lock` 不应匹配）。

**只测本阶段实际新增/修改的 health/config/包导入/项目管理**；全量其他阶段测试、真实 LLM、网络检索、Docker、多智能体 E2E 一律不跑。上述命令的成功与失败需要分开记录。若 P00 的代码未生成或本机无法运行，不可写“验证通过”。

#### P00-F. PyCharm 使用和安全规则

- 在 PyCharm 打开整个 Agent Git 仓库，Python Interpreter 指向 `<仓库>/backend/.venv/bin/python`。
- Run/Debug：Module `uvicorn`；Parameters `minideerflow.main:app --host 127.0.0.1 --port 8000`；Working Directory `<仓库>/backend`；正常运行和断点调试均应使用上述解释器。
- 如 Codex 无法直接操作图形界面，**只提供明确配置步骤，PyCharm 断点验证标为“待用户实测”**；不声称已经验证。
- 服务只监听 127.0.0.1；P00 不提供公网部署，不添加无认证的管理接口。
- 不执行 `git reset --hard`、`git clean -fd`、`git push --force`，不提交 .env、.venv、token、用户资料；不修改或删除已有用户成果。

#### P00-G. 提交、进度和退出规则

1. 仓库根目录仅使用 `feat/p00-bootstrap` 开发分支提交。先检查 `git diff` 与 `git status`，确保只包含 P00 文件变更。
2. 允许的提交信息示例：`chore(p00): bootstrap FastAPI backend with uv`。
3. 更新 `docs/progress/P00.md`：`IN_PROGRESS` 表示实际开始编码，代码实现/必要验证结束设置 `PENDING_REVIEW`；任务失败或依赖无法配置就设置 `BLOCKED` 并写原因。不得由 Codex 设为 `ACCEPTED`。
4. 输出 **真实文件清单、技术细节、运行命令、测试数/结果、未测项、问题和完整 Git SHA**；不能把未运行项描述为成功。GitHub 凭据可用时将开发分支正常推送远端，否则说明阻碍，不强制登录或提交到 main。
5. 提交后停止。**不自动合并 main、不进入 P01、不实现模型、Tool、LangGraph、SQLite、SSE 或前端。**

**P00 验收通过的判定**：用户能在干净 Python 3.12 + uv 环境安装后端并启动真实 `GET /health`，局部测试与安全检查有证据，PyCharm 能找到包的解释器；实现差异与提交可审核。**编译/测试成功不代表用户已审核，必须停在 PENDING_REVIEW。**

#### P00-H. 给 Codex 的单轮启动语句

> 从当前已克隆的 GitHub 仓库开始，只实施 `docs/DEVELOPMENT.md` 的 **P00-A 至 P00-G**。当前阶段方案已批准。请勿重新设计架构。首先检查 Git 和现有文件，若尚未克隆则告诉我如何克隆（当前没有本地仓库时不要凭空声称已操作）。在 `feat/p00-bootstrap` 分支按规定文件创建 Python 3.12 + uv 的可安装 `minideerflow` 包、FastAPI `/health`、简明 Settings、局部 pytest 与 Ruff、.env.example、.gitignore。仅运行 P00 本次新增内容的检查，更新 README 和 docs/progress/P00.md，提交并尽可能推送开发分支。完成后提供真实命令/结果/完整 Commit SHA 并停止；不要合并 main 或进入 P01。


### P01 — 单 Agent + 极简 Web 验证台（2026-11-05 实施合同）

**阶段状态：PLAN_READY（方案已按用户“继续完成 P01、最小 Demo 后才手测、每次同步前端”的新要求细化；尚未编码）。** 这是 P01 的正式执行规格，优先于早期 CLI-only 大纲。P00 后端代码已在 main；P01 不需重新初始化。

#### P01-1. 目标、范围与流程

**可运行 Demo 主线**：本地 Vite 页面展示服务健康状态；输入算式，点击后看到安全计算结果/错误；输入“请计算 (12+8)*3”，后端使用已配置的真实 Tool Calling 模型调用 `calculate`，LangChain Agent 将 ToolMessage 回馈模型，再由模型生成最后回答；页面分别展示**最终答复**和**来自实际消息的工具名称、参数、结果、是否成功**。普通问答允许不触发工具，绝不虚构调用轨迹。CLI 可作为同一 Agent 服务的轻量入口。

此阶段的结果是一次独立、同步等待的 HTTP 请求，不创造 Thread/Run ID，不持久化消息或事件，不使用 Checkpointer，不做 SSE、多 Agent、Todo、MCP、Skills、文件工作区、上传、RAG、后台任务或鉴权平台。这些归 P02 及以后。**仅监听本机回环接口**。健康检查不依赖密钥，没配置模型时页面健康/计算器依旧正常，Agent 入口清晰报 MODEL_NOT_CONFIGURED。P01 不是最终多智能体系统。

#### P01-2. 工程基线与官方参考

已核实 main 存在：`backend/src/minideerflow/main.py`（`create_app`+`GET /health`）、`config.py`（`Settings`+`get_settings`）、`backend/pyproject.toml`、`backend/uv.lock`、`tests/test_health.py`、`tests/test_config.py`。P00 锁定 Python 3.12；当前未安装 langchain/langgraph/langchain-openai，也没有 API、Agent、Tool、CLI、frontend 目录。

- DeerFlow v2.0.0 固定源码 `backend/packages/harness/deerflow/agents/factory.py`：观察 `create_deerflow_agent` 如何以 `model/tools/system_prompt/checkpointer` 参数调用 `langchain.agents.create_agent`；本阶段**只保留这个装配思路**，不复制 feature/middleware 堆栈。
- 同标签 `backend/packages/harness/deerflow/agents/lead_agent/agent.py`：观察 Lead Agent 组织与运行时依赖注入；不引入 DeerFlow 配置、状态、Todo、Subagent、Gateway 或 tracing。
- LangChain 官方 `https://docs.langchain.com/oss/python/langchain/agents` 与 `https://docs.langchain.com/oss/python/integrations/chat/openai`：确认已锁定版本的 `create_agent` / `ChatOpenAI` / `@tool` / `ainvoke` / `AIMessage.tool_calls` / `ToolMessage.tool_call_id` 实际签名。细小版本参数差异允许等价调整并记入进度；不得借此更换架构。

#### P01-3. 接口合同（先确定，Codex 只实现）

1. `GET /health`：保留现有 `{"status":"ok"}`，不能因为 Agent 配置缺失而失败。
2. `POST /api/demo/calculate`：body `{"expression":"(12+8)*3"}`；成功 HTTP 200 `{"result":"60"}`；无效表达式 HTTP 422 `{"detail":{"code":"CALC_INVALID_EXPRESSION|CALC_DIV_ZERO|CALC_TOO_LONG|CALC_OUT_OF_RANGE","message":"..."}}`。不走模型。
3. `POST /api/demo/agent`：body `{"message":"请计算 (12+8)*3"}`；成功 HTTP 200 `{"answer":"...","tool_calls":[{"name":"calculate","args":{"expression":"..."},"result":"60","ok":true}]}`。`tool_calls` 数组按实际执行顺序，普通问答为空数组，不可模拟或编造。模型未配置 HTTP 503 `MODEL_NOT_CONFIGURED`；模型超时 HTTP 504 `MODEL_TIMEOUT`；上游鉴权/网络/协议或运行失败 HTTP 502 `MODEL_UPSTREAM_ERROR` 或 `AGENT_EXECUTION_FAILED`，只返回脱敏短消息，不向前端透传 key、授权请求头、原始异常字符串或内部堆栈。请求正文空白/超过 2000 字符一律 HTTP 422（Pydantic 允许附带自己的 validation detail）。
4. Tool 消息错误必须可辨别（如 `ERROR[CALC_DIV_ZERO]: division by zero`）；HTTP 计算接口使用同一个纯函数并将错误翻译成 422；Agent 调用工具若报可恢复计算错误，应返回错误 ToolMessage 让模型解释，不视为成功结果；链路不得因为工具无效输入而崩溃。
5. 除 `/health` 外，这两个 `/api/demo/*` 是 P01 **临时调试入口**；P02 在复用底层 AgentService 的基础上加正式 `/api/threads`/`/api/runs`，不要扩展临时接口为持久运行协议。

#### P01-4. 逐文件实施规格

| 文件（相对仓库根） | 必须承担的实现与接口 |
| --- | --- |
| `backend/pyproject.toml`, `backend/uv.lock` | 增加 `langchain`、`langchain-openai`、`langgraph` 依赖，`uv lock` 真实锁定后 `uv sync --locked --group dev` 验证；不顺手升级无关 P00 依赖；遇到兼容问题记录具体版本与调整。 |
| `backend/src/minideerflow/config.py` | **继续使用 P00 此文件，不另建 core/config.py**。扩展 `model_name: str|None`、`model_api_key: SecretStr|None`、`model_base_url: str|None`；可加固定默认 model_timeout_seconds=45。Settings 构建时**不强制** model key；Agent 工厂调用时才校验非空 model/key。任何异常/log/JSON 不得输出完整 key。 |
| `backend/src/minideerflow/core/model.py` | `build_chat_model(settings: Settings) -> BaseChatModel`，唯一模型构造点，实例化 `langchain_openai.ChatOpenAI`；按实际锁定 API 传 `model`, `api_key`, 可选 `base_url`, 超时与低重试次数；无 key/model 抛出 `ModelNotConfigured`（独立可捕获的内部错误）。无启动阶段网络连接。 |
| `backend/src/minideerflow/tools/calculator.py` | `safe_calculate(expression: str) -> str` 是无副作用纯函数；另提供 LangChain `@tool` 修饰的 `calculate(expression: str) -> str`。使用 `ast.parse(..., mode="eval")` + **递归 AST 白名单**：数字常量（排除 bool）、`+ - * /`、一元正负、括号；拒绝 Name、Call、Pow、FloorDiv、Mod、容器、比较等；禁用 eval/exec。限制原表达式 128 字符，数值与中间结果绝对值 ≤ 10^12，拒绝非有限数和零除；返回简洁数字字符串。错误使用 `CalculatorError(code,message)`；`calculate` 工具将错误转为 `ERROR[code]: message`，而非 Python Traceback；校验最大表达式长度在 ast.parse 前。 |
| `backend/src/minideerflow/agents/lead.py` | `build_lead_agent(model, tools)` 仅调用 `langchain.agents.create_agent(model=...,tools=...,system_prompt=...)`。短提示词：直接答复普通问题；需要精确运算时调用 calculate；不能声称未发生的工具调用。不用自写 StateGraph/while 循环；不使用 checkpoint/middleware/subagents。 |
| `backend/src/minideerflow/agents/service.py` | `async run_agent_once(message: str, *, model: BaseChatModel|None=None) -> AgentResponse`（注入 FakeChatModel 的测试口）。空/过长输入拒绝；若未注入 model，再用 Settings+build_chat_model；通过 `agent.ainvoke({"messages":[{"role":"user","content":message}]}, config={"recursion_limit":12})` 触发一轮请求。解析实际 AIMessage 的 tool_calls 与匹配 tool_call_id 的 ToolMessage；有多次调用则按完成的 ToolMessage 顺序输出轨迹；含 `ERROR[...]` 的结果 ok=false；只有最后一个没有待处理 Tool Call 的 AIMessage 可作答；无法得到最终答复应返回明确执行错误，不能编造。限制请求范围、仅发送当前用户消息，**不储存聊天记录**。 |
| `backend/src/minideerflow/api/demo.py` | Pydantic request/response schema、`APIRouter(prefix="/api/demo")`、calculate/agent 端点和受控错误映射；仅薄 Router，不直接实例化 OpenAI 模型或重写 Agent 逻辑；测试中可 monkeypatch `run_agent_once`。 |
| `backend/src/minideerflow/main.py` | 在 `create_app()` 内包含 demo router，保留原有 health 原语义；缺模型配置时应用仍成功启动。 |
| `backend/src/minideerflow/cli.py` | `uv run python -m minideerflow.cli "请计算 (12+8)*3"`：只调用与 HTTP 同一 AgentService，打印 answer 和可读工具轨迹，失败 stderr + 非零码，不打印 key；不需要多轮终端交互。 |
| `backend/tests/test_calculator.py` | 安全计算：括号/负数/小数、优先级、零除、恶意 Call/Name/Pow、超长、溢出、bool/非数、输出稳定。 |
| `backend/tests/test_lead.py` | **Mock** 模型脚本驱动：无工具回复，AIMessage(tool_calls)→ToolMessage→模型最终回复；断言实际 tool_call_id 匹配、轨迹真实、计算失败得到 ToolMessage 错误而非虚构成功；Mock 需要按已锁定版本实现 bind_tools，不调用外网。 |
| `backend/tests/test_demo_api.py`、`backend/tests/test_config.py` | 两临时 API 的 200/422/503/脱敏错误及请求校验；配置无 key 时 `/health` 仍可启动；使用被测对象的依赖注入/monkeypatch，禁止真实消费额度。 |
| `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html` | React + TypeScript + Vite 最小应用；npm lock 真实生成；本地 Vite dev server 默认 127.0.0.1:5173；把 `/health` 与 `/api` 代理到 127.0.0.1:8000，不需要 CORS、不配置任何模型 key 到 Vite。最小 npm scripts `dev`,`build`。 |
| `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/styles.css` | 一个轻量测试页，不搭复杂路由/UI 库：健康检查（真实 `/health`）、计算器（输入+显示结果/错误）、Agent 问答（输入、等待态、最终回答）、**真实工具调用轨迹**（名称、输入、结果/失败）；每块独立按钮及失败提示。提供“当前已实现：P00 健康/P01 计算/P01 Agent”“后续：会话、SSE、Todo、文件”等静态能力导航，未实现区域禁用/标注，不显示伪结果；禁止 dangerouslySetInnerHTML。 |
| `.env.example`, `README.md`, `.gitignore` | 环境模板新增 MODEL_NAME、MODEL_API_KEY（留空占位）、MODEL_BASE_URL；P00 不自动加载 .env，文档明确使用 shell export/PyCharm env；README 只记录**真实已验证**的两终端启动、配置、API/CLI/前端 build、局部测试，说明真实模型需具备 Tool Calling；忽略 `frontend/node_modules`, `frontend/dist`，不要忽略 lockfile。 |
| `docs/progress/P01.md` | 每子任务记录真实文件、局部测试命令与结果、SHA、模型 Smoke 证据（不得泄 key）、功能与页面对应关系；未实测项目如实写未验证，完工转 PENDING_REVIEW，用户审核后 ACCEPTED。 |

`__init__.py` 只在新包需要时建立；如实际需单独 `schemas.py`/异常类，优先留在上述已有文件，若跨两处共享且不可避免可新增一个小文件，并在进度解释原因。不要生成空目录占位。

#### P01-5. 业务链路与一致性边界

```text
Browser -- fetch --> FastAPI /api/demo/agent --> AgentService.run_agent_once
  --> ModelFactory(ChatOpenAI) --> LangChain create_agent
  --> AIMessage.tool_calls(name=calculate,args,id)
  --> @tool calculate --> safe_calculate(AST) --> ToolMessage(tool_call_id=id)
  --> Model receives ToolMessage --> final AIMessage
  --> AgentService extracts answer + ACTUAL tool trace --> JSON --> Browser

Browser -- fetch --> /api/demo/calculate --> safe_calculate(AST) --> JSON
Browser -- fetch --> /health --> existing P00 health --> JSON
CLI ---------------------> AgentService.run_agent_once (same path as HTTP)
```

**执行边界**：客户端只传字符串，不传 Tool 名称/任意 Python 表达式/Provider Key；服务端只有 calculate 一个授权工具；单次同步 Agent 请求有模型超时与递归步数上限，客户端重复点击时用 `disabled/loading` 防止叠加请求（不承诺全局并发限额）。P01 Tool Trace 仅从已经发生的框架消息生成，后续 P02 再统一 SSE/RunEvent。P01 只对可信本机开放，绝不部署公网无鉴权 API。面向上游的错误不写出私人数据；日志与 HTTP 返回不包含 MODEL_API_KEY。

**关于工具结果**：P01 面向模型仅返回字符串/错误字符串，P03 起引入全局 `ToolResult` 协议；不可在 P01 假装完整 Tool Policy、重试或 side-effect-unknown 已实现。

#### P01-6. 编码任务、前端同步与停止条件

**P01-A 计算器 + 初始 Web 壳**：新增计算纯函数和 LangChain 工具、独立 HTTP calculate、主程序路由、Pytest；前端搭建 React/Vite，放 `/health` + calculate 两块可操作区域，Agent 标记未实现；更新相应环境/忽略配置。先以不配置模型的环境完成实际健康+计算 API 局部 Smoke 和 npm build。A 未通过时不进行 B。

**P01-B 单 Agent + Web Agent 区块**：加入模型配置/Factory、LeadAgent、AgentService、CLI 和 Agent HTTP；前端新增问答及真实 Tool Trace。Mock 无工具/工具循环/失败/参数边界；更新直接受影响的 config、health 与 API 测试，npm build；无 key 场景返回 503。不得把 Mock 当真实模型调用。

**P01-C 真模型 Smoke + Demo 交付**：在用户本地已有可用的 MODEL_* 环境且模型经确认为支持 Tool Calling 时，用正常问答和一次必须真正计算的问题调用实际 HTTP/CLI；保存非敏感证据：请求、状态码、实际 tool call 名称、参数、result、最终回答；**不保存密钥、原始认证头、模型隐藏内容**。如果没有 key 或 Provider 不支持，则如实记 `REAL_MODEL_SMOKE_BLOCKED`，不得把 Demo 标记为“真实 Agent 已验证”；其余无需模型的健康/计算/静态前端可以通过。更新 README 与 P01 进度，核验 demo 页面展示的是确实已实现功能。**用户直到 P01 最小 Demo 交付后才亲自手动测试**；Codex 在开发期间仍须独立运行新增/修改功能的局部测试和必要 Smoke。

**P01 的交付结果只能表述为**：静态前端/计算器已验证；Mock Agent 测试已验证；真实 Tool Calling Smoke 已验证或明确阻塞——三者分别汇报，不合并成一句“全部通过”。出现外部接口/架构变更、真实模型不支持 Tool Calling 或关键兼容失败，记录 BLOCKED 并停止相关部分；不自主转向其它模型框架/供应商、不开 P02。

**全阶段前端规则自 P01 生效**：此后 P02–P09 每完成一个开发任务，必须在同一提交/任务里同步更新极简 Web 工作台，让本地**实际已经实现并已验证的用户可见能力**可单独操作/观测；涉及旧面板的接口修改同步调整调用及状态；仅内部基础设施变更且不存在可见操作时，在进度解释“为什么无 UI 改动”。禁止先把新后端功能做完、多个阶段后才补前端；禁止为展示效果写 mock/硬编码假数据并冒充真实能力。P02 在 P01 页面的基础上逐步增加 Thread/Run、SSE、Checkpoint，不重起另一套 UI。

**局部验证最小命令（在 backend/ 下）**：`uv sync --locked --group dev`；`uv run pytest -q tests/test_calculator.py tests/test_lead.py tests/test_demo_api.py tests/test_config.py tests/test_health.py`（只选本次确实新增/直接受影响文件，A、B 分开执行）；`uv run ruff check src tests` 与 `uv run ruff format --check src tests`（作用于本阶段实际修改文件为佳）。`frontend/` 下 `npm ci && npm run build`，本机 `uvicorn` + Vite 并用 HTTP 检查 `/health`、`/api/demo/calculate`、`/api/demo/agent` 无密钥错误响应。真实模型 Smoke 仅当可用密钥存在且不产生隐私泄漏时运行。

**Git 操作**：从更新后的 main fast-forward 拉取，检查未提交工作后建/复用 `feat/p01-single-agent-web`；Codex 依 A→B→C 顺序实施并保持每个任务的前端与后端同步、分别做小提交，最后推送该分支（失败如实报错），记录 SHA/局部测试。不要 reset/clean/force push，不覆盖用户在本地的变更。阶段结束标记 PENDING_REVIEW，等待用户基于 Demo 进行审核；未获批准不进入 P02。

### P02 — Thread / Run / SQLite Checkpoint / SSE / 极简 Web（2026-11-06 正式实施合同）

**状态：IN_PROGRESS（P02-A 已在 GitHub 开发分支实现并记录局部验证；B/C/D 已获用户授权一次性连续编码，尚未实现）。** 以 `feat/p01-single-agent-web` 的实际代码及中文注释整理为基线。原 P02 三段概述以此四任务 A/B/C/D 细化合同为准；P03–P09 规划保持不变。不得以 P01 的 `PENDING_REVIEW` 冒充验收通过；执行 P02 前先同步并核验 P01 最新代码。

#### P02-1. 用户可见结果、边界及现状

**主业务链**：在已有 React 测试台创建/选择 Thread → 提交文本获得 `run_id`（HTTP 202，不等待模型完成）→ 单进程后台 Runner 使用相同 `thread_id` 执行 P01 Agent → LangGraph SQLite Checkpointer 保存多轮 Graph 消息 → 业务 SQLite 保存 Run 输入、状态、最终回答及实际工具轨迹 → SSE 实时传 Token/工具状态/终态 → 页面可切换会话、刷新恢复已完成历史、显示服务端真实状态。

**P01 已有**：`config.py` / 根目录 `.env`、`core/model.py`（`ChatOpenAI`）、`agents/lead.py`（`create_agent`）、`agents/service.py`（`run_agent_once`、ToolMessage 校验）、`tools/calculator.py`、`api/demo.py`、`main.py`、React/Vite `frontend/src/App.tsx` 和 `api.ts`；P01 真实普通问答与计算工具在 `AgentService` 层有验证记录，最新中文注释/格式未单独运行本地测试。P01 `/health`、`/api/demo/calculate`、`/api/demo/agent`、CLI 都必须保留。

**本期只做**：Thread / Run、Graph 历史、异步任务、有限流式事件、有限重连、简易 Web 会话 UI、服务重启时保守孤儿核查。**不做**：多用户鉴权/公网暴露、Todo/Sub-Agent、MCP/Skills、Workspace、文件上传、RAG、Redis/MQ、跨进程运行、完整 Run 取消和中断点精准恢复、永久 SSE 事件归档。P01 计算器仍是唯一 Agent Tool。所有服务器默认 `127.0.0.1`、仅一个 Uvicorn Worker、无 `--reload`。

**上游已经核对**：`bytedance/deer-flow` 标签 `v2.0.0` 中：
- `backend/packages/harness/deerflow/runtime/runs/manager.py`：参考 `create_or_reject`、`set_status`、`reconcile_orphaned_inflight_runs` 的职责分离；不复制复杂调度或存储重试框架。
- `backend/packages/harness/deerflow/runtime/runs/worker.py`：参考 `run_agent` 中 Graph 流式事件和 Run 终态顺序；不复制完整 Gateway 协议。
- `backend/packages/harness/deerflow/runtime/checkpointer/async_provider.py`：参考异步上下文管理器与关闭顺序；本项目直接用官方 `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`。
- 官方参考：[LangGraph StreamMode](https://reference.langchain.com/python/langgraph/types/StreamMode)、[SQLite AsyncSqliteSaver](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver)、[LangChain create_agent](https://reference.langchain.com/python/langchain/agents/factory/create_agent)。`messages` 为模型 Token + metadata，`updates` 为节点实际更新，二者语义不相同。具体签名以本地锁定的兼容版本实测为准。

#### P02-2. 固定数据模型、SQLite 架构与并发

两份独立文件位于 `backend/data/`（Git 忽略）：`runtime.sqlite3` 保存业务记录；`checkpoints.sqlite3` 交给 LangGraph 官方 Saver。可通过 Settings 指定路径，自动创建父目录；绝不提交本地 DB。`runtime` 写入使用单一 `aiosqlite` 连接和 `asyncio.Lock` 串行化写事务；启用 `PRAGMA foreign_keys=ON`、`journal_mode=WAL`、`busy_timeout=5000`。关键「检查 + 插入/更新」在 `BEGIN IMMEDIATE` 事务内完成并正确提交/回滚；只靠 Python 内存锁不足以保护表约束。

`threads`：
| 列 | 类型 | 约束 |
|---|---|---|
| `id` | TEXT | PK、UUID 字符串 |
| `title` | TEXT | 默认「新会话」，非空，最多 100 字 |
| `needs_recovery` | INTEGER | NOT NULL DEFAULT 0，仅保守阻止不确定会话继续 |
| `created_at` / `updated_at` | TEXT | UTC ISO8601，非空 |

`runs`：
| 列 | 类型 | 约束 |
|---|---|---|
| `id` | TEXT | PK、UUID |
| `thread_id` | TEXT | NOT NULL，外键 `threads(id)` |
| `input_message` | TEXT | NOT NULL，1–2000 字 |
| `status` | TEXT | NOT NULL，`CREATED/RUNNING/SUCCEEDED/FAILED/CANCELLED` |
| `answer` | TEXT | 成功时最终有效答复，否则 NULL |
| `tool_trace_json` | TEXT | 当次真实工具结果，默认 `[]`；不放凭据/原始 Provider 报文 |
| `error_code` | TEXT | NULL 或稳定脱敏错误码 |
| `created_at` / `started_at` / `finished_at` | TEXT | UTC ISO8601，后两者可空 |

至少建 `runs(thread_id,created_at,id)` 索引与部分唯一索引：
```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_one_active_per_thread
ON runs(thread_id)
WHERE status IN ('CREATED', 'RUNNING');
```

**固定状态转换**：`CREATED -> RUNNING -> SUCCEEDED/FAILED`；排队/启动异常时允许 `CREATED -> FAILED`；`CANCELLED` 仅预留终态，不暴露用户取消接口（P06 实现）；终态不能转回 RUNNING，也不可二次终结。只有服务端成功保存终态后才能发布 `run_end`。Graph 或工具文字声称“完成”不是成功依据。`run_id` 是单次执行，不等同 `thread_id`；`tool_call_id` 归实际工具消息管理。

**保守恢复**：启动检查遗留 `CREATED/RUNNING`，更新为 `FAILED/RUN_INTERRUPTED`，标记受影响 Thread 的 `needs_recovery=1`；正常执行进入 Graph 后出错/超时且可能留下部分 Checkpoint，也标记该 Thread 需恢复。此类 Thread 的新 Run 返回 409 `THREAD_REQUIRES_RECOVERY`，不自动重放或复用有缺口的历史；前端允许查看并提示“新建会话继续”。不提供恢复标志的手动清除 API。一个正常完成的 Thread 允许继续多轮对话。P06 再设计可靠恢复。

**检查点**：`AsyncSqliteSaver.from_conn_string(path)` 使用 `async with` 在 FastAPI lifespan 中管理，注入 `build_lead_agent(model,tools,checkpointer=...)`，Graph 调用 `config={"configurable":{"thread_id":thread_id},"recursion_limit":12}`。同一 Thread 串行，新的 HumanMessage 自动参与已有 Graph 消息；不用 Run 表模拟消息记忆。Saver 的表由库按需初始化，不直接改内部 schema；按已锁定库版本确认安全反序列化配置（官方建议 `LANGGRAPH_STRICT_MSGPACK=true` 或明确 allowlist），不读取不可信外部 SQLite 文件。正式验证包括释放连接后重新打开仍能读取相同 Thread 的消息。

**最终一致性顺序**：① 事务创建 Run 并做单 Thread 互斥 → ② 后台进入 RUNNING → ③ 流式执行且 Checkpoint 由框架写入 → ④ 验证最终 AIMessage 和工具回执，事务保存 Run 成功/失败 → ⑤ 发布终态 SSE。两份 SQLite **没有跨库原子事务**；异常/崩溃时以保守 FAILED + 恢复标志处理，绝不能宣称 Exactly-Once。

**本地执行容量**：固定最多 2 个并行 Agent Run、8 个 CREATED 排队 Run。Runner 在应用生命周期中持有 2 个 worker Task，`asyncio.Queue(maxsize=8)` 缓冲队列；同 Thread 活动 Run 始终唯一。提交端在 Run 创建前的统一准入临界区检查队列容量，满时返回 429 `RUN_QUEUE_FULL` 且不得留下孤立 CREATED。后台 worker 顺序从队列领取、把 CREATED 更新 RUNNING。P02 无动态优先级、分布式队列或数据库任务调度器。

#### P02-3. API 与响应合同（Codex 不自行改名）

| 方法与路径 | 请求 | 成功响应 / 语义 |
|---|---|---|
| `POST /api/threads` | `{"title":"可选标题"}`，可为空对象 | HTTP 201，`ThreadDto`（含 `id/title/created_at/updated_at/needs_recovery`） |
| `GET /api/threads` | 无 | HTTP 200，`ThreadDto[]`；按 `updated_at DESC,id DESC` |
| `GET /api/threads/{thread_id}/runs?limit=50` | limit 默认 50、最大 100 | HTTP 200，`RunDto[]`；截取最近 N 条后按时间正序显示 |
| `POST /api/threads/{thread_id}/runs` | `{"message":"..."}` | HTTP 202，`{"run_id":"UUID","thread_id":"UUID","status":"CREATED"}`，仅代表已接收 |
| `GET /api/runs/{run_id}` | 无 | HTTP 200，`RunDto`：`id/thread_id/input_message/status/answer/tool_calls/error_code/created_at/started_at/finished_at` |
| `GET /api/runs/{run_id}/events` | 浏览器 SSE，可带 `Last-Event-ID` | HTTP 200 `text/event-stream`；Run 不存在 404、失去保留窗口 410 |

共享错误响应：`{"detail":{"code":"...","message":"脱敏短消息"}}`。404 `THREAD_NOT_FOUND/RUN_NOT_FOUND`；409 `THREAD_BUSY/THREAD_REQUIRES_RECOVERY`；422 Pydantic 输入校验（空/超 2000 字必须拒绝，命名 `INVALID_MESSAGE` 的自定义错误可由边界适配）；503 `MODEL_NOT_CONFIGURED`；429 `RUN_QUEUE_FULL`；SSE 不可回放 410 `EVENT_STREAM_EXPIRED`。运行后发生的 Timeout/Provider 错误不再改变已经返回的 HTTP 202，而是更新 `FAILED` 与 SSE 错误事件。模型缺配置属于启动 Run 的前置校验：在建 Run 前立即返回 503，不残留 CREATED。API 不暴露内部堆栈、认证头、密钥。

**历史记录**：仅成功返回的 `answer` 是确认的最终回答；失败 Run 仍保留输入、状态、错误码，页面不得拼造回答。`tool_calls` 由真实匹配的 `AIMessage.tool_calls` 与 `ToolMessage.tool_call_id` 构造，沿用 P01 的 `ToolTrace` 语义，失败工具 `ok=false`。不要把 SSE 中间 Token 保存成“已完成回答”。

#### P02-4. SSE / 事件一致性合同

统一 `RunEvent`：`event_id`、`run_id`、`thread_id`、`type`、`timestamp`、`payload`，未来子任务可选 `task_id`。`event_id` 格式 `<run_id>:<递增整数>`，同一 Run 内单调递增，发布时分配；在 SSE 中使用 `id:`、`event:`、`data:`（data 是 JSON 的完整 RunEvent）。事件类型：
- `run_start`：RUNNING 已成功入库。
- `assistant_delta`：来自 Graph `messages` 流的真实模型文本增量，带 `message_id` 与 `text`；注意工具调用前的消息不一定是最终答复。
- `tool_start`：实际 Graph `updates` 中 AIMessage 的有效 `tool_calls`，带 `tool_call_id/name/args`。
- `tool_end`：对应真实 ToolMessage，按调用 ID 配对，携带 `name/result/ok`；未匹配的回执应视为执行错误。
- `assistant_final`：Graph 结束后通过已提交的最终消息验证提取的完整回答，前端用它**覆盖**临时 Token。
- `error`：仅错误码和安全说明，不透传 Provider 异常。
- `run_end`：终态已持久化，payload 包含状态；前端随后 `GET /api/runs/{id}` 复核。
- `stream_gap`：订阅过慢/窗口缺口的提示，前端停止拼接并改查 Run；这是一次性控制通知，不作为永久可回放业务事件。

`graph.astream(...,stream_mode=["messages","updates"])`：`messages` 仅用于模型增量，过滤非模型节点和工具调用 chunk，不把 ToolMessage 当 Token；`updates` 用于工具请求、回执及最终节点更新。流式过程中积累**本轮新增**的工具消息，不把以前 Thread 历史重复作为本轮工具记录；图正常结束后再从最后有效 AIMessage / `aget_state(config)` 复核最终答案与待处理调用 ID。必要时以当前 Run 的已观测 AI/Tool 消息集合明确隔离历史，不能直接对完整历史重新算所有 ToolTrace。去重依靠真实消息 ID/工具调用 ID；不能通过文本猜测工具名称或成功状态。

**EventBus**：按 Run 持有最多 512 条事件的有界 `deque`，最多每个订阅者 64 条待消费通知；事件先进入缓冲再通知订阅者。Run 创建成功后立即创建对应 EventBus 记录，确保 POST Run 返回后才订阅也可以读取 `run_start`。首订阅无 cursor 时回放当前保留缓冲；浏览器重连传 `Last-Event-ID` 时只重放更大的序号（同一个 Run ID），不跨 Run 复用 cursor；SSE 断开不取消后台 Run。慢订阅者溢出或 cursor 早于最早保留序号时发送一次 `stream_gap` 并结束流，绝不阻塞 Runner、也不默默假装连续；缺口控制消息不参与正常递增业务事件回放。终态后事件内存保留 10 分钟，之后清理；Run 已存在但无可回放事件时返回 410，让前端查询 `GET Run`。EventBus 是内存窗口，**不代表持久化历史**。

**终态事件顺序**：`assistant_final` 只有在结果确实有效后发布；`run_end` 永远在业务库终态提交之后发布。服务端持久化失败时不得发布 SUCCEEDED；至少记录安全日志供排查。HTTP SSE 设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`，客户端断线可重新订阅，历史展示必须以数据库为准。

#### P02-5. 逐文件设计与固定职责

路径除特别注明外均相对 `backend/src/minideerflow/`；只创建当前任务真实使用的包/文件，避免先建空目录。

| 文件 | 类/函数/接口（必须落地） | 边界与错误处理 |
|---|---|---|
| `backend/pyproject.toml` + `backend/uv.lock` | 新增 `aiosqlite`、`langgraph-checkpoint-sqlite` 并真实锁版 | `uv sync --locked --group dev`；记录精确版本；保留 P01 既有依赖与模型工厂 |
| `config.py`（改） | `runtime_db_path`、`checkpoint_db_path`、`run_max_concurrency=2`、`run_queue_size=8` | 默认绝对路径基于 backend 项目，不依赖 cwd；保留 `.env` 与 `SecretStr`、原模型配置 |
| `runtime/models.py` | `RunStatus(str,Enum)`、`ThreadDto`、`RunDto`、`RunEvent`、`RunAccepted`；`utc_now_iso()` | 序列化字段稳定、UTC 时间、Run 的 `tool_calls` 为 P01 ToolTrace |
| `runtime/db.py` | `RuntimeDatabase.open(path)`、`init_schema()`、`transaction(...)`、`close()` | 显式事务/锁、连接生命周期、WAL/外键/忙等待；不要让 API 执行 SQL |
| `runtime/repository.py` | `create_thread(title)`、`list_threads()`、`get_thread(id)`、`list_runs(thread_id,limit)`、`create_run(thread_id,message)`、`get_run(id)`、`transition_run(id,expected,target)`、`complete_run(id,...)`、`reconcile_orphans()` | 原子状态更改、唯一活动 Run 索引、`THREAD_BUSY` /恢复标志、终态不可逆；线程更新时间 |
| `runtime/checkpoints.py` | `open_checkpointer(path)` 异步上下文管理器，产出 `AsyncSqliteSaver`；`thread_config(thread_id)` | 连接关闭由 lifespan 负责；框架 saver 原生存消息，不手写 Checkpoint SQL |
| `agents/lead.py`（改） | `build_lead_agent(model,tools,checkpointer=None)` | 保留 P01 Prompt 与工具表，给 `create_agent` 透传 optional saver；P01 无 Checkpointer 路径仍正常 |
| `agents/service.py`（少量改） | 保留 `run_agent_once`；抽取纯函数 `extract_final_answer(messages)`、`extract_run_tool_traces(messages)`（若共用可降低重复） | 同样的 tool_call_id 校验、安全失败语义；不可因为新 Run 引入第二套 Agent 逻辑 |
| `runtime/runner.py` | `RunService.start_run(thread_id,message)`、`_worker_loop()`、`_execute_run(run)`、`shutdown()` | 有界 Queue + 2 workers、Task 强引用、配置预检、事务状态变化、异常清理/孤儿修复；202 不等待模型 |
| `runtime/streaming.py` | `stream_agent(agent,thread_id,input,event_sink)` | 仅转换 Graph chunks，过滤模型 delta、建立当前 Run tool_call_id 映射、返回实际终态答案/轨迹；不写 SQL |
| `runtime/events.py` | `EventBus.ensure_run(id,thread_id)`、`publish(...)`、`subscribe(id,last_event_id)`、`close_run(id)`、`prune()` | 顺序事件、有界 deque、64 容量订阅、10 分钟保留、断线不取消 Run、缺口显式提示 |
| `api/threads.py` | 201 创建/200 列表/200 历史 runs，使用 `request.app.state` 的 Repository | Pydantic 校验、统一 404/409；不直接调用模型或 SQLite SQL |
| `api/runs.py` | 202 新 Run、200 查 Run、SSE 订阅 Run | 读取 `Last-Event-ID`、处理 404/410、发送合法 SSE 帧；仅调 Runner/EventBus |
| `main.py`（改） | `asynccontextmanager lifespan` 初始化 DB → Saver → Repository reconciliation → EventBus/Runner；退出按 Runner → EventBus → Saver → DB 关闭 | 保留现有 app/health/demo 路由及 PyCharm `__main__` 入口，启动无模型密钥仍可健康检查 |
| `frontend/src/api/runtime.ts`（新增） | `createThread`、`listThreads`、`listRuns`、`startRun`、`getRun`、`subscribeRunEvents`；统一 TS DTO | 保留 `src/api.ts` 的 P01 计算/健康接口，不把 Key 放进浏览器 |
| `frontend/src/components/ThreadList.tsx`（新增） | Thread 新建/列表/切换，展示 `needs_recovery` | 显示真实后端数据，不能占位假会话 |
| `frontend/src/components/ChatPanel.tsx`（新增） | 当前 Thread 运行列表、输入、处理中内容、历史恢复 | 初期按真实 RunDto 恢复；请求中的状态可轮询，SSE 后覆盖为最终答案 |
| `frontend/src/components/RunStatus.tsx`（新增） | 状态、真实 Tool Trace、错误/恢复提示 | 只凭 GET Run 终态确认成功，不能从助手回答词句推断成功 |
| `frontend/src/App.tsx`、`styles.css`（改） | 组合两栏 UI、保留 P01 健康/计算器/一次性 Agent 调试区，增加 Thread 工作台 | 简洁 CSS，不引入 Redux/Next.js；响应式最小可用，禁用假完成信息 |
| `.env.example` / `.gitignore` / `README.md`（按需改） | 数据库配置、运行命令、忽略 `backend/data`、能力导航 | 不覆盖现有 `.env`，不提交真实数据库或密钥 |
| `docs/progress/P02.md` | A/B/C/D 每次真实变更、命令、局部测试、Git SHA、前端对应能力 | 未运行不得写通过；只有 Demo 验收后 `ACCEPTED` |

**测试文件**：`backend/tests/test_repository.py`、`test_checkpoint.py`、`test_runner.py`、`test_events.py`、`test_runs_api.py`；直接受影响时更新 `test_lead.py`、`test_demo_api.py`、`test_config.py`、`test_health.py`。测试使用临时 SQLite 文件、假模型，不请求真实 Provider、不读取用户本地 `.env`、不创建用户真实数据库。

#### P02-6. 子任务 A/B/C/D（B/C/D 已授权合并连续执行）

> **执行补充**：P02-A 已实现，详见 `docs/progress/P02.md`；用户已明确允许剩余 B/C/D 在一个 Codex 任务中顺序实现。**详细执行合同已写入 [docs/tasks/P02-BD.md](tasks/P02-BD.md)**，以此规定 B/C/D 的直接执行顺序、文件/函数、前端同步、各自测试与提交、失败停止条件。本章原 A/B/C/D 功能范围保留作为验收基线，若历史叙述要求逐个等待人工审批，本次以用户的新授权和任务文件为准。

**P02-A — SQLite + Checkpointer + Thread 列表（已实施，待最终 Demo 总体验收）**
1. 前置核验最新 P01 分支/当前工作区、是否已合入、未提交文件；从完整 P01 最新代码创建/复用 `feat/p02-runtime-web`，不得在旧 main 空代码基础上实现。核对 GitHub 文档/本地文件后确定实际工作树。
2. 实现依赖锁、路径配置、SQLite RuntimeDatabase/Repository、表索引/状态迁移、`AsyncSqliteSaver` 生命周期与 `build_lead_agent` 可选 saver；FastAPI lifespan 挂载资源与 Thread 创建/列表/历史空列表 API。
3. 前端增加 ThreadList 真实新建与切换；Agent 输入/Run 按钮注明 B 阶段尚未实现，不伪造执行。
4. 局部测试 `test_repository.py`（正常、404、唯一活跃、不可逆终态、隔离/事务）、`test_checkpoint.py`（同 Thread 保存/重新打开读取、跨 Thread 隔离）、受影响 config/health/lead；`npm run build`，仅真实可用接口的 Smoke。
5. 本次顺便复验此前 P01 中文注释/格式相关的直接受影响测试与 frontend build；不改 P01 行为，不展开无关重构。记录独立结果和 SHA。**A 未通过，不启动 B。**

**P02-B — 后台 Runner + Run API + 轮询前端**
1. 实现 `runtime/runner.py`、`runtime/streaming.py` 的基本 Agent 执行与最终结果收集；API 增加创建 Run/查询 Run。准入前检查模型配置，采用 2 workers + 8 等候、每 Thread 唯一活动 Run。`streaming.py` 在 B 阶段可先无 EventBus，仅收集真实执行结果；预留 C 阶段事件回调，不能自己另建事件协议。
2. 前端使用 B 的 Run 创建/查询 API，以有限轮询显示 CREATED/RUNNING/SUCCEEDED/FAILED，支持当前 Thread 下一轮对话；切换会话时停止旧轮询。
3. 局部测试 `test_runner.py`、`test_runs_api.py`：202 不等待模型、Thread 冲突 409、队列满 429、无 Key 503 且不建 Run、最终工具轨迹、模型失败/超时、终态不可二次修改、同 Thread 多轮 Graph 状态；`npm run build`。B 不假装已有 SSE。
4. 每次变更同步前端、README 与 `P02.md`；B 通过后才进入 C。

**P02-C — EventBus + SSE + 实时 Web**
1. 实现 512 条 Run 缓冲、64 条订阅通知、序号与 Last-Event-ID 校验；在 B 的 Runner 中注入 EventBus，新增 `/events` SSE 路由和模型 token/工具/错误/终态事件。
2. 前端用 `EventSource` 接收 `assistant_delta`（按 message_id 维护临时片段）、`tool_start/tool_end` 与 `assistant_final`；收到 `run_end` 或 `stream_gap` 时重新 GET Run 并结束当前流；仅本次 Run 可继续；防事件重复、跨 Thread 串台。
3. 局部测试 `test_events.py`、`test_runs_api.py`（POST 后订阅回放、断线后续跑、Last-Event-ID、丢失窗口、慢订阅不阻塞、成功与失败先入库后发结束）、`test_runner.py` 直接受影响内容、`npm run build`。不承诺完整 SSE 持久化。
4. B/C 每项前端展示的是确实已实现的功能，禁止演示用模拟结果冒充真实模型。

**P02-D — 重启恢复、真实联调与交付**
1. 集成历史 Run 读取、已保存消息和失败恢复提示；服务启动对孤儿 CREATED/RUNNING 标记 `FAILED/RUN_INTERRUPTED` 并阻止需恢复的 Thread 继续写。历史仅展示最近 50/最多 100 条 Run；记录边界。
2. 验证 `/health`、P01 calculator/CLI/demo 保持可用，完成 P02 页面、中文注释与长逻辑 1/2/3 说明，清除与真实行为不一致的注释；不动 P03+ 模块。
3. 用临时数据库与 Mock 做重启前后同 Thread 历史、不同 Thread 隔离、SSE 缺口回落、失败终态、工具实际调用 ID 的局部测试；如本地真实模型配置可用，再单独做普通两轮问答 + Tool Calling + SSE 真模型 Smoke。没有可用 Key 时记 `REAL_MODEL_SMOKE_BLOCKED`，不能假装通过。
4. 完整提交 `README.md` 和 `docs/progress/P02.md`：各小任务 SHA、实际执行命令、测试结果、前端功能/截图（有真实证据时）、未验证项。标记 `PENDING_REVIEW`，等待用户体验 Demo。**不自动开始 P03**。

#### P02-7. 成功条件与阻塞边界

必须分别证明：
- 创建 Thread 后同 Thread 两轮真正共享 Checkpoint，另一个 Thread 不共享；结束服务重新启动后可恢复成功对话的上下文。
- POST Run 返回 HTTP 202 后后台继续，运行期间 GET Run 看到真实状态；同 Thread 并发 409；排队满 429；缺配置 503 不产生幽灵 Run。
- 工具 `calculate` 调用的名称、参数、匹配 ID、成功/错误来自实际 ToolMessage；最后回答无效时不得 SUCCEEDED。
- SSE Token/Tool 事件顺序、POST 后首订阅缓冲、断线不取消、慢客户端显式 gap、终态后 GET Run 权威查询；刷新页面恢复历史。
- 启动对孤儿 Run 保守标 `FAILED/RUN_INTERRUPTED` 并显示需恢复提示；未实现暂停/无损恢复时不得假称能恢复。
- P01 健康/计算/一次性 Agent/CLI 保留；新增、修改后端的局部 pytest + Ruff 与前端 TypeScript/build 通过，真实模型和 Mock 的结果分开报告；每任务同步最简 Web 功能。
- 所有新改 Python/TS/TSX 关键逻辑遵守根目录 `AGENTS.md`：中文解释复杂机制，长流程 `1./2./3.` 分段；接口/模型描述保持现有行为。
- 只运行当前任务及直接受影响接口测试；不要因为迁移到 P02 就无边界跑 P00–P09 全集。关键行为改变/库冲突/Store API 无法按锁版实现，停止相关编码并提交精确证据给用户审核，Codex 不自行改技术栈。

**Git/停止条件**：本方案及 P02-A 代码已经位于 `feat/p02-runtime-web` 分支。B/C/D 以 [合并任务书](tasks/P02-BD.md) 一次交给 Codex，顺序实施，分别测试和提交 SHA，遇阻塞立即停下，不 reset/clean/force push，也不覆盖本地文件。最终 P02 Demo 完成后只标记 `PENDING_REVIEW`，用户审核通过才能 `ACCEPTED`；不得自动进入 P03。


### P03 — Workspace、文件安全与 Artifact

**业务链**：上传 → 获取 `file_id` → Agent 使用白名单文件工具读取/写出新文件 → 保存 `artifact_id` → 浏览器下载。文件数据进入 Thread 隔离目录，不进入 Git，不传宿主机绝对路径给 LLM。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `workspace/models.py` | FileRecord、ArtifactRecord、文件操作错误类型；文件记录包含 thread_id、run_id?、相对路径、sha256、size、mime、kind。 |
| `workspace/storage.py` | `save_upload/open_text/write_text/list_files/get_artifact`：使用 `data/workspaces/{thread_id}/` 隔离，先校验归属和安全路径，原子写入、限制文件大小和类型；使用 no-follow/目录句柄或等价安全策略防符号链接/TOCTOU，而非只靠字符串前缀。 |
| `workspace/repository.py` | SQLite 中新增 files/artifacts 表，记录来源、归属、文件大小与内部存储名，下载只能查登记过的 artifact_id。 |
| `tools/file_tools.py` | `list_files/read_text/write_text` 三项工具；工具只能访问授予 Thread 的虚拟目录，不开放 Path 对象、绝对地址、Shell 或通用 Python 解释器。 |
| `api/files.py` | `POST /api/threads/{thread_id}/files` 上传、`GET /api/threads/{thread_id}/artifacts` 列表、`GET /api/artifacts/{artifact_id}` 下载，校验文件归属和下载 MIME。 |
| `frontend/src/components/FilesPanel.tsx` | 上传、文件列表、下载；请求失败/文件过大有明确提示。 |
| `tests/test_workspace.py`、`tests/test_files_api.py` | 上传/读/写/下载、文件大小/路径穿越、符号链接、跨 Thread 访问、并发写冲突和失败清理。 |

**关键实现固定**：初版只接受 `.txt/.md/.csv/.json` 等可安全解码的文本格式作为 `read_text`，PDF 只保存上传而不宣称可以读取（P08 才解析）。`write_text` 使用临时文件加原子替换，默认禁止覆盖已存在产物，返回 Artifact ID。单用户也要做 Thread 归属判断，因为工具不应跨会话访问。文件工具的权限必须在 Python 执行层检查。

**实现次序**：P03-A Storage/路径安全 → P03-B Tool + SQLite Metadata/API → P03-C 文件面板及下载。局部测试只测新增文件链路和直接调用方，不重测所有 Agent。

**DeerFlow 参考**：`sandbox/security.py`、`sandbox/local/local_sandbox.py`、`app/gateway/routers/uploads.py`。本地 Sandbox 不等于不可信命令安全沙箱，不复制 Host Bash。

### P04 — Todo 规划、任务委派与 Sub-Agent

**业务链**：复杂目标 → 模型调用 `write_todos` 更新结构化计划 → `task` 工具指定角色和任务目标 → Dispatcher 限制并发、裁剪上下文、构造子 Agent → 子 Agent 调用允许的 Tool → 返回短摘要+证据/文件引用 → Lead 汇总。简单问题不需要强制规划。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `agents/state.py` | 基于实际 LangChain AgentState 扩展 `todos`；字段为 `todo_id,title,status`，合并规则必须保证更新同 ID 而非无限追加；并发更新先在父 Agent 串行归并。 |
| `tools/todo_tool.py` | `write_todos(items)` 验证状态 `pending/in_progress/completed`、合法 ID 和一次更新数上限；写入真实 State 并发布 todo_updated，禁止只输出自然语言 Todo。 |
| `agents/subagents/config.py` | 固定 general、research 两种 `SubAgentSpec`：name/system_prompt/allowed_tools/max_steps/timeout；初版禁止子 Agent 继续使用 task。 |
| `agents/subagents/dispatcher.py` | `dispatch(spec,input,parent_context)->TaskResult`；`asyncio.Semaphore(3)` 限制每 Run 总并发；使用子代理独立 messages，不拷贝父完整聊天日志；工具集取父授权与角色 allowlist **交集**。 |
| `agents/subagents/executor.py` | 使用 P01 Agent 工厂构建 child Agent，**不复用父 Checkpointer**（可设 False/None，以已锁版本实际语义为准），执行 asyncio 超时和错误归一；返回摘要、状态、证据/产物 ID，不能把完整子代理对话塞回父状态。 |
| `tools/task_tool.py` | 模型可调用的 `task(agent_type,description)`，由当前 Runtime 注入 task_id/run_id/权限上下文，不读取随意的全局单例；返回可序列化任务摘要。 |
| `runtime/task_registry.py` | 进程内 TaskRecord 生命周期 PENDING/RUNNING/COMPLETED/FAILED/CANCELLED/TIMED_OUT，输出对应 run 事件；默认无跨重启保证。 |
| `frontend/src/components/TodoPanel.tsx`、`TaskPanel.tsx` | 按 todo_updated/subtask_* 更新视图；不靠模型文本判断子任务终态。 |
| `tests/test_todos.py`、`tests/test_subagents.py` | 同 ID Todo 更新、非法转移、实际委派、角色权限、并发上限、超时、任务失败、父子 Checkpointer 隔离。 |

**默认约束**：`MAX_SUBAGENT_CONCURRENCY=3`、`MAX_DELEGATION_DEPTH=1`，每个子任务有 `max_steps` 和超时；子 Agent 默认只读 Workspace，写文件需要单独明确授权以避免并发覆盖。子任务结果未知要标记 UNKNOWN/FAILED 类别，不因为父模型在报告中写“已完成”就更改真实状态。

**实现次序**：P04-A Todo Tool/State → P04-B 一个串行子代理 → P04-C 三个并发以内、超时/取消/事件 → P04-D UI 与受影响合同测试。禁止把调度改成大型任务队列或随意扩展角色列表。

**DeerFlow 参考**：`agents/middlewares/todo_middleware.py`、`tools/builtins/task_tool.py`、`subagents/executor.py`，注意这些文件根路径均为 `backend/packages/harness/deerflow/`。父图 Checkpoint 不保证进程内子任务精确恢复。

### P05 — 统一 ToolRegistry、MCP 适配器与 Skills

**业务链**：Lead 请求可用工具 → Registry 合并内置工具与经批准的 MCP 工具 → ToolExecutor 统一校验权限/超时/异常 → 模型按需选择工具；当任务需要某种工作方法时，`list_skills/read_skill` 只加载对应 SKILL.md 的正文。**MCP 是工具来源，Skill 是执行说明，二者不是同一套运行机制。**

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `tools/registry.py` | `ToolRegistry.register/get/list_allowed`：按唯一名字注册工具（重名直接拒绝，不静默覆盖）；每项含 ToolSchema、权限级别、超时与来源；合并 P01、P03、P04 工具及 MCP Tool。 |
| `tools/executor.py` | `execute(tool_name,arguments,policy,context)`：先检查名字、权限、参数，再执行指定工具；按工具声明区分 read/write，超时、错误统一封装；未来网络有副作用操作遇未知结果不得盲重试。若 LangChain 的 tool lifecycle 与调用链不匹配，使用框架支持的 Middleware 包裹执行，避免另造与框架竞争的工具主循环。 |
| `tools/mcp_adapter.py` | 用 `langchain-mcp-adapters` 的现成 Client/工具转换接入配置好的 MCP Server，映射工具名/Schema/说明，执行统一转交 ToolExecutor；MCP 连接失败分类为 `MCP_UNAVAILABLE`，不能影响内置工具。 |
| `core/mcp_settings.py` | 使用明确的本地配置（如 `MCP_SERVERS` 或单个受控配置文件）声明 server_id、transport、URL/command、timeout、allowlist；第一版只允许用户预先配置的只读 Server，禁止模型自动新增任意 stdio command。 |
| `skills/models.py` | `SkillMeta(name,description,path,allowed_tools)`，记录必要元信息，不将所有正文常驻系统 Prompt。 |
| `skills/loader.py` | `discover_skills(root)` 读取受控本地 Skills 目录，`load_skill(name)` 使用安全 YAML 解析（需要时加入 PyYAML），验证名称唯一、正文大小上限、所需工具是否存在；禁止从任意 URL 自动下载安装 Skill。 |
| `tools/skill_tools.py` | `list_skills()` 输出名称/简介，`read_skill(name)` 返回本地 Skill 必要正文；模型只在需要时加载，激活不改变执行器 allowlist。 |
| `skills/public/example-research/SKILL.md` | 一个实际可执行的最小模板：输入目标、检索步骤、来源标注、输出规范；当前不实现 P07 的全部 Research 业务。 |
| `tests/test_tool_registry.py`、`tests/test_mcp.py`、`tests/test_skills.py` | 重名、拒绝越权、参数错误、超时、MCP 断开、坏 YAML、Skill 工具不存在、超长 Skill、只读权限下执行写工具被拒绝。 |

**固定权限策略**：工具默认 `DENY`，按 Run/角色显式构造 `allowed_tools`；子 Agent 可用工具是“父权限 ∩ 角色权限 ∩ 本次任务授权”，任何 Skill 提示都无权提升权限。ToolExecutor 对工具的名字和参数做可复验的检查，输出有明确错误代码、脱敏 Trace 和长度上限。不允许把远程 MCP 返回文本当成系统指令。

**实现次序**：P05-A Registry/Executor → P05-B 单个只读 MCP Server/失败处理 → P05-C Skill Parser/Tool → P05-D 权限与直接受影响的 Agent Tool Calling 测试。

**局部验收**：不改 Lead Agent 的核心循环即可注册一个新的 MCP Tool 与一个 Skill；连通实际可用的只读 MCP Server 或如实说明环境无法连接；工具不可通过 Skill/委派绕过授权。仅测对应的 registry/mcp/skills 测试及直接 Tool 集成。

**DeerFlow 参考**：`backend/packages/harness/deerflow/tools/tools.py`、`mcp/tools.py`、`skills/parser.py`、`skills/tool_policy.py`、`agents/middlewares/skill_activation_middleware.py`，所有均位于 `backend/packages/harness/deerflow/` 根下。

### P06 — 上下文压缩、预算、取消与恢复边界

**业务链**：Run 启动时设置模型/工具/时间预算 → 每次调用前后记录用量 → 长工具输出进入 Artifact，仅把短摘要/ID 注入消息 → 接近上下文限制时压缩旧消息并保护用户目标、Todo、引用与文件 ID → 任务结束时准确结算 Run；取消或服务重启走独立的 Runtime 状态逻辑。**上下文压缩不替代 Checkpoint，Checkpoint 不替代 RunService。**

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `runtime/budget.py` | `RunBudget(max_steps,max_tool_calls,max_seconds,max_input_tokens_estimate)`；`BudgetTracker.before_model/before_tool/record_usage`，触发上限后返回 `BUDGET_EXCEEDED` 与统计。估算 token 与提供方真实 usage 分开标记，禁止把估算说成实际账单。 |
| `agents/context.py` | `ContextManager.prepare(messages,todos,refs,budget)`：保留最近交互和关键用户约束；将旧消息摘要化，必要时调用已配置模型进行 summary；保护当前 Todo、真实 source_ids、artifact_ids，不丢失未完成步骤。 |
| `agents/middleware.py` | 通过官方 `AgentMiddleware` 或当前 `create_agent` 支持的中间件装配预算、工具输出长度、异常转换、摘要策略；**不重新实现模型/工具循环**。对支持的官方 Middleware 优先直接配置，仅对缺少的行为实现小型自定义包装。 |
| `runtime/usage.py` | `UsageRecord(run_id,task_id?,model,input_tokens?,output_tokens?,estimated)`，统计模型/子任务/工具耗时；缺失供应商 usage 时保留 unknown/estimated 标志，不虚构 0 成本。 |
| `runtime/runner.py`（修改） | 添加取消信号（`asyncio.Event` 或等价）与 `request_cancel(run_id)`；新工具执行前检查取消；已经开始的外部副作用不能假定立即停止或自动撤销；按真实结果写终态。 |
| `runtime/repository.py`（修改） | 增加 `CANCELLING`、`INTERRUPTED/UNKNOWN` 状态需要时迁移；启动时检查旧 RUNNING 并标记 `INTERRUPTED/UNKNOWN`，不自动重新执行未知副作用动作。 |
| `api/runs.py`（修改） | `POST /api/runs/{run_id}/cancel`：幂等请求，返回当前真实状态；已终结 Run 不重新启动。 |
| `tests/test_budget.py`、`tests/test_context.py`、`tests/test_cancel_recovery.py` | 超限停止、摘要保护、真实/估算区分、取消后不启动新工具、服务重启孤儿标记和外部写工具 UNKNOWN 不被盲重试。 |

**算法/约束固定**：
- 每 Run 默认 `max_steps=40`、`max_tool_calls=30`、`max_seconds=600`（可在配置中调整），保护系统不进入无限循环。模型使用量若不支持精确记录，标 `estimated`。
- 工具结果文本超过建议阈值 12 KB 时存入 Artifact 并给模型短摘要和引用 ID；裁剪不能破坏引用可定位性。
- ContextManager 只摘要较旧、已完成的交互；当前用户指令、尚未完成 Todo、关键证据/文件 ID 以结构化方式单独注入；摘要失败则按预算安全退出，不能静默丢上下文后继续。
- 重启时只恢复已经落盘的 Thread/Graph 数据与标记 Run，**不自动恢复进程内并发 Sub-Agent**；有副作用操作的结果 UNKNOWN 不重试。
- 对同一个 run_id 重复 cancel 应返回确定状态；若仍在调用外部工具，显示 CANCELLING/UNKNOWN 而不是提前声称 CANCELLED。

**实现次序**：P06-A Budget/Usage → P06-B Summary + Tool Output → P06-C Cancel/Restart 核查 → P06-D 局部故障注入。测试只测当前 Budget/Context/Runner/API 的直接影响，不重跑 Research/RAG 全量评测。

**DeerFlow 参考**：`agents/middlewares/summarization_middleware.py`、`tool_output_budget_middleware.py`、`loop_detection_middleware.py`、`runtime/runs/manager.py`、`runtime/runs/worker.py`（均在 Harness 根下）。

### P07 — Deep Research 的完整业务实现

**业务链**：用户给出研究题 → Lead 加载 `deep-research` Skill → Todo 分主题 → `search_web` 检索 → `fetch_webpage` 获取页面内容 → Sub-Agent 做独立分析 → `EvidenceStore` 汇总真实来源 → `ReportWriter` 输出 Markdown Artifact → 用户下载。**不重写一套固定 Deep Research Graph**，复用既有 Lead + Task + Tools + Skills。

**联网供应商固定**：首选 **Tavily Search API** 作为单一搜索适配器；通过 `TAVILY_API_KEY` 环境变量配置，搜索结果必须携带真实 URL、标题、片段。若账户不可用，任务标记外部依赖阻塞并告知用户，不由 Codex 擅自扩展为多个搜索框架。网页正文抓取走受限 `httpx`，只允许 http/https，限制大小/时长/重定向，并显式防 SSRF（拒绝 loopback、私有、链路本地地址和 DNS 重绑定风险）。不必自行编写复杂浏览器自动化。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `research/models.py` | `ResearchRequest(topic,scope?,report_format)`、`SearchHit(title,url,snippet,retrieved_at)`、`EvidenceRecord(id,url,excerpt,source_status)`、`ResearchReport(markdown,source_ids,artifact_id)`；来源未访问/抓取失败必须标注状态。 |
| `research/search.py` | `TavilySearchProvider.search(query,max_results=5)`：调用当前 Tavily SDK/HTTP API，转换为 SearchHit；过滤空 URL、去重、限制单次结果数；保留查询与检索时间及错误类别。 |
| `research/fetch.py` | `fetch_webpage(url)`：`httpx.AsyncClient` 有界超时、响应大小、Content-Type 与 SSRF/跳转检查；提取可阅读的网页文本并截断，不允许读取内网或本地文件。仅 HTTP 标题/摘要不足时明确“正文未核验”。 |
| `research/evidence.py` | `EvidenceStore.add/list/get`：保存 search/fetch 工具真实返回的 URL、片段、检索时间、状态及来源 ID；相同 URL 规范化去重。严禁模型自己生成新的“已检索来源”ID。 |
| `research/report.py` | `render_markdown_report(title,findings,evidence_ids,limitations)`：生成标题、研究方法、核心结论、对比、局限与来源清单；引用只能指向 EvidenceStore 中已经存在且满足引用条件的记录。将最终文本通过 P03 Workspace 保存为 Artifact。 |
| `tools/research_tools.py` | `search_web`、`fetch_webpage`、`save_research_report` 包装上述服务，加入 Registry 并声明超时/权限；工具的大返回内容存 Artifact/证据而非无限推给模型。 |
| `skills/public/deep-research/SKILL.md` | 明确输入、计划、分主题、搜索→核对、反向检索、合并、引用与停止标准；要求事实区分 verified/unverified，输出本项目支持的 Markdown 报告。 |
| `frontend/src/components/ResearchReport.tsx` | 展示报告、来源链接、无法验证提示和下载按钮；复用 P02 流事件、P03 Artifact API。 |
| `tests/test_research_search.py`、`test_research_evidence.py`、`test_research_report.py` | Mock 搜索结果转换、URL 去重、抓取失败、SSRF、虚假引用被拒绝、报告实际生成与 Artifact 下载。 |

**固定研究策略**：先由 Lead 评估问题范围，复杂任务创建 Todo；单个问题默认搜索不超过 5 条候选结果，每个 Run 总工具/Token/时间预算继承 P06；多个研究方向可由 P04 允许的 Research 子 Agent 并行检索；子 Agent 回传 **Findings + Evidence IDs + Missing** 而非全量网页文本。报告中没有真实证据的主张不得以确定性语气编成引用。只依靠搜索摘要的结论必须标记摘要级来源，不当作已精读正文。

**实现次序**：P07-A 搜索与抓取 → P07-B Evidence/引文 ID → P07-C Research Skill + 子任务报告 → P07-D UI 和一个真实网络 Smoke。测试只跑本次 research tests 和直接使用的 Tool/Artifact 接口，真实模型报告人工抽查主要来源。

**DeerFlow 参考**：`skills/public/deep-research/SKILL.md`、`skills/public/systematic-literature-review/SKILL.md`、`backend/packages/harness/deerflow/tools/builtins/task_tool.py`。Skill 负责工作方法而不是替代实际搜索工具。

### P08 — Docling + Chroma 多文档 RAG

**业务链**：用户从 P03 上传 PDF/Markdown/TXT → `DocumentService` 识别格式并调用 Parser → 保留真实页码/章节/文本结构 → Chunk → Embedding → Chroma 本地索引 → `search_knowledge(scope,query,top_k)` 返回真实 Evidence → Lead 生成带证据 ID 的回答；上传/解析失败或没有可用片段时拒答或标记不足。

**Embedding 决策**：使用 `langchain-openai.OpenAIEmbeddings` 的一个经测试支持的服务（独立 `EMBEDDING_MODEL`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` 配置，允许明确继承模型配置但不能假定 ChatModel 与 Embedding API 一致）；不用额外部署大型本地 Embedding 推理服务。调用失败则标记索引 FAILED，不写“已建库”。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `knowledge/models.py` | `DocumentRecord(id,thread_id,filename,content_sha256,parser_version,index_status)`；`ChunkRecord(id,document_id,index_version,source_text,page?,section?,offset?)`；`KnowledgeHit(chunk_id,document_id,excerpt,page?,score)`。页码无法可靠获得时为 null，不猜测。 |
| `knowledge/parser.py` | `parse_document(file_ref)->ParsedDocument`：文本直接解码；PDF 使用 Docling `DocumentConverter().convert(path)`，检查转换状态，提取结构化文档、页码/章节与原文。使用结构元素/provenance 保留真实位置；不要仅 export_to_markdown 后通过正则假推页码。重型同步解析放入线程，不阻塞 Async API。 |
| `knowledge/chunker.py` | `chunk_document(parsed,max_chars=1200,overlap=150)`：优先章节/段落边界，超长文本定长切片；产生稳定 `chunk_id=hash(document_id,index_version,position,source_hash)`，记录原文与真实位置。源文和用于召回的可选文本分开。 |
| `knowledge/embedding.py` | `EmbeddingProvider.embed_documents/embed_query`：单一模型与 API 适配，控制 batch/超时，记录 embedding model/version/dim；不把用户文档写进日志。 |
| `knowledge/vector_store.py` | `ChromaIndex.upsert/delete_document/search`：`chromadb.PersistentClient` 存 `data/chroma`，每条记录含 document_id、thread_id、chunk_id、index_version、page（可空时按驱动规则处理）；检索时强制使用 scope 过滤，返回 score/distance 的含义需准确声明。更新版本需先写新数据验证，再切换可见版本，不能混查新旧。 |
| `knowledge/service.py` | `ingest_document(file_id)`：P03 受控读取→解析→分块→Embedding→Chroma upsert→索引状态 READY；失败写 FAILED 并清理不完整版本。 `search_knowledge(thread_id,document_ids,query,top_k)`：校验归属和索引版本，只返回实际检索到的原文片段与引用位置。 |
| `knowledge/repository.py` | SQLite `documents`、`index_versions` 元数据，支持查看处理状态、重新建索引、删除过期索引；文件存储与 Chroma 不能假设有跨库事务，需要失败补偿。 |
| `tools/knowledge_tools.py` | `search_knowledge` Tool Schema、scope 白名单和 Evidence ID，不允许模型给出任意用户路径；只允许当前 Thread 已授权文档。 |
| `api/knowledge.py` | `POST /api/threads/{id}/documents/{file_id}/index`、`GET /api/threads/{id}/documents` 等最小接口（异步建索引可查询状态）；不能把耗时 Docling 解析直接堵塞事件循环。 |
| `frontend/src/components/DocumentPanel.tsx` | 上传后索引按钮/状态、文档选择、可跳转的来源页码或片段；不承诺具备完整 PDF 阅读器。 |
| `tests/test_parser.py`、`test_chunker.py`、`test_vector_store.py`、`test_knowledge_api.py` | 一份文本型 PDF/MD 解析、Chunk 位置一致性、索引检索、文档 Scope、无命中拒答、重建版本清理和失败恢复。 |

**固定检索逻辑**：V1 先 `top_k=5` 向量检索，命中片段附 `document_id/chunk_id/page/section` 及证据 ID；无可靠页码时只引用文件和片段，不伪造 PDF 页码。答案只能引用真实返回的 Evidence ID，禁止把生成摘要或虚构元数据当作原文事实。暂不做 Hybrid/Rerank、多级知识图谱和复杂智能路由，后续需有独立评测收益才扩展。

**实现次序**：P08-A Docling Parser/Chunk → P08-B Embedding/Chroma → P08-C Ingest/Search Tool 与引用 → P08-D 文档 UI 与局部金标 QA。只测 `knowledge` 当前模块及直接 Tool/API 消费者，不重跑 Deep Research 全套任务。

**参考**：DeerFlow 的 Workspace/Tool/Skill 接入形式；RAG 内部是我们独立实现，不把其 `deep-research/SKILL.md` 当向量数据库实现。Docling 官方从 `DocumentConverter` 返回 `ConversionResult`，应检查 `result.status` 并利用 `result.document` 的 provenance 信息，具体 API 用锁定版本实测。

### P09 — UI 完善、部署、定版评测与最终交付

**业务链**：在干净开发机按 README 启动 FastAPI + React → Web 创建/继续 Thread → 运行一个真实 Research 任务并下载报告 → 上传至少两份真实文档做跨文档问答 → 用 Workspace 工具生成真实文件 → 展示任务状态/错误/局部指标。这个阶段交付真实演示和可重复测量，不引入全新大功能。

| 新增/修改文件 | 编码必须完成的具体内容 |
| --- | --- |
| `frontend/src/components/RunTimeline.tsx` | 统一展示 Run 状态、Todo、Task、Tool 与 Artifact 事件，使用真实 EventEnvelope，不能从自然语言猜测进度。 |
| `frontend/src/App.tsx`、`frontend/src/api/client.ts` | 整理已有组件和异常状态、断线后的 `GET /api/runs/{id}` 同步；不引入复杂全站状态库。 |
| `backend/src/minideerflow/core/logging.py` | 统一 run_id/thread_id/task_id 的结构化摘要日志，敏感参数脱敏，不存 API Key、PDF 原文和私有响应。 |
| `eval/cases/research.json`、`eval/cases/rag.json`、`eval/cases/files.json` | 小型固定任务集与人工检查要求；包含明确真实来源/文档范围或确定性输出标准，不填伪造成绩。 |
| `eval/run_eval.py` | 调用本项目已有 API/Service 运行指定样本，记录 `git_sha/model/config/dataset_version/latency/token_usage/error` 与产物引用，原始结果写入 Git 忽略目录；报告标明无法运行和失败项。 |
| `Dockerfile` / `backend/Dockerfile`、`frontend/Dockerfile`、`compose.yaml` | 两个服务的单机启动；映射 Python 数据卷和必需的环境变量，不硬编码 Key；容器非 root，API 默认不无认证暴露公网。根据真实依赖控制体积。 |
| `README.md` | 安装、配置、PyCharm/终端启动、Docker、三条业务真实 Demo、已知局限和 DeerFlow 参考/源码许可；只列实际已实现功能。 |
| `tests/test_release_smoke.py`、前端对应组件测试 | 只验证本次新增部署/时间线/日志/发布合同；另实际运行三条**完整最终 Demo**，属于交付阶段约定而非每阶段全量回归。 |

**实施次序**：P09-A 前端体验/错误状态 → P09-B 定版样本和 Eval Runner → P09-C 单机 Docker/环境复现 → P09-D 三条真实 Demo、来源归属与安全复核。若没有模型/搜索/Embedding Key，明确将对应真实 Demo 标记 BLOCKED 或 NOT_RUN，不编造演示结果。

**固定评测口径**：Research 报告中实际引用有效性与人工支持度；RAG 的 Hit@K、引用可定位率、无命中拒答；文件任务实际产物校验；记录调用次数、时间和 Token（提供方返回或标 estimated）。不用 LLM 自评冒充人工真值。实测数据不足时不强行给 P95 等指标下结论。

**验收**：新环境可按 README 启动；三条演示分别拥有输入、脱敏 Run 记录、真实文件/引用、版本与失败说明；能证明工具限额、安全文件规则和外部不可用时的真实失败行为。最终是否执行全量历史 pytest/E2E 由用户另行决定，Codex 不自动扩大测试范围。

**DeerFlow 参考**：`frontend/src/components/workspace/`、`frontend/src/core/tasks/context.tsx`、`backend/packages/harness/deerflow/runtime/runs/manager.py`；只参考事件/界面组织，不复制完整界面与复杂运行时。

## 6. Codex 执行规则：让本地 AI 用最少上下文开发

**每次启动新阶段，先由 ChatGPT 根据最新代码设计并由用户批准本阶段详细方案；Codex 不承担阶段方案设计。**

每次仅交给 Codex：
- **已经由用户批准的当前阶段详细设计**及本次子任务 ID/验收要求，不把未批准的后续阶段预案作为执行指令；
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

规划、技术取舍、阶段详细设计和任务步骤只保留在本文件；每个阶段单独维护一份真实执行记录，不重复粘贴开发任务书。用户审核通过某阶段具体方案时，更新本文件的对应 Pxx 段落；**Codex 只更新当前正在执行的 `docs/progress/Pxx.md`**，其他阶段保持原样。未来阶段已有逐文件预案也必须重新走设计审核流程。

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
