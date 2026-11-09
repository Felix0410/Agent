# P07-A/B/C/D · Deep Research —— Codex 逐文件编码合同

> **设计完成，不代表已编码。** 源分支 `feat/p06-context-budget-cancel`（2026-11-09 最新注释 Commit `f291af58`），目标分支 `feat/p07-deep-research`。严格按 [P07 正式规格](../DEVELOPMENT.md) 编码。本地 Codex 不重新确定业务/技术选型、不引入第二套 Agent/Queue/StateGraph、不扩大公网 MCP/任意 Python/Shell 权限。用户“可以开始p7了吗”指进入此阶段的设计与受控推进；本期编码开始前必须先过质量门槛。各阶段 A/B/C/D 独立测试/Commit、同步前端，关键失败停止并上报。P02–P06 保持 PENDING_REVIEW，不自动视为人工通过。

## P07-0 · 代码质量与分支预检（在 A 之前）

1. `git status -sb` / `git branch -vv` / `git log -6 --oneline` / `git fetch origin` 确认目标分支起于 P06 完整实现。不可删除用户改动、reset、force-push、自动合 main。
2. 检查最新 P06 注释提交 `f291af58`：已观察到一处行尾空格、main.py import blank-line 排版变化，多个 `# noqa: BLE001` 消失。依次执行 `git diff --check HEAD~1 HEAD`、backend `uv run ruff check src tests examples`、`uv run ruff format --check src tests examples`、`uv lock --check` 和 frontend `npm run build`，仅修改格式/注释问题并在 P07 分支单独提交 `style: restore baseline formatting before P07`；**不能更改原本 Tool/Run 状态逻辑或擅自声称 P06 人工验收通过**。
3. Codex 如不能保留原用户本地未提交修改，必须 STOP 并报告状态；若 P06 局部回归失败，先定位是否格式改动造成，不得绕过测试直接实现联网。
4. 确认 `backend/src/minideerflow/{runtime/runner.py,agents/context.py,agents/subagents/{config,dispatcher,executor}.py,tools/{registry,executor}.py,skills/loader.py,workspace/service.py}` 的真实签名、原 P06 预算/取消/长结果和 ToolGuard Middleware 次序；子代理当前不能联网，这不是已实现的 P07 功能。

## A · Tavily Search/Extract、真实 EvidenceStore、基础研究面板

**逐文件责任**：

| 文件 | 必须完成 |
|---|---|
| `research/models.py` 新 | `SearchHit/EvidenceRecord/ResearchRequest/ResearchFinding/ResearchReport` 严格 Pydantic 限额、`SNIPPET_ONLY/EXTRACTED/EXTRACTION_FAILED`，不得将摘要写成verified全文 |
| `research/urls.py` 新 | 从 Tavily结果提取正常http/https公共 URL，拒绝 userinfo、私有/loopback/link-local/奇异端口/不支持scheme；规范化 URL 去重，绝不调用这些地址的本机 HTTP GET |
| `research/provider.py` 新 | 复用现有 `httpx`；固定POST `https://api.tavily.com/search` / `https://api.tavily.com/extract`，Bearer SecretStr，不设用户 URL 覆盖、不跟随302、禁环境代理；12s以内、响应字节上限、Search只 max_results=5/basic/无raw content；Extract检查 `results/failed_results` 的真实对应URL；错误脱敏，无自动重试 |
| `runtime/db.py` 改 | 新增 `research_requests`、`research_evidence`、`research_reports`，约束/索引/兼容旧SQLite。不触碰已有 P06 CHECK 或业务数据 |
| `research/repository.py` 新 | SQLite事务按run同一时刻原子占位每Run search6次/extract8次、最多30 evidence、URL唯一、同 Run/Thread权限；终态和孤儿 UNKNOWN，不自动网络重试 |
| `research/service.py` 新 | 协调 Provider+SQL+取消/共享 Tracker，查询者身份来自真实 Context；DB commit后发布轻量事件；search 返回真实 evidence ID、fetch 仅接受同Run证据ID；失败能查询状态 |
| `tools/research_tools.py` 新 | `search_web(query)`、`fetch_webpage(evidence_id)`、`list_evidence()`，真实 `ToolRuntime` 注入Context，模型 Schema 不能含 run_id、thread_id、service或key；ToolMessage有真实证据ID、状态、有限摘要 |
| `agents/context.py`、`tools/registry.py`、`runtime/runner.py`、`main.py` | 可选注入ResearchService、在freeze前仅配置Tavily时注册Lead三只读研究工具；无Key时不注册并标research unavailable；其他P05内置/MCP/Skills保留 |
| `config.py` / `.env.example` | `TAVILY_API_KEY` 为SecretStr可选，无测试真实key提交，固定Tavily地址，拒绝模型指定外网服务地址 |
| `api/research.py` 新 | `GET /api/research/status`、`GET /api/runs/{run_id}/research/evidence`，无报告A期返回null；不存在run404，任何字段无key或完整正文 |
| `frontend/src/api/research.ts`、`components/ResearchPanel.tsx`、`RunStatus.tsx`、`App.tsx` | 当前和历史Run里显示真实搜索证据/来源类型、未配置状态/刷新；事件`research_search_completed/research_evidence_updated`实时更新，Run完成/重连GET补齐；不渲染未经清理的HTML |
| `tests/test_research_provider.py` / `test_research_urls.py` / `test_research_repository.py` / `test_research_tools.py` | MockTransport + 临时业务SQLite/Workspace + Fake Agent真实ToolNode，确保无key/超时/HTTP429/恶意URL/假Evidence/同URL/并发6/8/30限额与上下文安全 |

**A验证**：简单问答不触发Search；有FakeProvider时Lead执行真实ToolCall后SQL和React显示ID/状态；没Tavily Key时禁用且原能力不变。合法Extract返回正文时从SNIPPET_ONLY→EXTRACTED，失败则EXTRACTION_FAILED。禁止直接本机GET任意模型URL。局部research tests +直接影响`test_tool_guard.py/test_runner.py/test_config.py/test_workspace.py/test_skills.py`、Ruff、前端build；提交A SHA与进度。失败不得进入B。

## B · Research Child 的受控联网与父子共享证据

- 修改 `agents/subagents/config.py`：General维持 `calculate/list_files/read_text`；Research在ResearchService有效时额外拥有 `search_web/fetch_webpage/list_evidence`。固定默认研究Prompt描述真实网络来源和未核验界限，**离线条件仍保留P04的“没有网络”限制**，不让模型自行声称“我已搜索”。
- 修改 `agents/context.py`、`dispatcher.py`、`executor.py`：ChildContext携带**可选可信research_service和只读tool_policy**；选出的全部child工具来自父Registry快照与角色白名单交集；不传parent所有messages、没有child Checkpointer、不得重新委派或write/report/Skill/MCP。
- 修改 `tools/executor.py`：ToolGuard明确允许可信ChildContext的`read`工具，只在真实Run/Thread和Policy都匹配时执行；所有P04/P05父图ToolRuntime/Command继续原样。
- 修改child middleware装配：加 ToolGuard **就要移除ChildToolBudgetMiddleware**，用P06 RunBudgetTracker在ToolGuard里只计一次；父子共用Usage/取消标记，子代理读证据/配额并发由数据库事务保证。
- 测试 `tests/test_research_child.py` 和直接影响`test_subagents.py/test_task_registry.py/test_tool_guard.py/test_budget_demo.py/test_cancel_recovery.py`：两个并发Child各收集同一Run不同证据，跨Thread/Run Evidence拒绝，General不会看到search，child不能save_report/write_text/task，真实工具次数不双记，父取消后不继续Search/Extract、未确认provider请求不重试，Research role35s限制有效。
- 更新ResearchPanel显示子代理检索到的真实证据；Ruff/npm build，提交B SHA。

## C · Deep Research SKILL.md / 结构化报告 / Artifact

- 新增 `research/report.py`：只接受标题(1–120)、有限的`findings:[{claim(1–400),evidence_ids(1–5)}]`（最多12条）及 limitations(最多8条，合计≤2000字符)，从 **当前Run SQLite EvidenceStore** 验证每个来源；服务器排序生成 `[1]` 等编号、方法/检索时间、正文已提取或仅摘要、冲突与不足；无证据的结论不得装成已核验。禁止直接让模型提供裸Markdown和自定脚注。
- `tools/research_tools.py` 增 `save_research_report`，只有Lead可见、ToolPolicy write，未取消且Run RUNNING；使用现有 `WorkspaceService.write_text` 创建唯一 `research-report-<uuid>.md` Artifact（非模型可指定路径），再事务登记 `research_reports` 的artifact_id；一个Run一份。登记失败不能误报成功或自动重写。
- `backend/skills/public/deep-research/SKILL.md`：YAML含 `name: deep-research`、`description` 和 `allowed_tools` 真实必需前置工具 `search_web/fetch_webpage/list_evidence/save_research_report`；方法：不强制普通问答、先分主题Todo、真搜索、取正文、比较冲突、写结论和未核验、真实报告；不会指示安装新工具或扩大权限。
- `api/research.py` 补GET报告；`frontend/src/components/ResearchPanel.tsx` 显示真实引用和Artifact下载，与 P03现有下载API一致；SSE `research_report_created` 只发ID。
- 测 `tests/test_research_report.py` 和`test_research_demo.py`，伪造URL/id/跨Run、只有snippet、真实Extract、空报告、语义不支持自动断言为真、Markdown HTML注入防护、重复生成、取消时已提交Artifact与报告SQL关联失败以及sha/hash下载。Ruff/frontend build并提交C SHA。

## D · 真实网络与模型、UI、取消和既有功能联调

1. Fake真实Graph全程：用户消息→P04 Todo→P05 Skill list/read→Lead search→两个Research Child通过真实ToolRuntime分别search/extract→同Run EvidenceStore归并→Lead save_research_report→真正可下载Artifact；P06预算/取消/Checkpoint、P03旧文件与P05 MCP/off都保持。
2. 提供方SDK/HTTP兼容性：默认无`TAVILY_API_KEY`全部Mock tests不碰网络。若用户已提供本机Key，**只做一轮小规模联网Search/Extract Smoke**，固定测试主题、max_results≤5，记录真实request/响应状态和最终 Evidence ID，不打印 key/全文/认证头、不过多消耗额度。无Key则真实公网E2E标`NOT_RUN_EXTERNAL_DEPENDENCY`，不得假称已联网通过。模型真实Tool Calling 另与Mock分开记录。
3. 独立浏览器观察搜索来源、Snippet/Extract区分、ToolTrace/子任务/报告下载/刷新/服务重启；无key显示禁用；高风险URL被拒、网络失败能正常退化而不伪造引用；注入假“系统指令”的网页文本不会影响ToolPolicy/注册表或触发越权写操作。
4. 只对本阶段新增/修改与 P01–P06直接消费者跑局部pytest、`uv lock --check`、Ruff check/format（已经P07-0恢复基线）、`npm ci && npm run build`；记录四SHA、实际测试数量、实际提供方请求和未知费用。整阶段为 `PENDING_REVIEW` 交用户手动验收，**不自动进入 P08**。

## Codex 交付边界

- 不实现直接URL抓取、不提供模型动态公网MCP/任意链接下载/文件系统Shell/浏览器自动化，也不做PDF RAG或Embedding。
- 默认不联网；不会为没配置Tavily的用户偷偷换提供方。Tavily Search/Extract 都是有可能计费的外部请求，未知实际价格不能虚构；P06模型Token与Tavily服务成本分别记录。
- 搜索命中仅证明Provider返回URL，Extract只证明Provider报告获取正文，均不等于事实经过独立核实。报告中的每个citation都来自当前Run、已记录来源，模型生成的内容仍须人工抽查是否与来源相符。
- 任何违反ToolPolicy/Child只读/预算/取消/SQLite隔离、绕过证据ID、未登记Artifact却声称已生成、输出不可信HTML、Source注入覆盖System Prompt时应 STOP，附最小复现与当前SHA。中文注释突出“机制和风险”，长逻辑按1/2/3分段，不要机械为每行代码写无意义编号注释。
