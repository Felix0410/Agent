# P07 · CONTEXT_BUDGET_EXCEEDED 专项修复｜进度

> **PENDING_REVIEW（2026-11-17：A/B/C/D已实现并完成局部验证，待用户手动验收）**
> 分支：`fix/p07-context-budget-exceeded`，基于 `feat/p07-deep-research` 远端 HEAD `72cae512fbdb31744a63084220b84df20bf8eda6`。
> 任务书：[P07-CONTEXT-BUDGET-FIX.md](../tasks/P07-CONTEXT-BUDGET-FIX.md)。
> 不改 P02–P07 已有人工审核状态；P07 仍 `PENDING_REVIEW`，本补丁修复完成后也需用户手动验证。

## 为什么需要专项修复

用户实测一个问题就发生 `CONTEXT_BUDGET_EXCEEDED`。代码静态核验确认：消息/工具以 UTF-8 JSON字节计入所谓“Token”估算，默认soft=12k/hard=18k；父代码可接配置而child `UsageBudgetMiddleware` 内还有固定18k限制；ContextManager只能在有先前完整用户回合时摘要，当前复杂P07一个Human下多组工具消息不能安全分段；另有Run累计估算120k独立上限。设计阶段尚无失败Run日志；本次本机数值诊断见A记录。

## 任务状态

| 任务 | 计划产物 | 真实状态 |
|---|---|---|
| A · 诊断与温和上调 | 请求成本细分/安全日志、父子一致阈值、前端明确单位、字节近似soft24k/hard48k/cumulative480k | PENDING_REVIEW，真实结果见下方记录 |
| B · 同一用户问题内已完成Tool批次压缩 | 安全完整tool_call_id配对、保留当前目标与Todo/Evidence、分块摘要、Checkpoint/ToolTrace回归 | PENDING_REVIEW，真实结果见下方记录 |
| C · 统一计数与版本化Token估算 | Provider Token vs token estimate vs 历史字节分列、窗口保守检查、兼容旧SQLite/Usage | PENDING_REVIEW，真实结果见下方记录 |
| D · 长研究全链路与前端回归 | Fake低阈值真压缩、普通问答、Child并发、取消、Artifact下载、真实模型可用时低成本Smoke | PENDING_REVIEW，真实结果见下方记录 |

## 设计已核对的真实文件

`backend/src/minideerflow/runtime/budget.py`、`agents/{middleware,context_manager,state}.py`、`runtime/{runner,usage,streaming}.py`、`agents/subagents/executor.py`、`tools/output_budget.py`、`config.py`、P06已有context/budget测试、P07研究Demo及React UsagePanel/RunStatus。仍保留P07研究证据真实ID/下载、P06取消/预算、P05 ToolGuard/Skills和P04 Todo/Child。方案提交当时只有设计文档；本次独立执行结果见下方A/B/C/D记录。

## 实施时记录规范

每个A/B/C/D都必须在这里追加：实际完整提交SHA与是否推送、代码文件、只跑新增/直接受影响测试的命令与通过数、是否真实触发了同Run压缩、浏览器UI变化、Fake/Provider测试区别、既存运行限制、失败和停止条件。用户未验收不能擅自标ACCEPTED，更不能用临时抬高上限来代替B的压缩验证。

## 用户后续手动验收

1. 普通简短问答一条成功，且首次预算诊断可解释schema/system/history占用。
2. 同一个复杂研究问题在默认预算内完成至少一条来源证据和真实报告，不能捏造公网联网（若未配置Tavily仅Fake）。
3. 使用低阈值隔离Fake实测在**单一Human轮次内**压缩过去已完成工具批次，Graph/ToolMessage/Todo与真实Evidence ID都完好。
4. 确认子代理父Run共享预算、不重复统计；累计预算不足时仍然明确停止。
5. 页面显示估算单位和Provider真实统计分开，刷新/取消/重启与文件下载仍正确。

## A · 统一字节预算与脱敏诊断（2026-11-17）

- 基线为GitHub方案原始提交`f44735815e6e2d831723ef8783d6066af5b1e2df`。终端git fetch超时，通过GitHub连接器读取Git数据，逐个校验4个commit/tree/blob SHA后导入同一原始历史；没有改写远端或覆盖未提交修改。上一轮预览修复原样保留，临时备份`/tmp/minideerflow-budget-before-plan.patch`，不含.env。
- 原失败Run数值诊断：四条消息12554字节近似、公开工具Schema7568，两次工具结果7351/4032 bytes；该例是同Run中小回执合计超限，不是模型Provider窗口错误。
- 修改config/budget/usage/runner/context_manager/middleware/lead、.env.example、UsagePanel/RunStatus/runtime类型、新test_context_budget_fix。默认soft24000/hard48000/cumulative480000，父子不再隐含18k；System与Schema各计一次，过大固定开销不调用摘要。SQL预算JSON保存最后分项，仅数值、版本和枚举。旧estimated_input_tokens列仍为字节近似，不改历史含义。
- 局部：`pytest -q tests/test_context_budget_fix.py tests/test_config.py tests/test_budget.py tests/test_usage.py tests/test_context.py tests/test_budget_demo.py tests/test_research_tools.py tests/test_subagents.py`，**57 passed in 2.53s**；本次核心修改Ruff check/format通过，`npm run build`通过43 modules。Fake模型/Provider，不代表公网验收；不升级依赖。
- UI同步真实Token/字节近似单位、请求分项及预算错误说明；A不宣称已解决同Run压缩。提交SHA后续记录；未推送、尚未浏览器手测、未自动合并。

## B · 同一Human内完整工具块压缩（2026-11-17）

- A提交：`957bde9`。修改context_manager/middleware/usage、前端UsagePanel/runtime类型、新test_context_tool_rounds。
- 解析完整并行Tool Call批次，遇到未配对/重复/invalid调用即保留该批及之后；边界扩大以保留最近至少6条实际消息，原Human目标不替换。多轮旧边界保留。摘要连续数据片段最多8KiB，滚动摘要最多2KiB，逐批共享预算；完整处理、引用归属验证、最终硬预算复核后才返回RemoveMessage替换。工具失败状态另以可信数据保留，Todo仍独立状态。
- 真实`stream_agent`的messages+updates流累计当前Run工具消息，Graph压缩后8次ToolTrace/SSE ID依旧完整，无需修改流式实现。SQL追加本轮工具历史压缩次数，UI刷新后提示真实次数。
- `pytest -q tests/test_context_tool_rounds.py tests/test_context.py tests/test_budget_demo.py tests/test_research_demo.py tests/test_research_child.py tests/test_cancel_recovery.py`：**37 passed in 7.65s**；Ruff通过本次修改；前端build通过43 modules。
- 单Human八次工具调用用soft6500/hard14000真实触发压缩且成功，Todo/current goal保留；摘要空/>2KiB/超时/外部Task取消/多批累计预算耗尽均保留旧Checkpoint。最初直接在Fake节点raise CancelledError被锁版LangGraph转换为NodeCancelledError，已改成实际外部Task.cancel验证取消链，不吞框架行为。
- 模型与来源仍Fake，不代表公网/真实模型；真实P07报告+两个并发Child强制压缩全链在D核验。未推送，不修改用户旧Run。

## C · 版本化预估与兼容旧SQL（2026-11-17）

- B提交：`68bc55f`。新增ContextEstimator协议/ContextEstimate统一每请求System+Schema+消息计量，未知兼容模型采用明确标记的`utf8_conservative_v2`（每UTF-8 JSON代理字节一Token的保守预估，不使用英文4字节/Token去放宽中文输入），不声称精确Tokenizer或Provider窗口保证；原字节硬限额始终独立生效。
- Settings可选已确认的MODEL_CONTEXT_WINDOW_TOKENS和输出预留；未知窗口不猜模型规格，已配置时同时检查保守预估+输出预留。父/Child/summary使用相同tracker预扣，累计预算仍为同单位字节预算，不拿旧版本历史跨单位比较。
- run_usage/usage_calls幂等新增nullable v2/版本列及已覆盖调用次数，旧行保持NULL，历史estimated_input_tokens字节总量不变；Provider缺usage仍NULL、唯一ID回执去重。前端同时明确显示字节v1、保守Token预估v2及Provider真实Token。
- `pytest -q tests/test_context_estimator.py tests/test_context_budget_fix.py tests/test_context_tool_rounds.py tests/test_budget.py tests/test_usage.py tests/test_budget_demo.py tests/test_config.py tests/test_context.py tests/test_cancel_recovery.py`：**60 passed in 7.76s**，包含实际删除新列构造旧库并迁移两次、中文/英文/长JSON、窗口拒绝、未知窗口回退及并发累计预扣。Ruff导入顺序问题已修复，format通过；前端build通过43 modules。未新增库或修改锁文件。
- 可回退为独立C提交；旧字节列不受回退影响。本轮尚未浏览器/真实模型验收，进入D。

## D · 研究全链、浏览器和真实模型核验（2026-11-17）

- C提交：`391dc53`。新增test_context_research_flow，以MockTransport执行固定Tavily API真实请求转换，Fake模型驱动单Human→Todo→Skill目录/读取→Search→Fetch→两个并发Research Child→两轮Evidence→真实报告Artifact→Todo完成；默认预算和人为soft12000/hard24000均成功，低阈值确实触发本轮压缩。15条真实合成证据/3条EXTRACTED、两个Child COMPLETED、完整11条父ToolTrace；父11+子6+摘要逐次计数，无重复账。
- 保留并纳入上一轮研究回执预览修复及测试：按UTF-8缩短title/snippet/excerpt、单回执最多3KiB；全部证据ID/等级保留，超长URL不伪造或截成假地址，完整记录仍在SQL/API。通用12KiB外置及Child写权限不变。补齐摘要invalid Tool Call拒绝、取消调用记为cancelled、最近不可压缩工具批次保守失败。
- 直接相关回归命令（backend，未跑P08/P09）：

```bash
.venv/bin/pytest -q tests/test_context_budget_fix.py tests/test_context_tool_rounds.py tests/test_context_estimator.py tests/test_context_research_flow.py tests/test_budget.py tests/test_usage.py tests/test_budget_demo.py tests/test_context.py tests/test_output_budget.py tests/test_cancel_recovery.py tests/test_runner.py tests/test_repository.py tests/test_runs_api.py tests/test_task_registry.py tests/test_tasks_api.py tests/test_events.py tests/test_todos.py tests/test_subagents.py tests/test_tool_guard.py tests/test_planning_demo.py tests/test_tools_demo.py tests/test_mcp.py tests/test_skills.py tests/test_file_tools.py tests/test_files_api.py tests/test_workspace.py tests/test_config.py tests/test_checkpoint.py tests/test_research_tools.py tests/test_research_child.py tests/test_research_demo.py tests/test_research_report.py
```

- **336 passed in25.60s**。随后针对摘要invalid Tool Call、取消记账、不可压缩近期工具批次补充变更，局部`test_context_tool_rounds/test_context/test_context_estimator/test_context_research_flow/test_cancel_recovery`：**35 passed in7.50s**。最终本次14个Python文件Ruff check/format通过；uv lock --check通过78依赖；前端build通过43 modules，无新依赖/锁变化。各次数字有重叠，不累加为测试总量。
- ego-browser TaskSpace1，隔离8017、临时两库/Workspace、前端生产构建，用户原服务未修改。浏览器Run `edfd964c-d30c-45f9-b265-d19cfea9d874` SUCCEEDED，24模型/15工具、7次本轮压缩、累计196968字节近似；Provider统计为未知。页面明确显示字节v1/Token保守预估v2/Provider真实Token、分项及7次压缩；刷新重新选择会话后数字一致。两个Child和Todo完成，15条来源可查。
- 报告页面查看1371 bytes，浏览器下载与HTTP下载相同，SHA256 `9be5cfb55b1497d1ef5ac7c7e20ed2dcda3a38344843c44a255e50a776d237d7`。MutationObserver实际观察“正在取消”后CANCELLED，旧会话需恢复，不自动重放。SQL重开后来源/Usage/Artifact字节恢复另有HTTP测试。页面截图`/tmp/minideerflow-budget-usage.png`已实际查看；报告/脚本也在/tmp，不进入Git。TaskSpace已finish，隔离服务已关闭、临时库/Workspace清理。Ego Lite提示有更新，本次未升级。
- **真实模型+Mock来源分开核验**：普通合成问答SUCCEEDED，1模型/0工具，Provider输入1547/输出4，估算8719字节；精简研究SUCCEEDED，4模型/3工具（Search/Fetch/Report），Provider输入10271/输出916，估算49184字节，实际报告已保存。合计5模型、真实Provider输入11818/输出920。全程独立临时两库/Workspace，结束清理；MockTransport不出公网，不声称实际Tavily或费用账单验证。
- `.env`只更新CONTEXT_SOFT_LIMIT_ESTIMATE=24000、CONTEXT_HARD_LIMIT_ESTIMATE=48000、RUN_MAX_INPUT_TOKENS_ESTIMATE=480000；其余内容保留，未写入密钥或猜测模型窗口，.env被Git忽略。README与前端说明已同步。原P07进度中的上一轮局部修复记录保留为历史。
- 中文注释覆盖消息块成对边界、字节/Token版本、引用验证、摘要分块原子替换、旧SQL增列、取消语义和真实统计展示。未修改System提示词、工具描述、权限或引入另一Agent循环。
- 未验证：真实Tavily公网来源/主张支持度、用户手动验收、PyCharm GUI/其它OS。已有FAILED/旧Checkpoint不迁移或自动重放；新建会话测试。P02–P07审核状态不变，不合并main，不进入P08。Git提交/远端交付见下方记录。

## Git交付核验（2026-11-17）

终端Git HTTPS连接超时，使用GitHub连接器逐对象上传，blob/tree SHA均与本地阶段内容核对一致；远端分支从方案提交`f44735815e6e2d831723ef8783d6066af5b1e2df`正常快进4次，已用compare确认ahead_by=4、behind_by=0。没有强推、改写共享历史、合并main或发送评论。

| 阶段 | 本地实现提交 | GitHub交付提交（内容tree相同） |
| --- | --- | --- |
| A | `957bde9e3e1c604c27c908d90410ed323761c7ef` | `7e00da7c8acca7f07c41fdd1806d55a04c29134d` |
| B | `68bc55f71ae5ab1fd9d30e278b505efdd9e79177` | `e3d3394466ab8ebb185429cd37721c0e52549cde` |
| C | `391dc53abf41a4b598ae6aaea47e467730c76c19` | `850376dfa485cc9705749903fafe58791f49cdd7` |
| D | `aa791d68acb4bbbb5da9dc5e7d7f938158282b4f` | `8ce99b765a666cdc5a562437cdf1838a07b16903` |

连接器创建提交时使用服务端作者/时间，因此提交SHA与本地实现提交不同，代码tree完全一致。本地原实现历史保留在`local/p07-budget-implementation-20261117`备份分支；当前修复分支在核对内容后与GitHub交付历史对齐。此记录另作纯文档提交。

本机8000原监听已停止，现已使用backend/.venv与新代码启动后端，启动/实际旧库幂等迁移成功，GET /health=200；加载.env的soft/hard/cumulative实际为24000/48000/480000。没有重放已有Run。最终补充35项局部测试再次通过（7.37s），14个Python文件Ruff check/format及最终diff空白检查通过。

状态仍为PENDING_REVIEW；真实Tavily公网、人工验收、PyCharm GUI和其它OS未验证。所有源码/测试/文档变更扫描未包含.env真实认证值；.env/生成库/Workspace/dist仍为Git忽略内容。
