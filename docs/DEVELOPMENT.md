# 开发方案、任务顺序与局部测试规则

> **代码可读性规范**：所有阶段代码同时遵循仓库根目录 [AGENTS.md](../AGENTS.md)：中文关键注释、较长逻辑按 1/2/3 分段、注释重点解释机制与边界，保持既定 API 和业务逻辑不变。每次 Codex 任务必须执行代码可读性自查。

**方案版本**：v2.0 · 2026-11-06  
**当前状态**：P01–P05 的实际 Python/TypeScript 代码已分别交付到 GitHub 开发分支；P02/P03/P04/P05 均为 `PENDING_REVIEW`（待用户最终手动验收）。P05-A/B/C/D 远端真实代码已核验；P06 的预算、上下文与取消/恢复详细设计已在 `feat/p06-context-budget-cancel` 分支完成，状态 `PLAN_READY`、**尚未编写 P06 业务代码或运行 P06 测试**。各阶段代码/实测以对应 `docs/progress/Pxx.md` 为准，旧 P02 早期设计措辞只代表历史授权。  
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


### P03 — Workspace / 文件工具 / Artifact（2026-11-06 逐文件正式设计）

> **P03：PLAN_READY（设计写入 GitHub，尚未编码）。** 用户于 2026-11-06 明确请求“启动 P3”；这允许启动 P03 的设计与 Codex 交付，但**不表示 P02 的手动验收已实测通过**。P02 进度继续保持 `PENDING_REVIEW`，P03 从包含全部 P02 代码的远端 `feat/p03-workspace-artifacts` 分支实施。编码者必须先读取 [P03-A/B/C 连续实施合同](tasks/P03-ABC.md)，按 A→B→C 各自局部测试和提交；范围变更/安全测试失败应停止，不能假装完成。

#### 1. 用户可见业务链、保留项和非目标

**一期闭环**：用户在现有会话选择文件 → `multipart/form-data` 上传 → 后端流式限制文件大小、存入 Thread 隔离 Workspace、登记真实文件元数据并返回 `file_id` → 主 Agent 在**服务端可信 Run Context** 下调用 `list_files/read_text/write_text` → 文件工具生成真实文件与 `artifact_id` → 业务库登记 Artifact → 前端列表查看、用登记过的 ID 下载文件，刷新与重启后仍可查询。旧 P01 计算、P02 Thread/Run/SSE/Checkpoint、调试入口均保留。

**文件能力本期只做**：文本上传 `.txt/.md/.csv/.json` 严格 UTF-8、上传 PDF（仅原样存储，**P08 才解析**）、有界 `list_files`/按 `file_id` 的 `read_text`/受控新建 `write_text`、产物列表与下载、局部前端。无需模型也能上传、列表和下载。**不做**任意 Shell/Python、任意宿主机路径、目录递归、覆盖/编辑已有文件、文件删除/分享、扫描 PDF 解析、RAG、文档索引、全文搜索、OCR、复杂 Sandbox、Sub-Agent、MCP、批量上传。

P02 的 `Run` 状态继续是权威任务终态；成功生成文件也需真实落盘/入库，不根据模型文案猜“文件已创建”。**文件系统与 SQLite 无联合事务**；先安全落盘后登记，登记失败尽力清理新文件并保证不通过 API 访问未登记的残留；崩溃留下的孤立临时文件不会被当成产物，后续专门清理可延期。

#### 2. 现有实际代码接入

P02 已有：`src/minideerflow/main.py`（FastAPI lifespan，`AsyncExitStack`、业务 SQLite/Checkpointer/EventBus/Runner）；`runtime/db.py`（`RuntimeDatabase.init_schema()` 和事务）；`runtime/repository.py`（Thread/Run 一致性）；`runtime/runner.py`（`RunService._execute_run` 中组装 `build_lead_agent(model,[calculate],checkpointer)`）；`runtime/streaming.py`（`stream_agent(agent,thread_id,message,event_sink,on_graph_start)`）；`agents/lead.py` （`create_agent`，可选 Saver）；`frontend/src/App.tsx` + `ChatPanel.tsx`（受控 selected Thread、SSE/Run 终态）；`frontend/src/api/runtime.ts`。

**重要设计调整**：
- 原 P03 粗略描述“按相对路径读写”，改为**所有模型可调用的文件读取操作只接受不可猜的 `file_id`；新文件写入只接受安全显示名 `filename` 和文本 `content`**。磁盘真实路径仅由后端 UUID 内部键决定；模型不提供 `thread_id`、`run_id`、`workspace_root` 或绝对地址。
- P03 的可信 `WorkspaceContext` 在创建 Run 的后端 `runner.py` 生成，并用 LangChain `create_agent(...,context_schema=WorkspaceContext)` + Graph `astream(...,context=context)` 注入 `ToolRuntime[WorkspaceContext]`；禁止来自用户 Prompt/工具 JSON 的会话身份，工具侧必须校验真实归属。当前锁版是否支持 `context=`、`ToolRuntime` 隐藏注入，需在 A/B 编码前用实际小样/假模型验证，若不兼容**停止并记录证据，不退化为进程级可变全局 Thread**。
- 上传有独立 HTTP 入口，没有 Run；模型产物必须关联当前真实 Run（`run_id` 由 Runner 内部传入），不能写进其它 Thread。
- 现有 `RuntimeDatabase` 与 `RuntimeRepository` 不复制。新增 `WorkspaceRepository` 共用同一 SQLite 连接和写事务；`RuntimeDatabase.init_schema()` 最小追加文件/产物表，无 ORM 或数据库迁移框架。P03 从新安装的文件表为空开始，原 Thread/Run 数据保留。
- P01 `/api/demo/agent` 和 CLI 默认继续仅注册 `calculate`，没有 WorkspaceContext 也不能调用文件工具；P03 File Tools 仅在 P02 托管 Run 路径注册。

#### 3. 可信身份、文件存储与安全策略（不可弱化）

**磁盘**：默认 `backend/data/workspaces/{thread_id}/`，路径基于 backend，不依赖 cwd；可配置 `WORKSPACE_ROOT_PATH`，必须与 Runtime/Checkpoint SQLite 文件不冲突，拒绝工作区根目录 symlink。每个 Thread ID 必须已登记在业务库且为合法 UUID。目录仅 Thread 一层、不支持用户提供子目录；存储文件名由后端生成 `file_id`/UUID hex，**绝不直接使用浏览器原文件名或模型提供的 filename 作为磁盘路径**。展示文件名保存元数据而非路径。

**POSIX（macOS/Linux）安全读写**：对目录采用 `os.open(...,O_DIRECTORY|O_NOFOLLOW)` 固定 `dir_fd`，在已打开的 Thread 目录 fd 下用 `os.open(...,dir_fd=fd,O_NOFOLLOW|O_CREAT|O_EXCL,...)` 写入 UUID 临时名；文件写完检查大小/sha256、`fsync`，用同目录 `os.link(src,dst,src_dir_fd=...,dst_dir_fd=...,follow_symlinks=False)` + 删除临时名完成**不可覆盖的原子发布**（或另一个明确同等级无覆盖原子方案），打开读取用 `O_NOFOLLOW` + `fstat` 校验常规文件、登记大小/哈希。拒绝符号链接、硬链接非预期文件、不受信任的 workspace 根目录、非 POSIX 能力缺失时 **fail closed**；不可只用字符串前缀、`Path.resolve()` 或“先 `exists()` 再 `open()`”充当 TOCTOU 防护。所有创建文件默认 `0o600`，目录 `0o700`；不从 HTTP 提供真实磁盘绝对路径。**仅限单用户本地回环，不宣称它可防御能直接修改本进程数据目录的同 OS 用户/恶意宿主进程**。

**显示名**：Unicode NFC、1–120 字符，允许中文/空格；拒绝 `/`、反斜杠、NUL、控制字符、`.`、`..`、绝对路径、盘符、首尾空白；Web `Content-Disposition` 使用安全 filename + RFC 5987 编码，不直接拼接不可信 header。相同 Thread 的**产物显示名**不得覆盖已存在产物，返回 `ARTIFACT_NAME_CONFLICT`；上传同名原文件可并存，因选择 `file_id` 无歧义。

**类型与限制**：
- 接受 `.txt` / `.md` / `.csv` / `.json`（严格 UTF-8，非文本不能伪装），每个最多 **2 MiB**；`.pdf` 最多 **10 MiB**，只校验 PDF 基本签名并以 `application/pdf` 保存，P03 `read_text` 禁止 PDF。
- Thread 最多 **50 个已登记文件**，合计最多 **30 MiB**；文件工具 `write_text` 仅可创建四种文本后缀，UTF-8 编码后最多 **128 KiB**；`read_text` 最多向模型返回 **64 KiB** 的完整文本，超出就返回明确 `TOOL_READ_LIMIT`，不得静默截断。
- 上传从 `UploadFile` 每次读取最多 **64 KiB** 并持续计算长度/哈希；不要一次 `await file.read()` 全读入内存，不信任 HTTP `Content-Length`、浏览器 MIME 或扩展名与内容完全一致。请求需要新增 `python-multipart` 并锁版。文件内容是**不可信资料**，不能因为它包含指令而修改 Run 的系统 Prompt、权限/工具白名单。
- 完成文件存储和数据库登记是两个步骤，任何超额、数据库约束、写异常、任务取消或上传中断都应清理临时/新文件；**不能覆盖旧文件**。可保留原子发布后异常清理的最佳努力行为并标注无法保证跨库/跨文件原子性。下载必须先查元数据关联 Thread、file、artifact，再以无跟随 fd 读取已登记文件，读取完成后将已验证内容返回（文件最大 10MiB），不要先查路径再让 `FileResponse` 二次打开产生 TOCTOU。
- 请求侧 `thread_id` 仅用于 API 业务归属匹配，**由于暂无登录认证，任何知道本地 HTTP 接口的进程都可枚举 Thread**；P03 不是面向公网的安全多租户隔离。工具侧更严格：所有文件 ID 必须匹配可信 `WorkspaceContext.thread_id`；不得从模型参数取得其它 Thread 的身份。

#### 4. SQLite 元数据与一致性

沿用 P02 `runtime.sqlite3`。新增：
- `files`: `id TEXT PRIMARY KEY`（`file_id`）；`thread_id TEXT NOT NULL REFERENCES threads(id)`；`run_id TEXT NULL REFERENCES runs(id)`；`display_name TEXT NOT NULL`；`storage_key TEXT NOT NULL UNIQUE`（内部 UUID，非用户原路径）；`kind TEXT CHECK(kind IN ('UPLOAD','ARTIFACT'))`；`mime TEXT`；`size_bytes INTEGER`；`sha256 TEXT`；`created_at TEXT`；对 `thread_id,created_at,id` 建索引；`kind=ARTIFACT` 的产物名在 Thread 内唯一。
- `artifacts`: `id TEXT PRIMARY KEY`（`artifact_id`）；`file_id TEXT UNIQUE NOT NULL REFERENCES files(id)`；`thread_id TEXT NOT NULL REFERENCES threads(id)`；`run_id TEXT NOT NULL REFERENCES runs(id)`；`created_at TEXT`。插入时需事务验证 `files.kind=ARTIFACT`、`file.thread_id=artifact.thread_id`、`run.thread_id=artifact.thread_id`，不能仅靠前端给的 ID。关联到真实 run 的产物即使 Run 最后 FAILED 也仍保留，并显示实际可下载状态，**不能让模型凭空声称完全成功**。
- 上传登记与 Thread 额度检查在同一事务；生成文件/Artifact 的双表登记在一个 SQLite 事务。若注册失败，清理本次新文件，保留旧记录与旧文件。文件元数据只含已登记资源，API 禁止直接按磁盘路径检索。

#### 5. HTTP / 模型工具合同

**HTTP**（新路由 `api/files.py`；全部只调用 WorkspaceService/Repository，不手写文件系统路径）：

| 方法 / 路径 | 输入 | 成功行为 |
|---|---|---|
| `POST /api/threads/{thread_id}/files` | `multipart/form-data` 字段 `file` 单文件 | 201 `FileRecord`（`id/thread_id/display_name/kind/mime/size_bytes/sha256/created_at`），不返回 storage_key/绝对路径 |
| `GET /api/threads/{thread_id}/files` | 无 | 200 `FileRecord[]`，按创建时间稳定排序；不存在 Thread 404 |
| `GET /api/threads/{thread_id}/artifacts` | 无 | 200 `ArtifactRecord[]`，含 `artifact_id/file_id/display_name/size_bytes/mime/run_id/created_at` |
| `GET /api/artifacts/{artifact_id}?thread_id=<UUID>` | 需要 thread_id 查询值，仅作为本地关联校验 | 200 文件 bytes，可信 MIME 与 `Content-Disposition: attachment`；仅登记 Artifacts，可下载；不存在或归属不符 404 |

新增 GET files 是为了 P03 前端刷新后能列出已上传的真实文件，原计划遗漏此接口。GET artifact 通过 ID+thread_id 校验归属，但由于无认证不能宣称提供多用户权限。

错误为现有 `{"detail":{"code":"...","message":"..."}}`：`THREAD_NOT_FOUND` 404；`FILE_NOT_FOUND`/ `ARTIFACT_NOT_FOUND` 404；`INVALID_FILENAME` / `UNSUPPORTED_FILE_TYPE` / `INVALID_FILE_CONTENT` / `INVALID_FILE_PATH` 422；`FILE_TOO_LARGE` 413；`WORKSPACE_QUOTA_EXCEEDED` 409；`ARTIFACT_NAME_CONFLICT` 409；本地安全能力缺失 `WORKSPACE_UNAVAILABLE` 503。API 错误不能暴露绝对路径、用户文件真实正文、环境变量或内部 SQL。

**LangChain Tools**（新 `tools/file_tools.py`）：
- `list_files(runtime: ToolRuntime[WorkspaceContext])`：只返回当前 Thread 已登记文件的**有限元信息**（file_id、name、kind、size、mime），最大 50 项。
- `read_text(file_id: str, runtime: ToolRuntime[WorkspaceContext])`：工具调用 JSON 中只有 `file_id`；校验 File 属于 runtime.context.thread_id，再安全读取对应文本，PDF/过大文件返回稳定错误，不向模型泄露路径。
- `write_text(filename: str, content: str, runtime: ToolRuntime[WorkspaceContext])`：工具 JSON 只有 filename/content；使用 runtime.context.thread_id + run_id + workspace service 验证归属，新建安全 Artifact，返回包含 `artifact_id/file_id/filename/size` 的结构化 JSON 字符串。旧名冲突直接错误，不覆盖。对预期业务失败返回 P02 可识别的 `ERROR[CODE]: safe message`；不能把故障当作成功工具回执。
- `WorkspaceContext` 是仅由 Runner 在每次运行构造的 dataclass（`thread_id`、`run_id`、`workspace_service`），通过 `ToolRuntime` 隐式注入，**不能出现在模型可见 Tool JSON Schema 中**。只将这些工具添加到 P02 持久 Thread Run 的 Agent；P01 独立 Demo 和 CLI 保持原工具范围。
- `agents/lead.py` 在不改变原 Prompt 的前提下允许可选 `context_schema` 透传 `create_agent`；`runtime/streaming.py` 为 `astream` 提供可选 `context`；`runner.py` 每轮创建 Context 并注册 `calculate + file_tools`。应真实验证 `ToolRuntime` 在锁定版本的注入机制。不可把 FileService 放进 Graph 持久 State 或用进程级可变的 `CURRENT_THREAD_ID`。
- 文件工具和上传页面的失败/错误展示必须清晰；P02 `run_end` 后前端重新拉取文件、Artifact 列表。可在确实取得登记成功 Artifact 时发 `artifact_created` SSE（可选，仅在真正注册完成后），**不得为了事件而推测模型写文件**。不改 P02 Run 终态/Tool Trace 的语义。

#### 6. 新改文件的确定职责

| 路径 | 实现点 |
|---|---|
| `backend/pyproject.toml` + `backend/uv.lock` | 新增 `python-multipart`，不无关升级 P02 依赖；uv locked sync |
| `backend/src/minideerflow/config.py` | `workspace_root_path`、大小/数量阈值固定常量或受界限的 Settings；backend 路径基准 |
| `backend/src/minideerflow/runtime/db.py`（少量修改） | 添加 files/artifacts DDL 与索引，保持 P02 事务/迁移不变 |
| `backend/src/minideerflow/workspace/models.py` | `FileKind/FileRecord/ArtifactRecord/WorkspaceError/WorkspaceContext`、严格文件名/扩展名/UTF8 校验 |
| `backend/src/minideerflow/workspace/storage.py` | `WorkspaceStorage`: 安全打开目录 fd、`save_upload_stream`、`save_text`、`read_registered`、`discard_new`；原子无覆盖、哈希/大小和 symlink 防护 |
| `backend/src/minideerflow/workspace/repository.py` | `WorkspaceRepository`: `register_upload`、`register_artifact`、`get_file`、`list_files`、`list_artifacts`、`get_artifact`；业务库事务归属/额度/唯一名 |
| `backend/src/minideerflow/workspace/service.py` | `WorkspaceService`: 先安全写→事务登记→失败清理；上传流、按 thread+file_id 文本读取、按 Run 产物写入、下载 bytes；协调两个数据源而不替换 RunRepository |
| `backend/src/minideerflow/tools/file_tools.py` | 三项 `@tool`，`ToolRuntime[WorkspaceContext]` 隐式注入；严格不接受客户端 thread/path 参数；返回安全 JSON 或规范 ERROR |
| `backend/src/minideerflow/api/files.py` | 四个路由、`UploadFile`/Field 校验、HTTP 错误映射和带安全 header 的下载 |
| `backend/src/minideerflow/main.py` | lifespan 初始化 WorkspaceStorage/Repository/Service，挂载 `app.state.workspace`，传入 RunService；注册 files router；原关闭顺序不变 |
| `backend/src/minideerflow/agents/lead.py` | 可选 `context_schema`；不改 P01 Prompt/独立路径 |
| `backend/src/minideerflow/runtime/runner.py` + `streaming.py` | 为 Thread Run 提供可信 Context、注册 file tools、传递 `context=`；原 ToolCall/SSE/Run 成功判定保持；P01/模拟测试可不启用 workspace |
| `frontend/src/api/files.ts` | `uploadFile/listFiles/listArtifacts/downloadArtifact`（download 必须带当前 Thread ID）；multipart `FormData` 不自行设置 Content-Type |
| `frontend/src/components/FilesPanel.tsx` | 上传、已上传列表、产物列表、下载；loading/error/上限/PDF 未解析说明；真实 Run 终态后刷新 |
| `frontend/src/components/ChatPanel.tsx`、`frontend/src/App.tsx`、`frontend/src/styles.css` | 当前 Thread 文件面板及 Run 结束后的文件列表更新；保留 SSE、历史、P01 独立调试区，不添加假数据 |
| `backend/tests/test_workspace.py`、`test_files_api.py`、`test_file_tools.py` | 真临时目录+临时 SQLite、Fake 模型验证上传/安全 FD/工具注入/跨 Thread/下载与异常，必要时更新 P02 直接消费者测试 |
| `README.md`、`docs/progress/P03.md`、`.env.example` | 本阶段实际 Demo/路径/限制，三部分各自真实测试+SHA；绝不提交上传内容、Workspace 文件或 Key |

#### 7. A/B/C 实施顺序与各自局部验收

**P03-A：安全 Workspace + 元数据 + 上传/列表 + 可操作前端**
1. 在已有 P02 全量代码上验证后端/前端依赖和目录；新增 `python-multipart`、Settings、存储安全 FD、文件上传数据表/Repository/Service、`POST /files` 与 `GET /files`、前端 FilesPanel 的上传与真实列表（产物入口预留但不可装作已可下载）。
2. 实测严格文件名、扩展名、UTF8、PDF 只存储、2/10 MiB 大小、每 Thread 50 项/30MiB、UUID 文件名、原子无覆盖、symlink/dirfd、防跨 Thread 指定文件、超额/异常清理、重启文件仍可列出。无需模型。
3. 只测 `test_workspace.py`、`test_files_api.py`（上传/列表部分）及直接受影响的 config/health；Ruff、`npm run build`、真实 HTTP 上传+刷新。**A 成功才继续 B。**

**P03-B：真实 File Tools + Artifact 登记/下载 + Agent/前端联动**
1. 新增 ToolRuntime/Context、`list_files/read_text/write_text`；调整 `build_lead_agent`/Runner/streaming 让**实际 Thread Run**取得 file tools。新增 Artifact 双表登记、GET artifacts 与下载、FilesPanel 实际下载和 Run 结束自动刷新；P01 旧一次性 Agent 不能调用文件工具。
2. 用假模型真实 Tool Calling 测试：上传两个文本（含中文）；本 Thread `list_files/read_text`、`write_text("summary.md","...")` 产出真实 artifact_id 与下载正文；不同 Thread 的 file_id 不可读；Agent 不得提供 thread_id/run_id 作为模型参数；拒绝 PDF read、越界 UTF8、恶意文件名与覆盖；失败 ToolMessage 可见 ERROR、失败 Run 不报假成功。工具返回不含宿主机路径或私人凭据。
3. 局部测试 `test_file_tools.py`、`test_files_api.py`、`test_workspace.py` 和直接受影响的 `test_runner.py/test_lead.py/test_runs_api.py`，Ruff/TS Build + Fake HTTP/真实浏览器；**B 成功才继续 C。**

**P03-C：跨重启、异常安全、实际联调与可读性收尾**
1. 复核文件 SHA/归属、下载实际内容与 MIME/header；应用重启重新打开两库，文件/Artifact 元信息与文件本体仍存在；模拟上传中断/元数据提交失败/同名产物争用，确保不覆盖旧文件、不暴露未登记临时文件。
2. 前端上传文本文档→Agent 用真实文件工具读入→根据指令创建 `summary.md`→网页可下载；按当前 Thread 的 Run 结束状态刷新，页面 reload 后仍可下载。若模型配置有效，做单独真实模型 Tool Calling Smoke；不可用则注明 `REAL_MODEL_FILE_SMOKE_BLOCKED`，Fake 测试不冒充真实。
3. 保留 P01/P02 路由/Checkpoint/SSE/Token/工具轨迹功能；中文关键注释，长逻辑 1/2/3 分段。仅运行 P03 新改及直接受影响用例、Ruff 和前端构建；逐项记录 A/B/C 测试命令、结果、提交 SHA、实际界面测试、未验项，末尾标 `PENDING_REVIEW` 并等待用户手动验收。不得进入 P04。

**参考**：DeerFlow v2.0.0 源码 `backend/packages/harness/deerflow/sandbox/security.py`（本地并非真实安全沙箱）、`backend/packages/harness/deerflow/sandbox/local/local_sandbox.py`（路径映射；**不要复制 Host Bash**）、`backend/app/gateway/routers/uploads.py`（上传分块和上限）；LangChain 官方 [ToolRuntime 与注入](https://docs.langchain.com/oss/python/langchain/runtime)、[create_agent](https://reference.langchain.com/python/langchain/agents/factory/create_agent)；FastAPI [UploadFile 与 python-multipart](https://fastapi.tiangolo.com/tutorial/request-files/)；Python [dir_fd/O_NOFOLLOW](https://docs.python.org/3/library/os.html)。Codex 只阅读当阶段相关源码/当前本地锁定签名，不擅自扩大系统范围。

**停止条件**：若本地平台不支持所要求的原子 no-follow 路径安全、官方 Runtime Context 隐式 Tool 注入无法与锁定版本兼容、任何 Thread 跨越/覆盖风险或关键测试失败，**停止下一子任务**、提供复现证据并等用户决定。不能通过松绑安全约束“把功能跑起来”。所有测试用临时两库/临时工作区、Fake 模型，不读写用户真实文件/密钥，不记录上传正文到日志；Git 不跟踪 workspace 文件。用户授权启动 P03 设计，**不表示允许自行合并 P02 到 main、清除 P02 审核状态或自动开始 P04**。


### P04 — Todo 规划 / task 委派 / Sub-Agent（2026-11-06 正式详细设计）

> **P04 当前为 PLAN_READY：仅设计与 GitHub 任务合同完成，尚无 P04 新增业务代码或测试。** 用户请求“设计 p4”，并未确认 P02/P03 亲自验收通过；两阶段各自 `PENDING_REVIEW` 保留。新分支 `feat/p04-planning-subagents` 从包含 P01–P03 实际代码的 `feat/p03-workspace-artifacts` 派生，绝不从 `main`（缺前期实现）重新建工程。
>
> **Codex 可执行任务**：[P04-A/B/C/D 连续逐文件合同](tasks/P04-ABCD.md)。先确认阶段设计，再由 Codex 实施；A→B→C→D 各自局部测试、提交、同步前端，遇关键失败立即停止，不自动进入 P05。

#### 1. 本阶段用户业务与明确边界

**主流程**：用户向当前 Thread 提交复杂目标 → Lead Agent 自行判断要不要计划 → 调用真实 `write_todos` 将计划写入 LangGraph State 并将**当前 Run Todo 快照**记入 SQLite → Lead 用 `task(agent_type,description,todo_id?)` 委派角色 → Dispatcher 限额启动完全隔离的 child `create_agent` → 子 Agent 用允许的真实工具执行 → 系统记录 Task 状态/短结果/来源文件 ID，向同一个父 Run 的 SSE 发布变化 → Lead 收到工具回执后汇总，页面同时显示 Todo、子任务状态与原有流式回答、Artifact。

**简单问题不强制规划/委派**：例如“你好”“计算 1+2”直接沿用 P02/P03 主 Agent 逻辑，通常不触发新工具。**不做**：自主后台离线子任务、跨进程/分布式 Task 队列、子 Agent 再委派、动态创建无限角色、外网搜索/RAG/MCP（P05及以后才有）、批准后重放/精确 Checkpoint 恢复、任意 shell 或 Python。用户可中断浏览器 SSE，但 P04 **不新增**服务端取消按钮/API；P02 Run 超时/进程关闭会取消当次内部子 Agent，按既定保守恢复策略处理。

**角色仅有** `general` 与 `research`：
- `general`：通用归纳、精确计算、当前 Thread 文本读取；**工具仅** `calculate/list_files/read_text`。
- `research`：针对用户已经给出的信息、当前 Thread 已上传文本做分析、差异整理、证据提取；**工具仅** `list_files/read_text`。名称“research”不代表已具备联网检索，必须在 Prompt/前端清楚说明本期仅基于已有材料；不能制造 URL、声称在线调研。
- 两者都**没有** `task/write_todos/write_text`，不直接生成 Artifact；Lead 仍保留 P03 `write_text` 来汇总后生成最终文件。子任务默认只读 Workspace，这避免并发覆盖文件及来源不清。

**业务验收示例**：用户上传一份 `notes.md`，请求“将文档的核心观点、潜在问题分别分析，最后创建 summary.md”，Lead 写结构化 Todo → 两次真实 `task` 委派 → 子 Agent 用 `read_text` 获取同一 Thread 已登记文件 → Lead 接收两份短结果并调用 `write_text` → 前端展示 Todo、任务完成状态及实际 Artifact 下载。模型不按预期调用工具时需如实记录，不能伪造多 Agent Demo。

#### 2. 现有代码接入与关键设计选择

P03 实际已有 `agents/lead.py:build_lead_agent(model,tools,checkpointer,context_schema)`，`runtime/runner.py:RunService._execute_run()`，`runtime/streaming.py:stream_agent(...,context)`，`runtime/events.py:EventBus`，`runtime/repository.py:RuntimeRepository`，`runtime/db.py:RuntimeDatabase`，`workspace/models.py:WorkspaceContext`（frozen dataclass，`thread_id/run_id/workspace_service`），`tools/file_tools.py` 的 `ToolRuntime[WorkspaceContext]` 权限校验与 `calculate`；React ChatPanel/RunStatus/SSE/FilesPanel。P04 **复用**所有上述能力，不复制第二套数据库、消息系统或 Agent 事件桥接。

采用**父 Agent 工具型 Supervisor**，不另起新 StateGraph 分支架构；子代理通过 `task` 工具在父 Agent ToolNode 内 await 子 Agent，多个 tool_call 可并发执行，但父 Agent 要等待结果才继续。与 P02 后台 Run 不同：P04 的 child `async def` 只是异步 I/O，不表示主 Agent 可在子任务运行期间另开新的同 Thread Run。

**可信上下文**：新增 `AgentRunContext(WorkspaceContext)`，包含 `todo_service`、`task_dispatcher`、`event_sink` 等依赖，全部仅由 `RunService` 在真正的 `run_id/thread_id` 下生成。P03 文件工具对 `WorkspaceContext` 的 `isinstance` 校验必须仍成功；模型可见 `task` 参数中不包含可信身份。子 Agent 单独使用 `ChildContext(WorkspaceContext)`，其 `run_id` 必须指向**父真实 Run**以便受控只读工具校验；子 Agent 不获得 task_dispatcher、不包含 write 类工具。任何伪造 Context/跨 Thread/file_id 都应失败。

**Graph State 与可恢复页面**：`agents/state.py` 扩展已锁版本 `langchain.agents.AgentState`，加入 `todos: NotRequired[list[TodoItem]]`，通过 `state_schema` 传给父 `create_agent`；`write_todos` 返回 `langgraph.types.Command(update={"todos":完整列表,"messages":[ToolMessage(tool_call_id=runtime.tool_call_id,...)]})`。这一更新应在同 Thread 官方 SQLite Checkpointer 中保留，并可由模型后续步骤读取。由于 Thread 的状态会被下一轮 Run 覆盖，**历史列表不能只读最新 Checkpoint**：每个 Run 的 Todo 快照需同时存在业务 SQLite `run_todos` 表，以供刷新页面、切换会话、应用重启后查询。两份状态不存在跨库事务，SQLite 先提交快照，再返回 Command；Graph 后续 Checkpoint 失败按已有 Run FAILED + Thread 需恢复处理。下一个 Run 开始时 Graph 输入显式 `todos=[]` 重置本轮计划，不污染其它 Run，历史快照仍在数据库。

**并发更新规则**：`write_todos` 每次提交**完整** Todo 列表，`todo_id` 固定，最多 8 条、标题长度 1–120，状态 `pending/in_progress/completed`。旧 todo_id 不能随意删除/换 ID，状态不能从 completed 回退；允许添加新 ID；新建/更新先在 SQLite 原子校验再替换快照，同 ID 更新覆盖而不无限追加。要求一次模型 AIMessage **最多一个 write_todos ToolCall**；如同批重复写计划，全部该批 `write_todos` 应返回稳定 `ERROR[TODO_CONFLICT]`，不允许两个并行 Command 修改同一个父 State Channel；必要时用检测工具调用批次、Run 层互斥 + 明确冲突拒绝，而非误用 append reducer。具体以已锁版本 `AgentState/ToolRuntime/Command` 实测，若无法安全把 Todo 写入 Checkpoint，停止，不退化为只有前端的假 Todo。

#### 3. Run/Task 边界与持久化合同

**存储**沿用 `backend/data/runtime.sqlite3`，`RuntimeDatabase.init_schema()` 只追加两个表/索引（兼容已有 P03 DB）：
- `run_todos(run_id TEXT REFERENCES runs(id),todo_id TEXT,title TEXT,status TEXT,position INTEGER,updated_at TEXT,PRIMARY KEY(run_id,todo_id))`，含 run 内唯一 position 和 status CHECK。完整快照提交为单个 SQLite 事务；按 position 排序；Run 新一轮状态从空开始，记录只归当次 Run。
- `subtasks(id TEXT PRIMARY KEY,run_id TEXT REFERENCES runs(id),thread_id TEXT REFERENCES threads(id),agent_type TEXT,description TEXT,todo_id TEXT NULL,status TEXT,result_summary TEXT NULL,error_code TEXT NULL,source_file_ids_json TEXT NOT NULL DEFAULT '[]',created_at TEXT,started_at TEXT NULL,finished_at TEXT NULL)`，索引 `(run_id,created_at,id)`；同一事务验证父 Run 属于 Thread 且处于 RUNNING；可选 `todo_id` 必须属于此 Run 的计划。子任务自身 ID 由服务端 UUID 创建，不复用 Graph ToolCall ID；`tool_call_id` 只做消息回执匹配。描述限制 1–1000 字、摘要上限 1600 字、source IDs 仅来源于真实允许的工具回执而非模型报告中随意写的 UUID。
- Task 状态：`PENDING → RUNNING → COMPLETED/FAILED/TIMED_OUT/CANCELLED`，或未启动时 `PENDING → FAILED`；终态不可逆，统一对外大写；服务启动时遗留 `PENDING/RUNNING` 标记 `FAILED/SUBTASK_INTERRUPTED`，不主动重试、不断言已经完成。后端退出主动取消时 `CANCELLED`；执行超时 `TIMED_OUT`。不存在 Task 独立于父 Run 永久后台执行的模式。

**Task Registry**：`runtime/task_registry.py` 只保存活动 Run 的限额信号量/Task 强引用/防重复计数；**权威历史 Task 结果写 SQLite**。每个父 Run 最大**4 次**委派（包含失败/超时，不允许无限重试），同时最多 **3 个**子代理执行；父 `RunService` 同时最多 2 个 Run，所以系统最多 6 个并发子代理（全局上限以运行中 parent Run 数自然推导，工具线程没有另建无限后台任务）。第 5 次 `task` 返回 `ERROR[SUBTASK_LIMIT]` 而不启动模型；并发执行使用 per-run `asyncio.Semaphore(3)`，保证取消时释放；每个被批准调用分配 Task ID、持久登记并发送 `subtask_created`，进入真正 child `ainvoke` 前更新 RUNNING 并发 `subtask_started`。

**生命周期与超时**：每个 child 最多 6 次模型/工具循环的等价图步预算（按本地锁版实测 `recursion_limit` 的“图节点步数”，不可误把 graph recursion_limit=6 当 6 次模型调用）；默认 `subagent_recursion_limit=14`、`subagent_timeout_seconds=35`、`max_subagent_concurrency=3`、`max_subagent_calls_per_run=4`。父持久 Run 全程默认 `run_timeout_seconds=150`（P02 之前 45 秒不足以连续执行多个子代理；P01 独立 Agent 仍保留原 45 秒设置）；**父 Graph 单独使用 `recursion_limit=36`**，否则旧 P02 的 12 步可能在 Todo+多轮 task/write_text 时提前终止；这表示 LangGraph 图节点步数上限，**不是 36 次模型调用**。子代理 `recursion_limit=14` 与它独立，任务次数仍由 TaskRegistry 设上限。前端 P02 轮询 180 秒上限可覆盖父 Run；若要进一步提高配额必须先更新合同和 UI 超时。任何取消应先取消/回收 child 后再终结父 Run，避免子代理晚到并继续使用已关闭的 Workspace/DB。子代理模型错误/超时被映射为脱敏安全错误，并生成真实 ToolMessage `ERROR[SUBTASK_...]`，父 Agent 可据此解释部分失败；**不因为子任务失败就伪造“全部完成”**。Run 整体成功与否仍由 P02 真实 Graph 最终答复校验决定，Task 状态不能由父模型措辞倒推出 COMPLETED。

**Child 隔离**：在 `agents/subagents/executor.py` 对每次 `task` 调用创建独立 `create_agent(model,allowed_tools,checkpointer=None,context_schema=ChildContext,system_prompt=角色Prompt)`，以只包含该子任务目标及必要的当前 Thread 文件 ID/受控摘要的 HumanMessage 启动；不传父消息列表、父 Thread Checkpointer、父全部上下文、父图 `configurable.thread_id`，不额外创建 SQLite child Checkpointer 或 child Thread。子模型不再调用 task，从而 **MAX_DELEGATION_DEPTH=1**。必要时传“用户已上传文件列表的已登记元信息”，仍先校验作用域，不主动把所有文件正文加载到 Prompt。子 Agent 的 `read_text` 直接沿用 P03 的归属验证。

**子任务结果**：`TaskResult(task_id,status,summary,error_code,source_file_ids)`；正常结束必须验证子图最后一条有效 AIMessage 与工具回执，摘要最多 1600 字，对模型过长/不可信结果保守裁剪并显式 `truncated` 标志；引用的 `file_id` 只能取 child 真实成功 `read_text` 调用的 ID 并做 Thread 校验，不能相信模型最后自然语言里声称的路径/URL。Task 工具仅返回此简要 JSON（或 `ERROR[CODE]`）给父 Agent，不向父 Graph 写子模型的完整消息、Token 或隐藏推理。

#### 4. SSE / HTTP / Web 合同

**增加事件类型**，沿用 P02 `EventBus.publish(run_id,kind,payload)`、相同 `run_id:sequence`/512 缓冲/订阅 gap/10 分钟结束保留/终态先 DB 后 SSE：
- `todo_updated`：`{run_id,todos:[{todo_id,title,status,position}],revision}`；仅 SQLite 快照成功提交才发，发送失败不能谎称持久化失败；前端历史以 GET 结果为准。
- `subtask_created`：`{task_id,agent_type,description,todo_id?,status:"PENDING"}`。
- `subtask_started`：`{task_id,agent_type,status:"RUNNING"}`。
- `subtask_completed`：`{task_id,status:"COMPLETED",summary,source_file_ids}`。
- `subtask_failed`：`{task_id,status:"FAILED"|"TIMED_OUT"|"CANCELLED",error_code}`。
- 事件没有要暴露的子模型完整提示词、Prompt、隐藏推理或文件正文；说明所有任务相关事件为**该父 Run** 的事件，不产生虚假的独立 P02 Run。

**新增只读 HTTP**，避免刷新后消失的内存 Task：
| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/runs/{run_id}/todos` | 200 `TodoItem[]`，无计划为 `[]`；未知 Run 404 |
| GET | `/api/runs/{run_id}/subtasks` | 200 `TaskRecord[]`，稳定创建时间排序；未知 Run 404 |

不提供由前端写 Todo/手工触发 Sub-Agent 的公共 API（P04 只能由可信父 Run 内 Tool Calling 发起）。运行中 SSE 快照来自服务器；断线/重连/刷新时 **GET Todos/Subtasks** 做权威补齐，事件可能已过期也不影响已登记记录查询。原 P01/P02/P03 HTTP、SSE 的 `assistant_delta/tool_start/tool_end/assistant_final/run_end`、工具轨迹与 Artifact 下载协议不变。对于内存事件缓冲满时出现 `stream_gap`，前端停下增量拼接，重新取 Run/Todo/Task 三个端点。

**前端**增加两个只读面板，绑定当前活动/历史 Run，尽量不增加新 UI 框架：
- `TodoPanel.tsx` 显示结构化顺序、状态、时间；同 ID 更新覆盖，不从助手自然语言识别状态；无计划显示“本次未使用计划”而非错误。
- `TaskPanel.tsx` 显示真实子任务角色、标题/描述、当前状态、简短结果、明确失败/超时；role 标签的 research 需要注明“仅已上传材料”；不会伪造模型内部步骤或子 Agent 文字流。
- `ChatPanel/RunStatus` 将 Run 详情与 Todo/Task 面板关联：实时 SSE 先更新本地视图，`run_end`/刷新/切换会话时使用 GET 权威覆盖；已经执行但 SSE 过期的历史 Run 也要看到真实 Todo/Task；保持现有 P03 FilesPanel 完整可用、Run 终态文件列表照旧刷新。
- `frontend/src/api/runtime.ts` 增加 DTO 和 GET API；`subscribeRunEvents` 显式注册 5 个新自定义事件（浏览器 EventSource 不能只用 onmessage），继续校验 run_id/thread_id/递增事件 ID，按已有缺口回退机制处理。

#### 5. 文件分工（Codex 不重新划分架构）

| 新增/修改路径 | 具体责任 |
|---|---|
| `backend/src/minideerflow/agents/state.py` | `TodoItem/P04AgentState`，AgentState 扩展/状态替换规则；工具 State Command 不做 append |
| `backend/src/minideerflow/agents/lead.py` | 可选 `state_schema`、P04 专属追加 system prompt；P01 单轮与 P02/P03 legacy 工具不变 |
| `backend/src/minideerflow/runtime/models.py` | `TodoItem/TaskRecord/TaskResult/TaskStatus` 可放独立 `agents/state.py` + `subagents/models.py`，但 DTO 只能定义一处并从全项目复用；RunEvent 结构向后兼容 |
| `backend/src/minideerflow/runtime/db.py` | 追加 `run_todos/subtasks` 表、索引和约束，无破坏式改造 |
| `backend/src/minideerflow/runtime/plan_repository.py` | 同一 RuntimeDatabase 原子 Todo 快照与 Task 创建/状态转换/列表，Run/Thread 真正归属验证、启动孤儿核查 |
| `backend/src/minideerflow/runtime/task_registry.py` | 每父 Run 3 并发/4 总次数、Semaphore/受管理 Task、timeout/cancel/shutdown，不替代 SQL 历史 |
| `backend/src/minideerflow/agents/context.py` | 冻结 dataclass `AgentRunContext(WorkspaceContext)` / `ChildContext(WorkspaceContext)`、可信依赖注入；确保 P03 tools 仍通过校验 |
| `backend/src/minideerflow/tools/todo_tool.py` | `write_todos(items,ToolRuntime[AgentRunContext,P04AgentState])->Command`，有效状态快照+真实 ToolMessage、SSE；拒绝多写并行冲突 |
| `backend/src/minideerflow/agents/subagents/config.py` | `general/research` 固定 Spec（system_prompt/tools/timeout/recursion），文档对 research 不夸大联网 |
| `backend/src/minideerflow/agents/subagents/executor.py` | 构建独立 child Agent、状态与 ToolMessage 校验、结果脱敏/长度限制/来源 ID、取消回收；不复用父 Saver |
| `backend/src/minideerflow/agents/subagents/dispatcher.py` | role+父授权交集、TaskRegistry 限额/数据库状态/SSE、同步等待结果，不创建独立 P02 Run |
| `backend/src/minideerflow/tools/task_tool.py` | `task(agent_type,description,todo_id?,runtime)`；模型 Schema 只包含公开参数，可信 Runtime 注入，不允许子代理再 task |
| `backend/src/minideerflow/runtime/runner.py` | 装配 P04 AgentRunContext、注入 todo/task tools、增父 Run 超时/终结和 Task 清理时序；沿用 P03 Workspace |
| `backend/src/minideerflow/runtime/streaming.py` | 支持本轮输入初始化 `todos=[]`，现有消息 ID 去重和 SSE 工具轨迹仍正确；不将 Task 结果当新的助手消息 |
| `backend/src/minideerflow/main.py` / `config.py` | 初始化并挂载 PlanRepository/TaskRegistry，启动孤儿标记、关闭任务先于 RunService/SQLite（依赖栈顺序要核对），配置上下界；注册只读 API |
| `backend/src/minideerflow/api/tasks.py` | 两个 GET 端点+统一 404/脱敏错误；不暴露写 API |
| `frontend/src/api/runtime.ts` | Todo/Task DTO + GET + 新 SSE 事件类型 |
| `frontend/src/components/TodoPanel.tsx` / `TaskPanel.tsx` | 两类真实实体的实时/历史只读面板 |
| `frontend/src/components/ChatPanel.tsx` / `RunStatus.tsx` / `App.tsx` / `styles.css` | 在当前 Run 和历史列表展示 Todo/Task、SSE、失败/刷新；P03 上传/下载和 P01 调试区原样保留 |
| `backend/tests/test_todos.py` / `test_subagents.py` / `test_task_registry.py` / `test_tasks_api.py` | 真 ToolRuntime + 假模型 + 临时 SQLite、状态/权限/并发/取消/重启 |
| 必要时 `backend/tests/test_runner.py` / `test_runs_api.py` / `test_file_tools.py` / `test_events.py` | P04 接入直接触及的旧能力，严格局部补测 |
| `README.md` / `docs/progress/P04.md` / `docs/tasks/P04-ABCD.md` | 分 A/B/C/D 记录真实接口、运行命令、前端功能、Git SHA、Fake/真模型及未测项 |

#### 6. 子任务执行 / 检测标准

**P04-A · Todo/GraphState/持久化/初版 UI**
1. 核对 P03 实际代码和本地锁版本；先用最小 ToolRuntime + `Command` + `create_agent(state_schema=...)` + SQLite Saver 假模型验证可用，再修改正式 Graph。
2. 实现 State/DTO、`run_todos`/PlanRepository、`write_todos`、RunContext、Run Service 仅接入 Todo、GET todos；前端 TodoPanel 显示当前和历史 Run。**不提前暴露 task 工具**。
3. 测同 ID 更新不重复、状态不能回退、最多 8、重复调用冲突、真实 Checkpointer `todos`、下个 Run 重置 Todo、无 Todo 普通问答、独立 Thread 隔离、返回 ToolMessage 关联 ID、SSE 和刷新历史。P01/P02/P03 直接消费者的局部测试 + Ruff/前端 build；完成 A 提交 SHA。

**P04-B · 单个真实 Sub-Agent/可信工具边界**
1. 固定两个角色的允许工具清单；实现 `AgentRunContext`、`ChildContext`、executor+dispatcher+task_tool，先单次/串行调用；子 Agent 的 `create_agent` 无父 Checkpointer、只有新 HumanMessage，真实 Tool Calling 读当前 Thread 文件。
2. RunService 为持久 Run 注册 task，PlanRepository 记录 Task；GET subtasks，前端 TaskPanel 查看真实结果，P03 FilesPanel/旧 API 均可用。
3. 测父 child 模型消息隔离、不可用工具不出 schema、research 无联网、跨 Thread/伪造 Context 拒绝、结果长度/来源 ID 校验、P01 独立 Agent 未增加 task、工具 ID 正确；提交 B SHA。

**P04-C · 有界并发/失败/超时/事件**
1. `TaskRegistry` 加 per Run Semaphore(3) + 4 次预算 + 35s child timeout、Task 强引用/清理；多个 task tool_calls 同一父模型步骤可以并行，**同批 write_todos 依旧拒绝冲突**。增加 5 种 SSE 事件和 HTTP 权威历史补齐，父 Run 的最终事件必须在 child 全部收尾后发布。
2. 测峰值最大 3、4 次预算、第 5 次拒绝、超时/取消/异常/重试不假成功、父 Run 超时等待所有子代理回收、单 Run 多子任务 ToolMessage ID 正确、SSE 断线不取消、重启 orphan Task 变 FAILED/SUBTASK_INTERRUPTED。前端实时 Todo/Task 不串 Run/Thread，事件缺口使用 GET；提交 C SHA。

**P04-D · 联调、中文注释与 Demo 交付**
1. Fake 模型端到端实际完成：上传样例 → `write_todos` → `task(general/research)` → child `read_text` → Lead 汇总并 `write_text(summary.md)` → 真实可下载 Artifact；前端显示状态变化、重启历史、会话隔离；简单请求无强制规划。
2. 真实模型可用时另测普通和复杂任务（不泄露 key / 不上传私人资料）；本阶段不具备网页搜索，research 只分析已有材料；未按预期调用 task 的场景记录实际失败而非伪造通过。
3. 只执行 P04 新增/修改及直接调用方 pytest、Ruff、TypeScript build、无 Key 的 HTTP/Fake 浏览器 Smoke；真实模型和假模型测试分开记录，前端同步；提交 D SHA、更新 README/进度。结束时整体 `PENDING_REVIEW` 等用户手动 Demo；不提前开始 P05，不自动合并 main。

**固定验收**：同一 Thread 不同 Run 的历史 Todo/Task 正确；状态只能由工具/Registry/SQL 更新，模型文字不能伪造成功；child 只看显式委派目标与允许文件，不继承父全部对话/父 Saver；一般和 research Tool 不越权且无任何嵌套 task；每父 Run 不超过 3 并发/4 次调用，超时取消后不留跑飞任务；工具轨迹和 SSE run_end 按实际业务状态；P01/P02/P03 保留；所有关键逻辑遵循中文注释及长逻辑 1/2/3 分段。

**参考资料**：DeerFlow v2.0.0 的 `backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py`、`tools/builtins/task_tool.py`、`subagents/executor.py`（参考职责，不复制庞大 TaskPool/隔离线程）；官方 [LangChain 自定义 AgentState](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[ToolRuntime 与 Command 更新状态](https://docs.langchain.com/oss/python/langchain/tools)、[Sub-Agent 工具委派和隔离](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents)。**工具签名须以本项目实际锁定版本为准**，不得直接照搬未来版本，必要时写最小假模型兼容测试。

**停止条件**：若 `ToolRuntime + Command`/自定义 `AgentState` 无法在锁定版本安全工作、并发写 State 存在隐性竞态、子代理越权/复用父 Saver、执行取消仍留下活跃 child、关键安全测试失败，Codex 停在最近可验证提交并上报复现证据；不得为了 Demo 放宽范围。阶段与 git 进度必须如实记录，不写假测试数字、不改 P02/P03 待验收状态。


### P05 — ToolRegistry / 受控 MCP / 按需 Skills（2026-11-06 正式详细设计）

> **状态：PLAN_READY（只有方案和 GitHub 任务合同；P05 代码尚未开发、没有 P05 测试结果）**。用户于 2026-11-06 要求“设计 p5”，不等于此前 P02/P03/P04 手动验收通过，也不代表已运行 Codex。分支 `feat/p05-tools-mcp-skills` **从已有 P04 A/B/C/D 完整代码的** `feat/p04-planning-subagents` 派生。独立 [P05-A/B/C/D 逐文件执行合同](tasks/P05-ABCD.md) 是交付 Codex 的唯一执行清单；严格 A→B→C→D，各自局部测试、前端同步、单独提交，关键失败停止，不进入 P06。

#### 1. 用户业务与核心边界

本阶段的业务闭环是：用户向已有 Thread 提交任务 → Lead 的原有 `create_agent` 自动选择已授权工具 → `ToolRegistry` 为当前 Run 组装**内置工具 + 用户事先批准的 MCP 工具 + Skill 元工具** → LangChain 官方工具执行路径由 `ToolGuardMiddleware` 校验权限/参数/超时，正常工具按原方式返回 `ToolMessage` 或 `Command` → `list_skills/read_skill` 按需读本地 SKILL.md，仅作为模型可见的说明文本而不是提升权限 → P04 Todo/Task/Run/SSE、P03 Artifact 保持可用。

**P05 不做**：让模型选择/安装任意 MCP Server；外网任意 MCP URL、任意 stdio shell/command、OAuth/token 管理、用户网页登录、通用远程搜索/抓取（留给 P07）、Skill 在线市场/安装/自动执行代码、MCP resources/prompts/sampling/elicitation、动态每请求权限审批、通用消息队列或自研 Agent 工具循环、P06 上下文压缩。研究方向仍然没有联网检索。**只在明确配置/批准后接入本机回环、只读 Streamable HTTP MCP。**

**概念边界**：
- Tool：一个真实可调用的 LangChain `BaseTool`，通过框架 `create_agent` 的现有 ToolNode 运行。
- MCP：Tool 的一种**外部来源**。批准某个 MCP Server 的工具并不表示其真实无副作用；当前只连接自己事先启动、可信且功能无副作用的本地示例服务。
- Skill：受控本地 SKILL.md 的元信息与执行说明，不能自行调用工具、改变 Agent 系统提示词、扩展工具白名单或修改文件；本期通过 `list_skills/read_skill` 工具让模型按需阅读。
- 统一执行：**不重写 LangGraph/ToolNode 主循环**；用官方 `AgentMiddleware.awrap_tool_call` 做前置 Policy 和错误边界。框架自己完成参数注入、ToolCall/ToolMessage/Command 的对应；Middleware 绝不双重执行 handler。

**可验收 Demo**：启动仓库内只读 MCP 示例服务，配置批准它的 `lookup_fact` → 页面“可用工具”出现 `mcp_demo_lookup_fact` → 新建 Thread 提问固定事实或本地资料 → 真实 Run 的 Tool Trace 记录 `mcp_demo_lookup_fact` 的调用与回执；再让 Lead `list_skills/read_skill("file-analysis")` 加载指南，照指南用 P03 的 `list_files/read_text/write_text` 生成 summary.md（只在用户要求生成文件时） → 页面能下载产物。将 MCP Server 关闭后，内置计算/文件/Task 不受影响；重新启动应用可发现其恢复。模型是否主动选工具不确定，必须同时有 Fake 的确定性调用测试和真实模型单独 Smoke，不能编造结果。

#### 2. 真实代码接入点与技术选型

P04 实际源码：`agents/lead.py:build_lead_agent(model, tools, checkpointer, context_schema, state_schema, prompt_suffix)`；`runtime/runner.py:RunService._execute_run` 直接创建 `tools=[calculate,list_files,read_text,write_text,write_todos,task]`，将 `AgentRunContext` 注入图；`agents/subagents/dispatcher.py` 严格注册子 Agent 的三个只读工具且取父 Context 的 `allowed_tools` 交集；`tools/todo_tool.py` 返回带 `ToolMessage` 的 `Command`，`tools/task_tool.py` 同步委派；`runtime/streaming.py` 处理真实 `AIMessage/ToolMessage` 与 SSE；`frontend/src/RunStatus/ChatPanel` 显示每次真实工具调用。**必须复用这些入口**，不另开执行器或重复流式桥接。

依赖方案：新增 `langchain-mcp-adapters`、MCP Python SDK（`mcp` 以直接依赖或锁定的子依赖出现，排除已知不安全旧版本）、`PyYAML`，仅这三类；采用`uv add`、`uv lock --check` 和本地签名兼容样例确认锁定版本，避免无关升级。MCP 客户端采用 `MultiServerMCPClient`、`get_tools(server_name=...)` 和 `tool_name_prefix` 相关能力，但**别同时套用新版 LangChain 内置 MCPAdapter 的不同 API**；以本项目最终锁版确切签名/返回 ToolMessage 格式为准。HTTP transport 只接受本机 `127.0.0.1` 的 `streamable_http`（适配器实际连接字面量可能叫 `streamable_http` 或 `http`，须实测映射），不使用历史 SSE transport。前置校验 SSRF/URL/重定向，信任边界不因只读工具自动消失。

#### 3. ToolRegistry、Policy、Middleware 的一致合同

新增 `tools/registry.py`：
- `ToolDefinition(name,tool,source,permission,timeout_seconds,origin,description)`，`source="builtin"|"mcp"|"skill"`；`permission="read"|"write"|"orchestrate"`，**Tool 名全局唯一**，重复包含内置名/别名都拒绝 `TOOL_DUPLICATE`，不覆盖已有工具。Registry 在应用 lifespan 构建并固定**快照**，不让模型运行时动态登记。注册的实际 LangChain `BaseTool` 是单一工具事实源，不自写与现有 Tool JSON Schema 不一致的镜像。
- `register(def)`、`get(name)`、`list_allowed(policy)`、`list_catalog()`；`list_allowed` 只返回获得许可的工具对象给 `create_agent`，同时在 Middleware 再次验证。允许空 MCP 清单，**内置工具一直可用**。
- 父工具合同照旧：`calculate/read_text/list_files/write_text/write_todos/task`；若 P04 Context 未提供则仅原 P01 demo 的 calculate；子 Agent 本期**不增加 MCP 或 Skills**，仍只保留 P04 `general:calculate/list_files/read_text` 和 `research:list_files/read_text`，保持 P04 research“仅已有材料”的含义。未来变更子 Agent 可用外部工具必须另行设计/审批。
- `ToolPolicy` 由可信 `AgentRunContext` 和角色创建，含 `allowed_names`、`allowed_permissions`、`run_id/thread_id`；默认 DENY，不根据模型输出、Skill 文本或 MCP 描述自动开放。Lead 默认沿用 P04 六个原有工具 + `list_skills/read_skill`，MCP 仅加入明确批准的工具；P04 `context.allowed_tools` 必须同步当前 Run 快照，让 Dispatcher 的父权限交集不退化。

新增 `tools/executor.py`：
- 类 `ToolGuardMiddleware`，使用实际已锁版 `AgentMiddleware.awrap_tool_call(request,handler)`，先取得 request.tool_call 的 name/id/args 和**服务端 Context**，校验 Registry 真实 name、Run 所属、当前 Policy 允许、`read/write/orchestrate`、参量类型/大小与工具的官方 `args_schema`，再 `await asyncio.wait_for(handler(request), timeout=definition.timeout_seconds)`。对已知失败返回**带相同 tool_call_id、status="error" 的 ToolMessage**，消息为 `ERROR[CODE]:...`；绝不假装 success。不可捕获/吞掉 `CancelledError`，不因为超时自动重复调用有副作用工具。
- **保留框架类型**：正常执行返回原 `ToolMessage` 或 `Command`，尤其 `write_todos` 的 Command.update 必须原样送到 Graph，否则会破坏 P04 State 和 Checkpointer。原有 P03 `read_text` 允许完整 64KiB，**不能用统一 8KiB 限制将其静默截断**；对 MCP 输入 JSON 最多 2KiB、MCP 输出最多 8KiB，超出返回有明确错误码/截断标志，不泄露敏感字段。既有内置工具合法返回不更改 ToolMessage ID 和 ToolTrace 成功判定。
- 对 ToolError/SchemaError/Timeout/连接失败映射稳定安全代码 `TOOL_NOT_ALLOWED`、`TOOL_INVALID_ARGS`、`TOOL_TIMEOUT`、`MCP_UNAVAILABLE`、`MCP_TOOL_ERROR`、`TOOL_EXECUTION_FAILED`；不能把原始 MCP exception/header/环境变量/路径塞入 model-visible 或日志。已执行写操作的 timeout **结果未知不自动重试**，保持已有 P02 Graph/Run 保守恢复语义。不能为了 Middleware 的易实现性另造一套 while(tool call) loop。
- **安全性/兼容性前置必测**：真实 LangChain ToolRuntime 身份注入、P04 `write_todos` 的 `Command` 状态更新与 matching ToolMessage、`task` 并行与取消、P03 `write_text` 的文件实际下载、模型错误 ToolTrace 均正常。Middleware 返回 `ToolMessage` 的 `tool_call_id` 一定匹配当前调用。若所锁版本与官方 Middleware 形状不兼容，**停止报告实际版本/最小复现，不退化为自行实现 ToolNode**。

#### 4. 只读本地 MCP（不是凭“readOnlyHint”当授权）

新增 `core/mcp_settings.py` 与版本管理的 `backend/config/mcp_servers.example.json`：
- `MCP_CONFIG_PATH` **默认空，P05 默认不连接任何外部 Server**；用户明确配置到本机 JSON 时读取，文件不能被前端 API/模型修改，文件不得含凭据/token，根目录 `.env.example` 仅追加注释/示例配置项。
- 配置最多 2 个 Server，每个 `server_id` 正则 `[a-z][a-z0-9_]{0,31}`，URL 只接受 `http://127.0.0.1:<1..65535>/mcp` 的显式数字端口，禁止 localhost/DNS、IPv6 特殊写法、userinfo、query/fragment、任何其它地址、跳转；入口不支持 stdio command 或内网其它 IP。可用配置示例 `{"servers":[{"id":"demo","transport":"streamable_http","url":"http://127.0.0.1:8765/mcp","tools":[{"name":"lookup_fact","schema_sha256":"<reviewed pin>"}]}]}`；最多每 Server 4 个工具，工具名和 schema digest 在服务端启动时严格匹配用户批准值，变化需人工重新审核配置，不能自动接受。
- Registry 别名统一 `mcp_<server_id>_<tool_name>`，须符合模型工具命名约束；将适配器返回工具做**浅克隆/受控别名**，不手写损坏参数 Schema 的代理；MCP 原真实工具名仍由 adapter 的 coroutine 绑定。工具元数据的 `readOnlyHint`/自然语言描述**不能决定权限**；只有 config 明确批准 + Schema 摘要匹配 + 本地可信 Server 的工具才获得 `read`。未知/未批准、写型/任意本地文件/Shell 工具一律不注册。
- `mcp_adapter.py`：先按 Server 独立 `get_tools`，确认响应 JSON Schema/名称/描述/注解的规范化 SHA256（批准项 hash；不要纳入不稳定对象 repr），拒绝重复/非法名/变更；单个 Server 不可用则记录 `MCP_UNAVAILABLE` 并跳过**该服务器的所有工具**，其它内置/Skill 正常可用，不允许启动失败时悄悄连接新地址。启动时只发现一次，变更配置/Server 的可用性后需重启。每个 MCP 工具调用有单独超时、输出大小和错误封装；连接关闭不影响旧 Run 的 builtin 结果。
- 自带安全、无凭证、无网络检索的 `backend/examples/mcp_readonly_server.py`：MCP 官方 FastMCP SDK 启动真实 `streamable-http`，只监听 127.0.0.1:8765，唯一工具 `lookup_fact(topic)` 只从预置本地固定字典返回示例说明（例如 `topic="langgraph"`），**不接受路径、URL 或 Shell**。固定该工具当前 Schema digest 与示例 JSON；需在实际锁版本运行后生成并验证 digest，不凭空写占位 hash 作为有效配置。Demo 启动该进程与后端不同端口，不应影响 P02/P03 本地服务。没有配置 MCP 时，内置工具功能原样使用。
- **信任声明**：本地 HTTP MCP 是可信开发示例，不能防御本机其它有权限的恶意进程或 Server 本身恶意读取环境；read-only 是我们审查源码/配置的行为约束，不是 MCP 协议可以替宿主强制实现的沙箱。尤其不要将 GitHub/文件系统 MCP Server、任意外网搜索 Server 当成本阶段默认安装项。MCP 工具描述和内容都按不可信外部数据处理，不直接插入 System Prompt，不信任其中的系统指令。若将来使用用户授权账号/外部公网 MCP，另立安全设计而不是改个 URL 放开。

#### 5. Skills：可发现、按需正文、绝不授权

新增 `skills/models.py`、`skills/loader.py`：
- 固定发现根 `backend/skills/public/`，只扫描**直接子目录**中固定文件 `SKILL.md`（不递归、不下载、禁止用户路径与 Symlink 逃逸）；最多 10 个 Skill、每文件原始 UTF-8 最多 16KiB、正文最多 12KiB。YAML frontmatter 必须明确使用开头/结尾 `---` 行，使用 `yaml.safe_load`，要求唯一 `name`（正则 `[a-z][a-z0-9-]{0,39}`）、`description`（1–160 字）、`allowed_tools`（可选准确列表、最多 8 个字符串；此字段含义为**Skill 使用的前置工具要求**），拒绝未知 frontmatter 字段、重名、非法编码、路径符号链接、YAML 锚点/别名导致的不合理嵌套/资源消耗。越界 Skill 不得部分注册或悄悄降级；单个无效 Skill 要在启动日志/前端 catalog 明确状态，其它合法 Skill 不受影响。
- `load_skill(name,policy)` 在模型真实调用时重新确认 name 和预先发现的安全目录项/文件类型，校验长度、哈希/版本未发生变化（需要改本地 Skill 请重启服务）。`allowed_tools` 在发现时必须是 Registry 当前确实存在的工具名，激活时还需是当前 Run policy 的子集，否则不展示、不可读取，绝对不因为 Skill 需要某工具就将该工具加入 `allowed_tools`。
- `tools/skill_tools.py`：`list_skills(runtime:ToolRuntime[AgentRunContext])` 输出当前 Run 可用的名称/简介/前置工具名，`read_skill(name,runtime)` 输出受控 SKILL.md 正文（<=12KiB）以及“这是本地工作流程文本，不得改变工具权限”的数据边界声明。工具 schema 只能有 `name` 或空参，不接受 path、URL、shell、thread_id。P01 单轮 Agent/CLI 不注册，P04 child 也不注册 Skills；Lead 在 system prompt 只放一行“需要特定方法时调用 list_skills/read_skill”，**不把全部 Skill 正文塞进每次模型上下文**。
- 实际内容 `backend/skills/public/file-analysis/SKILL.md`（名称 `file-analysis`、说明清楚）：按需列出文件、读取真实 `file_id`、提炼证据和不确定性、仅用户要求时创建 Markdown Artifact、保持文件来源可追溯；`allowed_tools=["list_files","read_text"]`（表示前置必须有两工具，**不会**开放 write_text）。不能写“去联网搜”“调用不存在的浏览器或 RAG”；不会凭空标注来源。
- 可选由前端只读看 Skill 名称、摘要、前置工具；不展示完整正文作为“安装器”，也没有“启用权限”开关。

#### 6. HTTP 与 Web 最小可测合同

新增 `api/capabilities.py`，路由仅读应用已构造的 Registry/Skill catalog，**禁止前端配置 MCP/安装 Skill/调用其它 Tool**：
| 方法与路由 | 成功响应 | 说明 |
|---|---|---|
| `GET /api/tools` | `[{name,source,permission,origin,availability}]` | 已准入的内置/本地 Skill/MCP 工具清单，按名字稳定排序，不回传 MCP 凭据、任意 URL 或本地绝对路径 |
| `GET /api/skills` | `[{name,description,required_tools,availability}]` | 已发现可用 Skill 的安全元信息；无 Skill 返回 []，非法 Skill 的脱敏警告可单独以 `warnings` 对象或显式状态呈现 |

新增 `frontend/src/api/capabilities.ts`、`frontend/src/components/CapabilityPanel.tsx`：现有极简 Web 中显示真实可用工具的来源/读写能力、Skill 名称及限制、MCP 未启用/连接失败提示，提供**刷新列表按钮**（只重新 GET，MCP 服务器发现仍需重启后端）；后续 A/B/C 每项完成都能在这个面板独立验证对应功能。没有新图表/页面/大组件库。P02/P03/P04 的会话/Todo/Task/SSE/Artifact 路径保持；真实调用详情已在 RunStatus tool trace 中显示，无需复制另一套日志系统。

#### 7. 文件职责与实施顺序（Codex 精确编码）

| 文件 | 必须实现的职责 |
|---|---|
| `backend/pyproject.toml` / `uv.lock` | B/C 新增并锁定 MCP Adapters、MCP SDK、PyYAML，检查 MCP SDK 安全修复版本；其它依赖不无关升级 |
| `backend/src/minideerflow/tools/registry.py` | ToolDefinition/ToolPolicy/ToolRegistry，重复拒绝、权限/来源/有界超时、内置注册函数 |
| `backend/src/minideerflow/tools/executor.py` | 官方 `awrap_tool_call` Middleware：身份+白名单+schema+时限+安全 ToolMessage；Command passthrough/取消保留 |
| `backend/src/minideerflow/core/mcp_settings.py` | Pydantic 解析 JSON/本机 URL/Server ID/tool 白名单+schema pin、默认无连接 |
| `backend/src/minideerflow/tools/mcp_adapter.py` | 受控 MultiServerMCPClient、元数据 pin、异常/超时、MCP Tool 别名/ToolDefinition |
| `backend/examples/mcp_readonly_server.py`、`backend/config/mcp_servers.example.json` | 真 Streamable HTTP + lookup_fact 确定性例子及经实际 SDK 计算过的 schema pin |
| `backend/src/minideerflow/skills/models.py` / `skills/loader.py` | SkillMeta、发现、安全读取、完整 UTF-8/Frontmatter/schema、catalog 与按需正文 |
| `backend/src/minideerflow/tools/skill_tools.py` | `list_skills/read_skill`，ToolRuntime 可信权限，不接受路径 |
| `backend/skills/public/file-analysis/SKILL.md` | 真正可用于上传文件归纳的本地样例 Skill |
| `backend/src/minideerflow/agents/lead.py` | 可选 Middleware 参数传入 `create_agent(middleware=...)`，原 P01 直接调用仍兼容 |
| `backend/src/minideerflow/agents/context.py` | 在 AgentRunContext 增可选/冻结的 Registry/Policy/Skill 依赖，不改 P03 WorkspaceContext 与 ChildContext 继承契约 |
| `backend/src/minideerflow/runtime/runner.py` | 从 Registry 快照构建 Lead 工具列表、Policy、Middleware、Run Context；保持 P04 Todo/Task 和 P03 Context，P01 不自动开放 |
| `backend/src/minideerflow/agents/subagents/dispatcher.py` | 仅核对父 allowed_tools 仍为当前 Registry 快照；**不加 MCP/Skills 到 child** |
| `backend/src/minideerflow/main.py` / `config.py` / `.env.example` | lifespan 组装 Registry/Skills/MCP（连接失败只降级 MCP）、GET Catalog 服务、AsyncExitStack 清理；MCP 未启用不增加额外进程 |
| `backend/src/minideerflow/api/capabilities.py` | GET /api/tools 与 /api/skills，返回脱敏 DTO |
| `frontend/src/api/capabilities.ts` / `components/CapabilityPanel.tsx` / `App.tsx` / `styles.css` | 展示真实工具/Skill/MCP 在线状态及刷新；不做虚构执行按钮 |
| `backend/tests/test_tool_registry.py` / `test_tool_guard.py` | 真实 ToolNode+Command+工具注入、重复/权限/参数/超时/ID、P04/P03兼容 |
| `backend/tests/test_mcp.py` / `test_skills.py` / `test_capabilities_api.py` | 真实本机 MCP 进程/协议（不依赖外网/密钥）、pin/失败降级、YAML/路径安全/权限、HTTP Catalog |
| `backend/tests/test_runner.py` / `test_file_tools.py` / `test_todos.py` / `test_subagents.py` / `test_planning_demo.py` | 因 P05 接线直接受影响才补测，尽量不执行无关整仓测试 |
| `README.md` / `docs/progress/P05.md` / `docs/tasks/P05-ABCD.md` / `docs/ARCHITECTURE.md` | 记录 A–D 各自实际 SHA、局部命令/结果、Web 可见状态、MCP 本地启动步骤、安全边界与未测项 |

#### 8. 子任务划分与验收

**P05-A · 统一 Registry/Policy 与 ToolGuard，不引入 MCP 依赖**：注册所有旧内置工具；Lead 从 Registry 取允许工具，Middleware 真拦截 + ToolRuntime 不丢失。含 GET /api/tools、CapabilityPanel 真实 builtin 目录，MCP/Skills 显示“未启用”而不是假结果。Fake 工具测试：`write_todos` Command/SQL+Graph、task 两 child、P03 write_text/真实文件、calculate、权限拒绝/重复、非法 Schema、超时/取消。只测 A 及触及旧测试、Ruff、前端 Build；独立提交 A SHA。**如 P04 Command 被错误转成 ToolMessage、丢 Graph State 或模型能越权，STOP**。

**P05-B · 真只读 HTTP MCP 与工具审批**：加入 SDK/Adapters、配置与本地 sample、固定 Schema digest；两进程真实协议握手/发现/查询，注册唯一 `mcp_demo_lookup_fact`，让 Lead Fake Model 真 Call 后读取 ToolMessage。断开 Server 时只 MCP 工具失效/禁用，不影响 builtin；配置变化和 Server 变化需重启；后端不接受外网/stdio/未批准名、schema 修改与写工具。CapabilityPanel 显示 MCP 状态；Ruff/npm Build+局部/真实 HTTP Smoke；独立提交 B SHA。

**P05-C · 本地 Skills 按需读取与不提权**：实现 Loader、示例 SKILL.md、list/read 两工具，GET /api/skills，CapabilityPanel 实际技能列表；用 Fake 测正向加载、非法 YAML、超限、symlink、重名、非法 name/unknown tool、Skill 要求未授权工具不展示也不能读取、Prompt 不一次性注入全部内容；同 P03 的文本文件工具配合；独立提交 C SHA。**Skill 不是可执行代码，也不能修改 Registry**。

**P05-D · 主链、故障、刷新、真模型最终 Demo**：组合 P01–P04 当前代码，实测本机 MCP + Skills + 内置文件工具在**同一父 Run**能按需选择；必要时上传 notes.md → list_skills/read_skill → read_text/list_files → summary.md Artifact，另个问题调用 MCP sample，子代理不能得到 MCP/Skills；MCP 离线不拖垮 builtin，重复/缺 pin/特殊 URL/prompt injection/超时不泄露权限，旧 Todo/Task/SSE/Checkpoint/下载仍正确。只对新增/修改和直接调用方做局部 pytest、Ruff、TypeScript Build、真实浏览器（独立端口/临时数据）。有用户已配置可用真实模型时单独 Smoke，不改变 .env、不输出 key 或真实私人正文，明确记录实际 ToolCall IDs 与真实模型选择，不能把 Fake 结果当真模型通过。最后标 `PENDING_REVIEW`，用户手动验收前不改为 ACCEPTED、不开始 P06。

**明确停止条件**：官方 `awrap_tool_call` 与锁版不匹配、`write_todos` Command/ToolMessage 丢失或重复、MCP schema pin 无法复验、HTTP URL/工具权限绕过、本地 Skills 逃逸/提权、故障后模型/Registry 仍错误允许不可信工具、子 Agent 获得新增权限，必须 STOP 并附最小复现和当前 SHA；**不要为完成 Demo 放宽安全边界**。只记实际发生的 SHA/测试，日志不收集外部敏感数据。

**资料/重要差异**：DeerFlow v2.0.0 `backend/packages/harness/deerflow/tools/tools.py`、`mcp/tools.py`、`skills/parser.py`、`skills/tool_policy.py`、`agents/middlewares/skill_activation_middleware.py`；LangChain 当前官方 `awrap_tool_call` / [Agent Middleware](https://docs.langchain.com/oss/python/langchain/middleware)；[LangChain MCP adapters 源码](https://github.com/langchain-ai/langchain-mcp-adapters/blob/main/langchain_mcp_adapters/client.py)；[MCP 安全实践](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)；[官方 MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。上述是参考机制，不要直接移植 DeerFlow 的 SessionPool/前端管理或复制全部 Skill 系统。


### P06 — 运行预算 / 上下文压缩 / 取消与恢复（2026-11-06 正式详细设计）

> **状态：PLAN_READY（仅设计、未开始 P06 代码和测试）**。用户已明确请求“设计 p6”，不是自动授权开始本地 Codex 或将 P02–P05 设为 ACCEPTED。工作分支 `feat/p06-context-budget-cancel` **从含 P05 A/B/C/D 真实代码的** `feat/p05-tools-mcp-skills` 派生。逐文件实现与局部测试以 [P06-A/B/C/D Codex 合同](tasks/P06-ABCD.md) 为准，每步交付同步前端、独立测试/提交，关键边界失败立即停止，不进入 P07。

#### 1. 用户业务主线、功能范围

**正向链路**：用户发起较长 Thread Run → RunService 建立有界预算和共享 UsageTracker → 每次 Lead/Child 模型调用及工具调用前校验剩余额度，结束后从模型实际 `AIMessage.usage_metadata` 记录 provider usage；历史接近单请求上下文阈值时，只压缩**已经完成**的旧回合，保留当前目标、最近完整消息、Todo 和真实文件/Artifact ID；过长工具输出只向模型返回短预览和已登记的可追溯文件引用 → P02 Run 与 SQLite 使用量持久化 → Web 实时/刷新后显示预算与实际/估算用量。

**中断链路**：用户按“取消 Run” → HTTP 在 SQLite 原子标记 `cancel_requested_at`（表示**请求已接收**而非执行已经停止）→ 尚未运行的 CREATED 直接安全终结 CANCELLED，排队记录成为可跳过 tombstone → RUNNING 的 Graph Task 收到取消、拒绝后续新 Tool/Model 调用，等待 child Task/Workspace/SQLite 清理 → 状态最终为 CANCELLED 或保守 FAILED/OUTCOME_UNKNOWN；重启时仍只核查并终结孤儿，**不重放未知副作用**。

**不做**：跨进程恢复正在运行的 Sub-Agent、长期记忆/向量检索、真正 Tokenizer 精确成本计费、多用户配额、第三方计费查询、任意重新执行 ToolCall、通用补偿事务、在浏览器关闭时自动取消、替换 P02 Checkpointer、后台作业中心或分布式队列。**本地单 Worker/SQLite/Graph/Workspace/MCP/Skills 现有架构不变**。

#### 2. P05 实现基线与本阶段关键取舍

实际当前源码：`runtime/runner.py` 由有界 Queue（2 workers/8 pending）执行 `_execute_run`，父持久 Run `run_timeout_seconds=150`，Graph `recursion_limit=36`，`task_registry.close_run` 执行清理；`runtime/repository.py` 只允许 CREATED/RUNNING→SUCCEEDED/FAILED，`RunStatus.CANCELLED` 虽已在枚举和数据库 CHECK 中却**从未启用**；`runtime/db.py` 有 CHECK 约束与已有数据；`tools/executor.py:ToolGuardMiddleware.awrap_tool_call` 会原样透传 `Command`、按工具超时与权限检查；`agents/lead.py` 可选传 `middleware`；`agents/subagents/executor.py` 独立 create_agent 无父 Checkpointer，`context.py` 的 AgentRunContext/ChildContext 仍继承 P03 WorkspaceContext；`runtime/streaming.py` 采集真正的 ToolMessage / AIMessage；React 当前 180 次 1 秒轮询即停止继续查询。

**重要修订原粗规划**：
1. 不做 `runs.status CHECK` 的破坏性 SQLite 表重建。**沿用 CREATED/RUNNING/SUCCEEDED/FAILED/CANCELLED**。用新增 nullable `cancel_requested_at` 表示 RUNNING 时“取消处理中”，前端展示“正在取消”，最终 CANCELLED 仅说明**本地执行与子任务已停止**；无法确认外部写入时用 FAILED + `OUTCOME_UNKNOWN` + `needs_recovery=1` 提醒人工检查，**不要**声称外部动作已撤销或支持精确一次。
2. P06 允许长 Run，`run_timeout_seconds` 改默认 **600 s**、上界 600；前端轮询从 180 次调整到**720 次**、Run 的 EventSource 重连策略仍按 P02，不无限轮询。P01 单轮 `model_timeout_seconds=45`、child 单任务35 s/14图步、父 `recursion_limit=36` 不变。最大请求时长与调用次数/工具次数**各自独立**，不是 40 次模型调用等于 LangGraph 40 图节点步。
3. 数据库只增可回滚/幂等的 `runs.cancel_requested_at` 一列和预算/usage 表/索引，不改旧 Run/Thread/Checkpoint ID，默认旧数据可读。增列由 `RuntimeDatabase.init_schema()` 检查 SQLite `PRAGMA table_info` 后**仅在缺列时 ALTER TABLE ADD COLUMN**，不可通过修改 CREATE TABLE IF NOT EXISTS 假装旧库升级。
4. `agents/context.py` 已负责可信 Context dataclass，新增独立 `agents/context_manager.py` 管理摘要，`agents/middleware.py` 管理执行 hook；不复制同名 `Context`，不把可变预算/服务对象写进 Graph State/SQLite Checkpoint。
5. P05 MCP 本期仍然只有批准的本地只读 Server；P06 不为 Child 增加 MCP/Skills/文件写权限。压缩与预算并不修改 `ToolPolicy`、`TaskRegistry` 限额或 Skill 前置条件。

#### 3. RunBudget / Usage：可计数、可观测、不虚构

默认每父 Run：
- `max_model_calls=40`、`max_tool_calls=30`，**父+所有 Child + 触发摘要的模型调用共享同一额度**，并发下用同步/async lock 原子预扣；失败/超时调用也消耗预留次数。父图节点步上限36、Child分别14仍继续各自限制，因此40不是可保证用满的数字。
- `max_input_tokens_estimate=120000`（Run 累积输入估算软/硬保护用上界）、`context_soft_limit_estimate=12000`、`context_hard_limit_estimate=18000`（单次请求的**保守估算值**）；模型实际 context window 因提供方不同而不确定，这些数**不是**模型端承诺的窗口。估算使用确定性文本 UTF-8 大小/消息结构开销，测试用固定逻辑，不输出“精确 tokens”；当下一请求超过 hard 必须先摘要或失败，不可透传超限然后让 Provider 兜底。
- `max_seconds=600` 从 Run **转 RUNNING** 的单调时钟开始；排队不计运行预算，运行中实时检测 Deadline，所有 await 须受已有总 `asyncio.timeout` 控制；Sub-Agent 单次仍35秒。超额统一 `BUDGET_EXCEEDED`，不继续新的模型/工具调用；已发出但未确认成功的外部写操作不自动重试。
- Usage 用模型回复的 `AIMessage.usage_metadata`（或已锁版真实 provider metadata）取得 `input_tokens/output_tokens`，**按父/子/摘要每一次唯一模型调用 ID 去重**。没有使用量时 `provider_input_tokens/provider_output_tokens=NULL`，另填 `estimated_input_tokens`、`usage_source="estimate"|"provider"|"unknown"`；不能把 estimated 计入真实 provider total，不能将缺失=0或算出不存在的金额。SSE 流式 chunk 不能与最终 AIMessage 重复计费。
- `RunBudgetTracker` 属于每个在执行 Run 的可信内存对象（锁+deadline+共享计数器），Parent 与 Child Context 指向同一 tracker；记录一份业务 SQLite 可查询聚合 `run_usage`（run_id PK、model_calls/tool_calls、provider token 汇总/unknown_count、estimated tokens、elapsed_ms、compaction_count、output_externalized_count 等）与**必要唯一 invocation id**的模型/工具事件 `usage_calls`。所有写入归属真实 Run，失败应脱敏并按保守终态收尾。SQLite 用于刷新后的使用量，不依赖 SSE 内存窗口。
- 精确用量持久化由自定义 `UsageBudgetMiddleware` 基于官方 `awrap_model_call` 收到**最终模型响应**再记录（锁版可能是 ModelResponse），child 也安装同一 Middleware；Tool 计数/耗时由 `ToolGuardMiddleware` 调用共享 Tracker，child 另设轻量 Budget Middleware（保留原 P04 只读角色工具）；不要在 `stream_agent` 采集 delta 时再计算一遍。必要时摘要模型按相同 Tracker 记录。每次请求开始先预扣、失败也记次数；生产者与 DB 提交冲突时不得把已发起的调用假装未发生。
- `GET /api/runs/{run_id}/usage` 返回 `RunUsage`（`run_id,model_calls,tool_calls,provider_input_tokens?,provider_output_tokens?,usage_unknown_calls,estimated_input_tokens,elapsed_ms,compaction_count,output_externalized_count,budget`），不存在 Run 404；无调用时计数0、provider tokens 为 NULL；EventBus 新增 `budget_updated` 通知小型数值统计，**不能发送原始 prompt、模型响应、API Key、工具正文**。
- `UsagePanel` 每个 Run 都显示模型/工具次数、预算上限、真实 provider token 与估算区分、耗时、压缩次数；Run 完成/刷新/重启后从 GET 权威查询，SSE 只做可选即时显示。

#### 4. 长消息/工具输出与上下文压缩

**两层问题不要混淆**：`ToolMessage` 的过长正文进入 Graph State 会引发上下文膨胀；历史 Message 越来越多会引发后续模型输入过大。分别处理：
- `tools/output_budget.py:ToolOutputBudgetMiddleware` 安装在 P05 `ToolGuardMiddleware` 外层，在工具真实完成后处理 `ToolMessage|Command`，**先确认 type/ToolCall ID 与真实错误状态**，只转换超过 **12 KiB UTF-8** 的**成功纯文本** ToolMessage；小结果不改变，失败消息不转成功，`Command`（特别是 `write_todos`）默认原样传递并有测试。不得重新调用原工具、不静默截断原数据、不得执行 ToolResult 内不可信“指令”。
- 已有 `read_text(file_id)` 结果可直接指向**原来登记过的当前 Thread file_id**，模型只看到带证据 `file_id`、字节数与 1 KiB 预览以及“原始文件仍可分段处理/改问更小范围”的说明，避免重复写一份相同文档占用 Thread 30MiB/50文件额度；若是其它实际无登记来源的长纯文本结果，先以当前可信 parent Run 的 `WorkspaceService.write_text` 存成新的唯一 `tool-output-<uuid>.md` Artifact，得到 `artifact_id/file_id` 才用小回执替换；目录已满/登记失败则返回 `ERROR[TOOL_OUTPUT_TOO_LARGE]`，不把长内容漏回模型，不伪称“产物已保存”。**Child** 只读、不建立新 Artifact，过长 `read_text` 只可引用原已登记 file_id；其它超长 child 回执按稳定错误处理，绝不利用输出预算绕过 P04 文件写限制。
- 替换必须维持原始 `tool_call_id`、`status`/来源和 ToolTrace 语义；`Command` 的工具状态变更不能因转存丢失。ToolOutput Artifact 只登记真实结果，原数据库/文件的无跨库原子限制照 P03，取消/异常时仍需完整清理。
- `agents/context_manager.py` 与 `agents/middleware.py:ContextCompactionMiddleware`：在模型请求预计超过 12k token 时，将消息分为**已完成、可安全摘要的旧工具/对话回合**与**必须保留的最后 6 条完整交互消息及当前 HumanMessage**。任何带未配对 tool_calls 的 AIMessage 与后续 ToolMessage 必须作为整体保留，不能摘要掉一个、留下另一个；保留当前 Run 的用户原始目标、活动未完成 Todo（Graph `P04AgentState.todos` 独立字段 + SQLite）、真实已登记的文件/Artifact IDs 与关键原始证据引用。只摘要旧回合，不跨 Thread 汇总，不直接修改 P02 Run 历史。
- 优先对齐锁版 LangChain 官方 `SummarizationMiddleware` + `RemoveMessage/REMOVE_ALL_MESSAGES` 的安全状态更新；如果官方通用摘要 API 无法同时确保上述 Todo/ToolMessage 完整性，允许在项目的 `abefore_model` 做**最小**安全分区/替换实现，必须写 Fake+Checkpoint 真实状态测试，不能引入自造 Agent loop。摘要模型使用同一已配置模型，计入同一 Run 预算和耗时，单次摘要文本最多 2KiB、额外最少保留最近 6 条、拒绝用摘要代替用户当前指令；不要将摘要“变成更高权限的系统指令”。摘要返回空、超时、估算仍高于硬上限，应 `CONTEXT_BUDGET_EXCEEDED` 失败而非静默删除仍未处理的任务；无配置模型时本期仍可直接使用无摘要短会话。
- `context_compacted` EventBus 只发布 `{run_id,old_message_count,new_message_count,estimated_before,estimated_after}`；SQLite 使用量只记录次数，不将原对话正文复制进新表。Graph Checkpointer 保留摘要后状态，**SQLite Run 历史依旧完整记录各轮用户提问/最终答复**，但 Graph 的历史消息可被安全压缩；摘要不是 Checkpoint 的替代品。

#### 5. 用户取消、服务关闭、重启恢复边界

**API**：`POST /api/runs/{run_id}/cancel` 无 body，幂等，返回 `{run_id,status,cancel_requested_at?}`。不存在404；已 SUCCEEDED/FAILED/CANCELLED 返回既有真实终态而不修改；CREATED 在业务库事务内直接 `CANCELLED`、写 finished_at，运行队列里 ID 保留 tombstone，worker 拿到时跳过且不调用 Graph/Model；RUNNING 仅原子写 `cancel_requested_at` 并返回**202 请求已接收**，此时 status 仍 RUNNING，页面按 cancel_requested_at 显示“正在取消”，不提前返回 CANCELLED。重复 cancel 不增加信号、不改变已保存的请求时间。

**RunService 内部**：添加单进程 `RunCancellationRegistry`（`runtime/cancellation.py`）保存当前图任务句柄、cancel event、工具执行不确定性标记；**worker 不可因为一个 Run 的 cancel 就被杀死**：把单个 Run 的 `_execute_run` 放在由 worker 等待并拥有的独立 Task 中，停止信号取消的是该 Run Task；worker 收尾继续消费其它 queued Run。用户请求与模型自然终态存在竞态，终结事务必须以 `cancel_requested_at IS NULL` 等 CAS 防止“取消已提交后又成功”；若成功先提交，cancel API 读到 SUCCEEDED 而不是伪造取消成功。**特别处理 RUNNING 已提交但活动 Graph Task 尚未注册的窗口**：`RunCancellationRegistry.register` 必须注册后复查数据库 cancel_requested_at/事件；`_execute_run` 真正开始模型/Tool 之前再次验证请求标记，发现已取消则直接按清理流程结束，不允许漏掉先到的取消信号。Graph 取消后必须先 `await TaskRegistry.close_run`，等待 Workspace/ToolGuard 关键事务，才写 Run terminal 和 `run_end`，释放当前 Thread 的活动 Run 约束。ToolGuard/Usage Middleware 在下一次 Model/Tool 发起前检查 cancel 标记，取消后不得继续新增操作。

**结果判定**：
- 未进入 Graph 的 CREATED → CANCELLED、`needs_recovery=0`，继续正常 Thread。
- 已进 Graph 且确定被本地完全取消并清理 → CANCELLED，**保守设置 `needs_recovery=1`**（Graph 可能部分写了 Checkpoint）；不提供从最后一条半完成消息盲续跑。用户创建新 Thread 继续。
- ToolGuard/RunService 检测到已发起的写/外部调用但**无法确认其真实结果**，或取消/崩溃导致进程结果不明 → 最终 **FAILED + `OUTCOME_UNKNOWN` + needs_recovery=1**；页面明确提示检查已登记 Artifact/外部系统后手动处理，绝不声称事务已回滚，也不自动重试。当前 P05 MCP 默认只读，但这条边界给未来外部写工具留安全位置。
- Run 超时/预算耗尽仍写 FAILED + 稳定 `MODEL_TIMEOUT` / `BUDGET_EXCEEDED` / `CONTEXT_BUDGET_EXCEEDED`，是否需恢复沿既有 graph_started 保守规则。**关闭后端**与**用户主动取消**明确区分：无显式取消请求的 shutdown/重启不写 CANCELLED，只按 `RUN_INTERRUPTED`/不确定性失败处理。
- 重启 `RuntimeRepository.reconcile_orphans()` 检测旧 CREATED 与 RUNNING（含 cancel_requested_at 非空）按实际是否进入 Graph 保守标记，已有 P02 旧库无法从业务库判断是否已进入图时宁可设 needs_recovery=1；不自动重新派发 child 或调用写工具。P04 子任务 `reconcile_orphaned_subtasks` 延用 FAILED/SUBTASK_INTERRUPTED，无精确恢复承诺。
- SSE 增加 `run_cancel_requested`，终态继续使用旧 `run_end` 且必须 DB 先落终态；浏览器断开 SSE **不触发取消**，只有用户点击取消才走该 API。Run 仍 RUNNING 且已申请取消时禁止重复点击；未知结局需明确的 UX 警告。

#### 6. 精确文件、接口和前端职责

| 文件 | 本期职责 |
|---|---|
| `backend/src/minideerflow/runtime/budget.py` | `RunBudget` 与 `RunBudgetTracker`：父子共享的原子次数预扣、估算输入预算、deadline、取消检查及终结汇总 |
| `backend/src/minideerflow/runtime/usage.py` | `UsageRecord/UsageRepository` 与 provider usage 解析、去重/归属/NULL vs estimate 语义、查询 DTO |
| `backend/src/minideerflow/runtime/db.py` | 增加 `run_usage`、`usage_calls`、索引；幂等 ALTER `runs.cancel_requested_at`，旧 P05 数据不断表、不断列 |
| `backend/src/minideerflow/agents/middleware.py` | `UsageBudgetMiddleware`/ `ContextCompactionMiddleware`；父/子模型计数与用量；P05 原 ToolGuard 仍存在 |
| `backend/src/minideerflow/agents/context_manager.py` | 旧回合原子分组、已配对 ToolCall 保留、当前目标/Todo/真实 refs 保护、摘要+安全 Checkpoint 更新、触发条件 |
| `backend/src/minideerflow/tools/output_budget.py` | 官方 `awrap_tool_call` 长文本 12KiB 控制：ToolMessage 短预览、登记原文件引用或安全产物、不能触碰 Command/失败消息 |
| `backend/src/minideerflow/tools/executor.py` | P05 ToolGuard 最小加入预算预扣/耗时、取消检测、工具结果未知标记；原权限/Schema/MCP 规则不变 |
| `backend/src/minideerflow/agents/context.py` | AgentRunContext/ChildContext 加共享 budget/usage/cancellation 只读依赖；仍继承 WorkspaceContext、child 不增权限 |
| `backend/src/minideerflow/agents/lead.py` | 复用可选 Middleware 列表，指定 P05 Guard + P06 Budget/Context/Output 合法顺序 |
| `backend/src/minideerflow/agents/subagents/executor.py` / `dispatcher.py` | child 同步使用共享 tracker 和取消信号；Child 独立 Checkpointer None 与 P04 超时、Tool 白名单保持；子模型实际 usage 计入 parent Run |
| `backend/src/minideerflow/runtime/cancellation.py` | 活动单 Run Task/信号、in-flight 未知结果标志、请求后的等待与注销；worker 不取消、无悬空 child |
| `backend/src/minideerflow/runtime/models.py` / `repository.py` | RunDto 增可选 cancel_requested_at/提示字段；CAS 取消和单向 CANCELLED 迁移、未知失败/孤儿核查、无旧数据损坏 |
| `backend/src/minideerflow/runtime/runner.py` | 组装并传递预算/usage/工具输出/摘要/取消，单 Run Task 与 Queue tombstone，父 timeout 600 秒、SQL 终态与子任务回收 |
| `backend/src/minideerflow/api/runs.py` | POST cancel + GET usage，保留现有 Run/SSE API、脱敏错误与错误码 |
| `backend/src/minideerflow/main.py` / `config.py` / `.env.example` | 生命周期初始化 UsageRepository/CancelRegistry，预算默认与硬上界，资源关闭顺序不变 |
| `frontend/src/api/runtime.ts` | CancelResponse/RunUsage DTO、新请求函数、`cancel_requested_at`、SSE 新事件订阅；轮询 720 秒 |
| `frontend/src/components/UsagePanel.tsx` | 当前和历史 Run 的真实/估算用量、预算计数和摘要次数，刷新 GET |
| `frontend/src/components/RunStatus.tsx`、`ChatPanel.tsx`、`styles.css` | Run 取消按钮/取消中状态/保守失败/新事件/用量面板；P02–P05现有控件无倒退 |
| `backend/tests/test_budget.py`、`test_usage.py`、`test_context.py`、`test_output_budget.py`、`test_cancel_recovery.py`、`test_budget_demo.py` | Fake 模型、SQLite Saver+业务库、工具闭环、压力限额/摘要/取消/shutdown与前端 HTTP/SSE 测试 |
| P02–P05 直接消费方测试 | `test_runner.py/test_runs_api.py/test_checkpoint.py/test_tool_guard.py/test_subagents.py/test_planning_demo.py/test_tools_demo.py` 等仅按具体接口影响运行 |
| `README.md` / `docs/progress/P06.md` / `docs/tasks/P06-ABCD.md` / `docs/ARCHITECTURE.md` | A–D 真实 SHA、局部测试/构建、真实/估算值区别、用户 Demo 与限制 |

#### 7. A/B/C/D 实施步骤与每阶段验证

**P06-A · 共享模型/工具预算、Usage SQL、UsagePanel**
1. 先用已锁版 Fake 检验 `awrap_model_call` 及其 ModelResponse/AIMessage usage_metadata、child `create_agent`、P05 `awrap_tool_call` 的顺序；禁止靠猜测双计数。
2. 实现 `runtime/budget.py`、`usage.py`、DB 表/索引、官方 Middleware + Runner/Child 上下文注入、GET usage；前端 UsagePanel + SSE 数字。独立 P01 模式不增加 P06 复杂预算，原 45s 生效。
3. 验证父子共享 max_model_calls40/tool_calls30、并发预扣无超额、provider usage 与估算独立、缺失显示 unknown/NULL、Run刷新重启与历史、无 ToolCall ID 污染、P04 Task/ToolGuard 不受影响。局部 tests + Ruff + TS build；独立 SHA。

**P06-B · 长工具输出外置、Graph 上下文安全压缩**
1. 先用受控 20KiB/60KiB 样例实测 `ToolOutputBudgetMiddleware` 对普通 ToolMessage、P04 `Command`、P05 Guard 的真实调用顺序；保持工具只执行一次。
2. 实现 `tools/output_budget.py`（已有 file_id优先引用、不重复复制，非登记来源结果登记 Artifact），`agents/context_manager.py`、摘要 Middleware/Graph State；配置 12k/18k 单请求估算阈值。前端 UsagePanel 展示 compaction_count/output_externalized_count；SSE 两个轻量事件。
3. 测多个旧回合压缩后 Checkpoint 仍可用、当前用户目标及 Todo/未完成 ToolCall 配对保留、真实 file ID/Artifact ID 与 P03 下载匹配、摘要失败拒绝继续、无模型短会话不触发、超限/额度不足 fail closed、跨 Thread 不串消息；局部 tests + Ruff + TS build，独立 SHA。

**P06-C · HTTP 取消、Queue/Runner/Child 竞态、历史状态**
1. 实现 `runs.cancel_requested_at` 原地兼容迁移、`RunCancellationRegistry`、`RuntimeRepository.request_cancel` 和 CANCELLED 真实迁移；不改旧 status CHECK / 既有 Run 终态/Thread 独立性。
2. 在 Runner 让 worker 等待单 Run Task，显式 cancel 只取消该 Run、不杀 Worker，`TaskRegistry.close_run`/Workspace shield/DB 事务完成后发终态；queued CANCELLED 记录被 worker 安全跳过，竞态用 SQL CAS。新增 API/前端取消按钮与运行中提示，不影响历史 GET。
3. 测重复 cancel、CREATED 未模型执行、RUNNING 停止 tool/child、外部未确认 FAILED/OUTCOME_UNKNOWN、cancel/success 同时发生、shutdown 无用户取消不假报 CANCELLED、重启 orphan 不重放、SSE 断开不取消、timeout/BUDGET_EXCEEDED 与 P02 恢复状态；局部 tests + Ruff/TS Build，独立 SHA。

**P06-D · 完整联合 Demo + 故障注入/手动验收材料**
1. 用真正的临时 SQLite 两库+Workspace、Fake Model、可控慢模型、真实 ToolNode 运行：长文档/多轮逼近阈值 → Graph 完整消息压缩、Todo保留、引用不丢 → 长 ToolMessage 外置或原 file_id 引用 → Usage 总量/Null semantics → User cancel 中断一个复杂 Run → 并发队列中另一个 Run 继续正常 → 历史刷新/重启不丢失、产物可下载。
2. P05 真实本机 MCP 可用时做连接/离线与取消边界；默认无 MCP 仍可验收 P03 文件/P04委派。若现有真实 Tool Calling 模型可用，单独使用短合成材料 Smoke 真实 usage、一次触发摘要（不要通过大量真实 token 堆叠强行触发）、取消与后续新会话；真实/估算/Mock 分开记录。
3. 旧 P01 计算/单轮、P02 Run/SSE/Checkpoint、P03 Workspace、P04 Todo/Child、P05 Registry/Skills/MCP 直接消费者必须通过局部回归；保留中文关键注释和 `# 1/2/3` 分段。仅实际运行的 pytest、Ruff、uv lock、前端 npm build 记结果；无全量 P07+。真实浏览器含 UsagePanel、取消中/终态、刷新/重启。
4. 进度写入 A/B/C/D 真实 SHA/局部数量/模型账务来源/异常与未验，D 结束状态 `PENDING_REVIEW` 供用户手动验收，**不把 P02–P05 当作已亲测、不自动进入 P07**。

**停止条件**：官方 Middleware/SQL旧库增列/ToolMessage Command/usage去重任何一项不安全；压缩破坏当前目标或工具成对消息、取消后仍新增子任务/模型调用、原子 CAS 失效、模型推测用量被记成真实费用、文件外置丢数据、Run 提前显示 CANCELLED、未知副作用被重放，Codex 必须停止并给最小复现；不得只为了 Demo 放松约束。所有状态只由真实运行和业务库决定。

**参考**：DeerFlow v2.0.0 源码 `backend/packages/harness/deerflow/agents/middlewares/{summarization_middleware.py,tool_output_budget_middleware.py,loop_detection_middleware.py}` 和 `backend/packages/harness/deerflow/runtime/runs/{manager.py,worker.py}`；官方 [LangChain Middleware](https://docs.langchain.com/oss/python/langchain/middleware)、[短期记忆与状态](https://docs.langchain.com/oss/python/langchain/short-term-memory)。优先参考**当前锁版**的 API，与这些上游不同则实测后做最小兼容变更。


### P07 — Deep Research：真实联网检索、来源证据与报告（2026-11-09 详细设计）

> **P07 状态：PLAN_READY；仅设计与任务合同，尚无 P07 代码/测试。** P06 的 Run/Context/Budget/Cancel 已推送远端，2026-11-09 最新注释优化 Commit `f291af58bfec249eeae55823739b7c12a47ab8bf` 已核实；P06 与 P02–P05 仍为 `PENDING_REVIEW`。P07 分支 `feat/p07-deep-research` 从该 P06 完整代码分支派生。**开始 P07 设计不代表 P06 手动验收通过；启动 Codex 编码前先完成 P07-0 基线质量检查**。实施合同：[P07-A/B/C/D 逐文件任务书](tasks/P07-ABCD.md)，真实结果只记 [P07 进度](progress/P07.md)。

#### 1. 本期到底要做什么（业务验收链）

用户发起一个需要最新信息的研究问题（如“比较 LangGraph 和其他 Agent 编排方案的功能与边界，输出含参考资料的报告”） → Lead 根据复杂度调用 P04 `write_todos` → 读取 P05 `deep-research` Skill 的研究步骤 → 使用 **`search_web(query)`** 获取真实候选来源并给每个来源分配服务器生成的证据 ID → 使用 **`fetch_webpage(evidence_id)`** 取得有上限的网页正文，并明确区分“只有搜索摘要”和“已取得正文” → 有需要时委派 P04 `research` Sub-Agent 对子主题搜集和比较，子 Agent 仅返回 Findings、Evidence IDs、Missing → Lead 调用 **`save_research_report(title,findings,limitations)`**，服务器验证引用证据和来源状态、渲染 Markdown，经 P03 Workspace 写入真正的 Artifact → React `ResearchPanel` 显示来源/验证等级/报告下载；刷新、重启可查询同 Run 结果。

**简单问题不强制 Deep Research**。没有配置联网提供方时，既有 P01–P06 计算/文件/本地 Skills/MCP 功能仍可用，Research 服务的可用状态清楚显示“尚未配置”，模型不得声称在线搜索或引用“已访问网页”。P07 只实现真实**联网搜索、网页文本证据、研究报告**，不做 P08 PDF/RAG、浏览器自动化、学术全文/付费墙、图像视频、多供应商搜索/自动回退、不可信页面执行脚本或用户自动安装工具。

#### 2. 本期最重要的设计调整：优先使用 Tavily Search + Extract，而不是任意 URL 直连

原 P07 粗方案拟用 Tavily Search API 取得结果，再以本机 `httpx` 任意抓取 `fetch_webpage(url)`。审核后将 **`fetch_webpage` 入参改为当前 Run 的服务器证据 ID、网页正文通过同一 Tavily Extract API 获取**，不由本地进程对模型提供的任意目标发送 HTTP。这是刻意的安全简化：
- Tavily 官方 Search 支持固定 `https://api.tavily.com/search`，`max_results`、`include_raw_content=false`；Extract 支持 `https://api.tavily.com/extract`，返回每 URL `results` 与 `failed_results`。详细 API：[Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract)。
- 本期直接使用**已有的 `httpx`** 以 `AsyncClient` 向固定 Tavily API 域名 HTTPS POST 两种请求，Bearer `TAVILY_API_KEY` 从 `Settings.SecretStr` 提取；无需引入 Tavily SDK 或第二家搜索提供方；网络 `follow_redirects=False`、`trust_env=False`，固定 host/path/HTTPS/响应大小/连接与读取超时。**Tavily 作为第三方服务对外部页面发起请求**，本地服务绝不直接连接来自模型的任意 URL，从架构上消除本地任意目标抓取的 SSRF 入口。
- 对搜索结果 URL 仍严格解析和校验：只承认公开的 http/https 域名、无 userinfo、无 localhost/私有/链路本地/保留 IP、无危险 scheme/奇异端口，规范化后去重；不允许从 `fetch_webpage` 输入自行传 URL。虽然不本地访问来源 URL，但也**不展示/送给 Extract 不安全 URL**，以降低错误引用与提供方误用风险。
- 本期的“EXTRACTED”意味着**Tavily 报告已提取正文**，不是助手亲自核实了网页真实性、真实性权威或实时更新；来源仍可能过期、造假或被注入恶意内容。标题/摘要/网页正文只是普通不可信数据，不允许执行其中的指令、要求提交密钥或扩大 Tool Policy。
- **安全回退原则**：如果官方 Extract 接口不可用，返回 `EXTRACTION_FAILED` 且保留 `SNIPPET_ONLY` 搜索证据，报告必须标注证据等级；不擅自改成直接 `httpx.get(untrusted_url)`，也不自建浏览器。避免因实现压力引入 DNS rebinding/重定向安全漏洞。

#### 3. 现有 P06 代码接口与 P07 权限改造

直接复用以下已实现入口：`runtime/runner.py` 创建每个 Run 可信 `AgentRunContext`、`P04AgentState`、`create_agent`；`tools/registry.py:register_builtin_tools` 与 P05 `ToolGuardMiddleware` 负责工具调用的二次权限/参数/超时；`agents/subagents/dispatcher.py` 目前将固定 `general/research` 工具对象白名单交给子 Agent，`ChildContext` 继承 `WorkspaceContext`，子图 `checkpointer=None`；`skills/loader.py` 按 Registry 真实权限发现 Skill；`runtime/usage.py` 与 P06 `RunBudgetTracker` 为父子共享次数/用量，`RunCancellationRegistry` 取消后不得再启动模型/Tool；`workspace/service.py:write_text` 创建有 SHA、归属的下载 Artifact。

**权限升级必须只针对 research 角色**，不得把 P04 general 子代理变成通用联网 Agent：
- Lead 增四个工具：`search_web`、`fetch_webpage`、`list_evidence`、`save_research_report`；均在 ToolRegistry 登记且使用可信 `ToolRuntime`，Schema **不暴露** `run_id/thread_id/provider/key/service`。 `save_research_report` 权限写/编排，仅允许 Lead 且要求当前 RUNNING 且未请求取消。
- Research 子 Agent **只**新增 `search_web/fetch_webpage/list_evidence` 到原有 `list_files/read_text`；无 `write_text/save_research_report/task/write_todos/MCP/Skills`。General 保持 P04 `calculate/list_files/read_text` 不变。当未配置 Tavily 时，research 保持原 P04 离线角色和准确 Prompt，不主动假装联网。
- 修改 `ChildContext` 增**可选可信** `research_service` 和 `tool_policy` 字段；父 `AgentRunContext` 同样增加 `research_service`，服务端由真实 Run 装配。P05 ToolGuard 原实现只接受 AgentRunContext，故必须在代码中明确支持**仅用于 `read` 研究工具的 ChildContext**，并且父子校验 `thread_id/run_id`、`allowed_names/permissions`、身份确实 RUNNING；不可简单跳过守卫，否则模型 JSON 可绕过 Tool Policy。Child 启用 P05 Guard 后**替换而非叠加** P06 `ChildToolBudgetMiddleware` 以防工具次数重复入账；保持 Child 的 `UsageBudgetMiddleware` 与 `ToolOutputBudgetMiddleware`，不同角色的 Tool Schema 确实不同。
- `ToolRegistry` 在应用 lifespan 内按顺序：P05 原内置 → 配置时 Research Tool（若无密钥则 capability 标记 unavailable，不给模型工具）→ P05 已批准本地 MCP → P05 Skill Tool → freeze → 创建 SkillCatalog。研究工具服务的 Provider/API key 从不暴露给前端或提示词。**不重建第二个 Agent 主循环或固定 Deep Research StateGraph**。
- P06 上限保留：父 Run600s、模型40次/工具30次共享、TaskRegistry总4次/最大3并发、每 child35s/图步14；研究调用有更紧的**按 Run SQL 上限**：`search_web` 最多6次，`fetch_webpage` 最多8次，每次最多5 SearchHit，一 Run 最多30证据条目，研究报告最多1份。计数按**发起尝试**、含失败、并发 SQL 原子预扣；这不是替代 P06 预算而是叠加的外部 API/成本保护。
- API Provider 实际单次耗时：Search/Extract 各最多12秒，不做隐式重试；ToolRegistry 为 Search/Fetch 单次配置15s，Child35s总超时仍生效，P06取消传播到父子，运行结束/重启不重发可能已计费的请求。用户需知 Tavily 搜索/正文提取可能另有独立提供方费用，**本期不虚构提供方计费金额**；P06 UsagePanel 仍只统计模型 provider usage。

#### 4. EvidenceStore：一切引用以服务器持久记录为准

新增业务 SQLite 表（使用 P06 `RuntimeDatabase.init_schema` **幂等增表，不改变既有表 CHECK/Run/Thread**）：
- `research_requests(id TEXT PRIMARY KEY,run_id TEXT,kind TEXT CHECK(kind IN('SEARCH','EXTRACT')),status TEXT,created_at TEXT,finished_at TEXT)`，索引 Run+kind；用于网络调用次数的 SQL 原子占额，`PENDING` 在重启后 `UNKNOWN`，不自动重发。
- `research_evidence(id TEXT PRIMARY KEY,run_id TEXT REFERENCES runs(id),thread_id TEXT REFERENCES threads(id),canonical_url TEXT,title TEXT,snippet TEXT,extract_text TEXT NULL,status TEXT CHECK(status IN('SNIPPET_ONLY','EXTRACTED','EXTRACTION_FAILED')),searched_at TEXT,extracted_at TEXT NULL,content_sha256 TEXT NULL,UNIQUE(run_id,canonical_url))`；内容字段最多**20 KiB UTF-8**、标题最多200、Snippet最多500；按 Run+时间排序。读/更改证据必须验证真实 Thread/Run，不能跨 Run 复用 ID。对相同 URL 合并不无限追加；更新为 EXTRACTED 只接受真实 Provider Extract response，并在同事务校验请求/Run 归属；失败不会伪造成功。
- `research_reports(id TEXT PRIMARY KEY,run_id TEXT UNIQUE REFERENCES runs(id),thread_id TEXT,artifact_id TEXT REFERENCES artifacts(id),created_at TEXT)`，只记录**真实已登记 Artifact** 的结果；如果 Workspace 成功但登记报告关系失败，保留原 Artifact 并明确失败/不可自动重放，不声称报告已经完成。

**结构化对象**：`SearchHit(evidence_id,title,url,snippet,status,searched_at)`；`EvidenceRecord(...,source_status,excerpt,content_sha256?)`；`ResearchFinding(claim,evidence_ids)`；`ResearchReport(artifact_id,title,citations,limitations)`。Evidence ID 由服务器 UUID 生成，显示用稳定 `[1] [2]` 脚注号根据证据排序；不能用模型手写 URL/引文编号充当查询证据。

**必须验证的引用语义**：
- `search_web` 真正请求 Tavily 并在 SQLite 成功登记 SearchHit 后才给模型返回 ID；失败返回稳定 `RESEARCH_PROVIDER_UNAVAILABLE/RATE_LIMITED/SEARCH_FAILED`，不返回伪结果。
- `fetch_webpage(evidence_id)` 仅接收同 Run 搜索结果生成的 ID，从数据库取 canonical_url 发 Tavily Extract；结果/failed_results逐条核对 URL，才将状态置 EXTRACTED/EXTRACTION_FAILED。正文只暴露简短预览(≤1500字符)给模型，完整有界文本留业务库；不允许直接 fetch 任意 URL，也不承诺付费墙/JS网页一定可读取。
- `list_evidence()` 输出当前 Run 的 ID、title、canonical URL、状态和简短摘要，不暴露跨Run/原始大正文。失败/缺失证据也保留可信状态。
- `save_research_report(title,findings:[{claim,evidence_ids}],limitations)` 先根据数据库验证每个 Evidence ID 属于本 Run，至少1个真实来源；已 EXTRACTED 给出“正文来源”，SNIPPET_ONLY 或 EXTRACTION_FAILED 只能以**“仅摘要线索/正文抓取失败”**标注，不得在渲染器自动提升为全文支持。模型没有提供 evidence_id 的主张必须列在“尚待核验”而非伪加引用。渲染器决定 Markdown 引文与完整来源列表，不相信模型 Markdown 中的 `[1]` 或手工 URL；并明确“来源存在不等于其主张真实性已独立验证”。
- 来源 URL/网页文字可含恶意 prompt injection；工具返回给模型时采用普通 ToolMessage，不插入 System Prompt。只用可信数据库来源 ID 渲染最终引用；前端 React 不以 `dangerouslySetInnerHTML` 输出外部正文，不自动请求内网 URL、源站 favicon 或任意图片；外部链接需 `target="_blank" rel="noopener noreferrer"`。

#### 5. API、前端与用户可见状态

新增只读 `api/research.py`：
| 方法/路径 | 返回 | 失败边界 |
|---|---|---|
| `GET /api/research/status` | `{enabled,provider:"tavily"|null,status}` | 只报告是否配置；不返回 key/账单 |
| `GET /api/runs/{run_id}/research/evidence` | `EvidenceRecord[]`（标题、URL、状态、摘录、时间、ID） | 未知 Run404；没有研究证据[] |
| `GET /api/runs/{run_id}/research/report` | `ResearchReportDto|null` | 未知 Run404；无报告 null；链接必须指向已登记 Artifact |

不开放前端直接 POST provider search、fetch 或 report；研究行为由可信 Run 的真实 Tool Calling 引发。P02 EventBus 新增 `research_search_completed`、`research_evidence_updated`、`research_report_created` 事件，仅 ID/标题/状态/Artifact ID，**不携带正文/密钥**；数据库提交后发事件，SSE 缺口/重启靠 HTTP 查询真实历史。

React 新增 `frontend/src/components/ResearchPanel.tsx` 和 `frontend/src/api/research.ts`；当前 Run/历史 Run 显示联网状态、证据条数、来源 title/URL、SNIPPET_ONLY/EXTRACTED/FAILED 中文区别、报告链接和下载（复用 P03 已有 Artifact 下载 API）。P04 Todo/Task、P06 Usage 与 Cancel、P05 CapabilityPanel 在每阶段仍必须可用；P07-A 完成后研究状态和搜索证据就能单独在前端测试，B/C/D 逐步增强，不允许“最后再一起补 UI”。

#### 6. Codex 精确文件责任

| 文件 | 责任（不重新设计） |
|---|---|
| `backend/src/minideerflow/research/models.py` | SearchHit/EvidenceRecord/ResearchFinding/ResearchReport 等强类型模型与大小限制；source_status 明确 |
| `backend/src/minideerflow/research/provider.py` | TavilyProvider 固定 HTTPS POST Search/Extract、SecretStr、不重试、12s上限、JSON规范转换、出错脱敏；现有 httpx 无需添加 Tavily SDK |
| `backend/src/minideerflow/research/urls.py` | search URL 验证/规范化/公开域名判断，拒绝 DNS/IP/奇异端口/私有来源；**只对 Tavily API 发起 HTTP** |
| `backend/src/minideerflow/research/repository.py` | 同一 SQLite `RuntimeDatabase` 实现 6 search/8 extract 配额、最多30条 evidence、事务归属/URL 去重、真实状态、重启 orphan、报告关联 |
| `backend/src/minideerflow/research/service.py` | Search/Extract/Evidence/Report 主业务协调，失败保留状态、Run/Thread授权、DB提交后轻量SSE，取消/预算统一 |
| `backend/src/minideerflow/research/report.py` | 结构化 findings 与服务端真实 evidence ID 做 Markdown 引文、方法/时间/不足，调用 P03 Workspace write_text 写唯一报告 Artifact |
| `backend/src/minideerflow/tools/research_tools.py` | search_web/fetch_webpage/list_evidence/save_research_report 四个真正 ToolRuntime工具，模型只能传业务参数 |
| `backend/src/minideerflow/runtime/db.py` | 新增 research_requests/research_evidence/research_reports 三张表/必要索引，仅增量兼容 |
| `backend/src/minideerflow/agents/context.py` | 父和 child 可选 research_service；child 可信只读 policy，保留当前 P03 WorkspaceContext/P06 shared tracker |
| `backend/src/minideerflow/tools/executor.py` | ToolGuard 安全识别 ChildContext，**只允许 read 研究工具**、真实同Run身份、父子不双计数；P05原Command/ToolTrace/权限全部回归 |
| `backend/src/minideerflow/agents/subagents/config.py` / `dispatcher.py` / `executor.py` | research role 仅在配置可用时新增 3 个只读web research工具，其它角色/ChildCheckpointer None不变；child使用 Guard 替代重复Tool计数Middleware |
| `backend/src/minideerflow/agents/lead.py` / `runtime/runner.py` | 现有图使用 Registry中的四个研究工具，注入可信Service/Role；仅必要的短Prompt引导，P06预算/取消保持 |
| `backend/src/minideerflow/main.py` / `config.py` / `.env.example` | 可选 TAVILY_API_KEY SecretStr, lifespan建ResearchRepo/Service，ToolRegistry在freeze前注册，SkillCatalog后创建，HTTP路由 |
| `backend/skills/public/deep-research/SKILL.md` | 正式场景：明确是否需要实时资料→Todo→多角度search→提取正文/交叉核验→证据等级→局限→最终报告。required_tools 是真实已注册工具名，不提权 |
| `backend/src/minideerflow/api/research.py` | 三个只读 HTTP，未知Run404、密钥不出服务端、report关联真实Artifact |
| `frontend/src/api/research.ts` / `components/ResearchPanel.tsx` / `components/ChatPanel.tsx` / `components/RunStatus.tsx` / `App.tsx` / `styles.css` | 研究证据与报告的实时/历史面板；断线GET补齐与P06 cancel正常 |
| `backend/tests/test_research_provider.py` / `test_research_urls.py` / `test_research_repository.py` / `test_research_tools.py` / `test_research_report.py` / `test_research_demo.py` | HTTP Fake transport、恶意URL、SQL并发额度、真实ToolRuntime、Child权限、引用合法性、完整Artifact/HTTP/SSE/刷新 |
| `README.md` / `docs/progress/P07.md` / `docs/tasks/P07-ABCD.md` / `docs/ARCHITECTURE.md` | 完整A–D责任、局部真实测试、用户Demo/Tavily配置、文档链接与实际Git SHA |

#### 7. A/B/C/D 分解（每项单独提交、更新前端）

**P07-0 · 开始编码前的质量门槛**：先根据 `feat/p06-context-budget-cancel` 的注释提交 `f291af58bfec249eeae55823739b7c12a47ab8bf` 核对 `git status -sb`、`git diff --check f291af58^ f291af58`（用于定位既有行尾问题，**此历史比较预期会报错，并不是可在新分支修复为通过的门槛**）、`uv run ruff check src tests examples`、`uv run ruff format --check src tests examples`、P06 必要回归与 React build；修正后还要 `git diff --check feat/p06-context-budget-cancel...HEAD`（检查 P07 新变更）。最新 P06“注释优化”Commit 已确认至少一处行尾空格，并变更了 `main.py` 导入格式、去除部分 `noqa`；**目前不能声称这些检查已通过**。如果失败，仅单独提交**最小格式/注释修正**，记录在 P07 progress，严禁借机改 P06 业务逻辑或虚构 P06 人工验收。检查通过后开始 A，未通过就停下报告。Git 远端提交历史本身正常，不必重写 Git 配置、强推或合并 main。

**P07-A · Provider/搜索/取文/证据初版**：建研究模型/URL规则/TavilyProvider/SQL请求额度及EvidenceStore、search_web/fetch_webpage/list_evidence真实 ToolRuntime及Guard，Lead可搜索；增加只读 GET research/status/evidence 与 ResearchPanel 最小列表。Fake+MockTransport 不使用 Tavily Key：验证真实Schema、Search API转换、Extract结果/failed_results、同Run归属、6/8/30 SQL原子配额、链接校验、缺Key降级、Provider 超时与取消。每项测试后前端可见实际来源/状态；提交 A SHA。

**P07-B · 研究子代理有界联网/并发**：只为 research 角色添加 3 个研究只读工具，child 创建时用服务端白名单/ToolPolicy Guard，继承P06 Tracker，替换重复的 ChildToolBudgetMiddleware；General保持离线，Child无save/report/write/task。Fake 真实 ToolNode + two agents 并行访问同Run EvidenceStore、断网/失败/超时/取消和SQL配额，P04 Task/SSE/Checkpoint/ToolTrace 全部保持；ResearchPanel显示child写入的真实证据，提交 B SHA。

**P07-C · Deep Research Skill、结构化引用与报告**：版本管理 Skill，研究规划使用 P04 Todos；新增 `save_research_report`、证据核验、Markdown renderer和ResearchReport SQL真实Artifact，至少1条有效Run证据，引用可区分EXTRACTED与SNIPPET_ONLY，无法验证主张写入局限；没有已登记录或只有伪造ID的输入拒绝。前端可查看真实报告和下载，不注入 HTML；测试内容注入/交叉Run/非正常重试/Artifact双库边界和未知回执，提交 C SHA。

**P07-D · Fake/真实网络/浏览器/故障综合验收**：用户请求→Todo/Skills→Lead搜索→Research Child搜索/Extract→Evidence持久化→报告Markdown Artifact→下载/刷新/重启、P06 Usage与Cancel、P05 MCP off仍用builtin。Fake 全链路为必需；真实 Tavily key已配置时只用一个合成主题进行**少量真实 Search/Extract**并记录真实 URL/Provider响应/费用额度未知；没有 Key 应标真实网络 Smoke 未执行、P07外部依赖待配置，不能把Fake标成公网可用。真实 ChatModel若可用再独立Smoke，模型可能自主不调用工具必须如实记录。局部 pytest（仅P07及直接消费者）/Ruff/uv lock/npm build和Web人工演示材料，D独立提交，最终 P07 标 `PENDING_REVIEW`，不自动启动 P08。

#### 8. 硬性停止与验收标准

- 模型能任意指定 URL 让本地 httpx 直连；Research 子 Agent 获得写文件/委派/Skills/MCP 权限；Child ToolGuard与 P06 ChildToolBudget重复计数；权限或同Run证据隔离被绕过；从错误/搜索摘要假装已取得全文；Report可凭空引用不存在ID；未获已登记Artifact却返回成功；网页 prompt injection 被当系统指令；取消后继续发新Provider请求；SQL并发超配额；P06数据/Checkpoint/取消/用量受破坏——任意一项需 STOP 并报告复现，不得降级安全要求。
- Demo 验收以**真实网络请求/数据库证据状态/Report Artifact/下载字节/Run ToolTrace**为准，模型口头说“我已搜索/已读页面”不算。不能因为没有 Tavily key 就临时开放公网 MCP、任意 Shell 或本地不受控抓取。
- 参考：[DeerFlow v2.0.0 deep-research SKILL](https://github.com/bytedance/deer-flow/blob/v2.0.0/skills/public/deep-research/SKILL.md)、[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract)、[OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)；API具体字段和异常类型由 Codex 以锁版 `httpx` + 实际 Tavily官方响应/Mock实测为准。


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
