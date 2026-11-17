# P07 · CONTEXT_BUDGET_EXCEEDED 专项修复｜进度

> **IN_PROGRESS（2026-11-17：A已完成局部验证，B/C/D实施中）**  
> 分支：`fix/p07-context-budget-exceeded`，基于 `feat/p07-deep-research` 远端 HEAD `72cae512fbdb31744a63084220b84df20bf8eda6`。  
> 任务书：[P07-CONTEXT-BUDGET-FIX.md](../tasks/P07-CONTEXT-BUDGET-FIX.md)。  
> 不改 P02–P07 已有人工审核状态；P07 仍 `PENDING_REVIEW`，本补丁修复完成后也需用户手动验证。

## 为什么需要专项修复

用户实测一个问题就发生 `CONTEXT_BUDGET_EXCEEDED`。代码静态核验确认：消息/工具以 UTF-8 JSON字节计入所谓“Token”估算，默认soft=12k/hard=18k；父代码可接配置而child `UsageBudgetMiddleware` 内还有固定18k限制；ContextManager只能在有先前完整用户回合时摘要，当前复杂P07一个Human下多组工具消息不能安全分段；另有Run累计估算120k独立上限。尚无用户真实失败Run日志，因此未知哪一项首先触发。

## 任务状态

| 任务 | 计划产物 | 真实状态 |
|---|---|---|
| A · 诊断与温和上调 | 请求成本细分/安全日志、父子一致阈值、前端明确单位、字节近似soft24k/hard48k/cumulative480k | TODO，没有代码/测试 |
| B · 同一用户问题内已完成Tool批次压缩 | 安全完整tool_call_id配对、保留当前目标与Todo/Evidence、分块摘要、Checkpoint/ToolTrace回归 | TODO，没有代码/测试 |
| C · 统一计数与版本化Token估算 | Provider Token vs token estimate vs 历史字节分列、窗口保守检查、兼容旧SQLite/Usage | TODO，没有代码/测试 |
| D · 长研究全链路与前端回归 | Fake低阈值真压缩、普通问答、Child并发、取消、Artifact下载、真实模型可用时低成本Smoke | TODO，没有代码/测试 |

## 设计已核对的真实文件

`backend/src/minideerflow/runtime/budget.py`、`agents/{middleware,context_manager,state}.py`、`runtime/{runner,usage,streaming}.py`、`agents/subagents/executor.py`、`tools/output_budget.py`、`config.py`、P06已有context/budget测试、P07研究Demo及React UsagePanel/RunStatus。仍保留P07研究证据真实ID/下载、P06取消/预算、P05 ToolGuard/Skills和P04 Todo/Child。新分支目前**只有设计文档**；没有独立执行项目的pytest、Ruff、前端构建或本地问题重现。

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
