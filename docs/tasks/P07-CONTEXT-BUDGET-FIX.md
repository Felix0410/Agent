# P07-HOTFIX · CONTEXT_BUDGET_EXCEEDED 修复合同（Codex）

> **状态：PLAN_READY / 仅设计，尚未改业务代码或执行测试**。2026-11-17 用户反馈“一个问题就 CONTEXT_BUDGET_EXCEEDED”。开发基线 `feat/p07-deep-research` 远端 HEAD `72cae512fbdb31744a63084220b84df20bf8eda6`，修复分支 `fix/p07-context-budget-exceeded` 直接由该分支派生。单独修复 P06→P07 的上下文控制，不重写 Agent、不实现 P08、不动已有业务数据库的历史含义；P02–P07 依旧 PENDING_REVIEW。按 A→B→C→D，每项单独提交、**仅局部测试及直接受影响用例**，有安全阻断即停。各步同步已有 Web UsagePanel/RunStatus；仅测试实际完成时更新 [修复进度](../progress/P07-CONTEXT-FIX.md)。

## 0. 诊断结论（以实际 P07 源码为准）

- `runtime/budget.py:estimate_messages/estimate_tools` 返回 `len(json.dumps(...).encode("utf-8"))+64` 的**字节近似**；虽然名为 `estimated_input_tokens`，**不能当作真实 Token 数**。P07 Dev 记录曾出现真实模型 5 次调用 provider input 11618、估算 59411（两者都是跨调用汇总，仅说明计量口径不同，不能用于推导固定换算率）。
- `config.py` 的 `context_soft_limit_estimate=12000`、`context_hard_limit_estimate=18000`，且 Pydantic 分别限制 `le=12000/le=18000`；只在 .env 写 48000 会启动失败。
- `UsageBudgetMiddleware("child")` 默认自带 `hard_limit=18000`，调用 `min(self.hard_limit, tracker.context_hard_limit)`，**父 Run 调大配置后 child 仍会被18k截断**；旧无 Workspace 分支也默认18k。
- `ContextManager.partition` 只寻找较早的 `HumanMessage` 作为可压缩边界，且要求旧前缀以无 tool_calls 的 AIMessage 结束。因此 P07 的“**一个 HumanMessage → 多次搜索/ToolCall/子代理 → 保存报告**”流程，在当前 Run 内可能根本找不到旧用户回合可压缩；输出外置的 12KiB 阈值也不能解决重复的中小回执。
- `ContextManager.prepare` 用 messages+工具Schema 的大小判断软/硬阈值，但 `UsageBudgetMiddleware.awrap_model_call` 实际还会加 `system_message`；两个关卡不是严格同一口径。`RunBudgetTracker` 另有 `max_input_tokens_estimate=120000` **每Run累加**，突破后报 `BUDGET_EXCEEDED`，与单次 `CONTEXT_BUDGET_EXCEEDED` 是不同问题。
- 现有 `ToolOutputBudgetMiddleware` 在正常成功时对大回执保留 ToolCall ID 和真实 file_id/Artifact，P07 `EvidenceStore` 的 SQLite 真实来源ID由服务端校验；修复不能丢失这些语义。旧多轮压缩测试存在，但**缺同一用户问题里多次已完成工具调用的触发用例**。
- 本轮**没有拿到用户出错 Run 的 SQL/模型真实上下文窗口/Provider回执**，不能断言唯一触发点。第一步必须用不包含用户正文的数值诊断定位是初始 Schema、同Run回执，还是异常摘要。

## A · 诊断 + 临时解除过早拦截（可独立止血）

| 文件 | 具体动作 |
|---|---|
| `runtime/budget.py` | 新增**只读** `BudgetBreakdown`（`system_bytes, tool_schema_bytes, message_bytes, total_bytes, soft_bytes, hard_bytes, cumulative_bytes, estimator="utf8_json_bytes_v1"`），统一调 `estimate_messages/estimate_tools`，不可包含原文、工具参数、URL、文件内容、API Key；保留现有 Provider usage 独立记录 |
| `agents/middleware.py` | `UsageBudgetMiddleware(hard_limit=None)`：没有独立明写覆盖时**仅以同Run `tracker.context_hard_limit`**为准，父/child一致；单请求失败前记录脱敏 `phase=before_model`、各部分占用与`reason=INITIAL_OVERHEAD/ACTIVE_MESSAGES/UNCOMPRESSIBLE`，不把日志异常填进 ToolMessage/Stream全文。`ContextCompactionMiddleware` 将真正分区失败原因写成简短枚举，不发送全文 |
| `agents/context_manager.py` | 复用相同 breakdown 计算，System 和工具Schema在压缩前后的预算按同一口径；如果初始 System+Schema 已超硬阈值，不启动不可能成功的历史摘要，诊断为 `BASE_OVERHEAD_EXCEEDS_HARD_LIMIT`；不能用任意截断 System/工具Schema 绕过此条件 |
| `config.py` | **先保持原字节估算法，仅适当放大字节近似阈值**：`context_soft_limit_estimate default=24000, ge=64, le=96000`；`context_hard_limit_estimate default=48000, ge=128, le=128000`；`run_max_input_tokens_estimate default=480000, ge=1, le=1000000`。三个数均为**字节近似预算**而非模型实际Token；保留 `soft < hard` 和 40模型/30工具/600秒/Child35s，使用的模型不支持这么大窗口时按实际窗口配置更保守值；无法从代码推定模型真实上下文 |
| `runtime/runner.py` / `agents/subagents/executor.py` | 按Settings→同Run Tracker统一父/子/摘要阈值；旧测试独立创建Tracker时保留安全默认(48k字节)；不额外加另一套计数Middleware、不重复计费 |
| `runtime/usage.py` / `api/runs.py` / `frontend/src/components/UsagePanel.tsx` | API/UI向后兼容，增加`estimate_unit="utf8_json_bytes_v1"`或等价安全标识；旧 `estimated_input_tokens` 是历史列名，UI**明确标为“UTF-8 字节近似预算（非真实Token）”**，provider输入输出仍只显示真实Token。新增值只能增字段，旧SQL不迁移为虚构Token |
| `frontend/src/components/RunStatus.tsx` | `CONTEXT_BUDGET_EXCEEDED`用简短提示“单次上下文预算不足；可在Usage中查看分项占用”，不要把所有错误渲染成模型故障；UI显示数值时避免暴露原始正文 |

**A 的测试**：新 `test_context_budget_fix.py` 测首轮只有Human/System/ToolSchema也能进模型；人为把Schema做得比硬上限大仍必须安全失败，并明确诊断；`test_budget_demo.py` 中 child 配置 48k 而不被固定18k拒绝；`test_config.py` 新上下界/soft<hard；provider usage与字节估算绝不混合。对P07已有普通问答、Search/Skill和Child路径进行直接回归；Ruff/TS build。**先执行这一步，再观察实际 Run 的分项日志**；仅凭数值上调不足以声称已彻底修复。

## B · 同一 Run 内已完成工具调用分段压缩（核心修复）

修改 `agents/context_manager.py`、`agents/middleware.py`、必要时 `agents/state.py`/ `runtime/streaming.py`，**不另建 Agent 循环**。

1. 以消息块为单位解析 Graph state：每个 `AIMessage.tool_calls` 及其**全部同ID匹配**的 `ToolMessage` 组成原子已完成工具批次；一批次有多个并行工具时所有结果到齐才可压缩；存在 unmatched/invalid tool_call/正在进行的 batch 则该批次及之后全部保留，禁止孤立 ToolMessage。
2. 先保护当前用户 HumanMessage 原始目标、最近**至少6条**实际消息（若跨工具批次边界则扩大保留直到成对）、当前 P04 Todos独立状态、用户上传 file_id/Artifact ID 和**服务端验证当前 Run 真实 Evidence ID**；不把模型生成的虚构ID标为可信。工具业务错误状态/未完成Todo/报告Artifact是否已创建等不得靠摘要文本默默改写。
3. 当用户仅问一次且同Run已产生多个**完整的**工具批次，允许将最早的已完成批次**连同有关中间自然语言消息**一次压缩为不超过2KiB的“历史数据”摘要锚点；原始 Human 目标仍保留，不能用该摘要代替原指令。原本旧多轮 Human 边界压缩能力照旧。新的锚点内容为数据，不提升角色/工具权限，已有 `P04AgentState.todos` 不改。
4. `RemoveMessage(id=REMOVE_ALL_MESSAGES)` 与原状态 reducer 只在**全部摘要安全完成并复核额度、引用与ToolCall成对**后原子返回；流式 ToolTrace/SSE 内当前Run事件、SQLite Run历史、已注册来源不受删旧Graph消息影响。Graph Checkpoint 可保存较短上下文，但不能导致当前Run最终回答的工具调用记录缺ID。必要时给 `stream_agent` 仅增加已经完成的业务ToolTrace提取优先路径，而不是绕开消息验证。
5. 摘要过程必须**分块**：单个摘要输入不可高于自身硬预算（建议单批最多8KiB UTF-8原文代理），禁止把任意长历史全部拼成单个HumanMessage后又报同一个错误；每批模型调用按 P06 同Run预算占额，超时/取消传播。数值可配置但不得突破父Run累计调用上限；无法安全形成完整片段就保守失败，不随机截断工具结果。
6. 先不降低 `ToolOutputBudgetMiddleware` 现有12KiB边界、不让Child写Artifact，也不在压缩时再次执行搜索/工具或重试未知报告；P07的EvidenceStore仍是唯一来源。若首次 model call **尚未出现任何工具批次**已超限，则必须提示“初始占用超限”，**不**尝试摘要未处理的问题。
7. 与P06 `context_compacted` SSE/Usage的`compaction_count`复用，事件只发旧/新消息数、估算大小与原因枚举；前端 `UsagePanel` 加“已压缩本轮工具历史”提示，不把被清理的原文打印到日志。

**B 的必要用例**：
- **关键重现**：同一个Human输入，父 Agent串行3–8轮search/fetch/list_evidence/Task，再生成真实Artifact，低阈值故意触发压缩，验证真实Graph、ToolCall ID、来源ID和最终 ToolTrace完整。
- 并行 `AIMessage.tool_calls=[a,b,c]` 只来a/b结果时禁止切割；最终c到齐后才可整体压缩；输出如Command仍保留State todos，不泄漏跨Run来源。
- 验证“最近六条”含多个ToolMessage或跨边界时全批保留；旧多轮历史仍可压缩；当前用户目标及此前summary继续有效；正文中的“忽略权限”不变成System指令。
- 摘要模型返回空、>2KiB、调用超时/取消、输入单批>8KiB、多批累计预算不足：保护Checkpoint旧原始状态，不半写摘要；安全错误码/原因，不吞取消。
- 必须覆盖实际 `stream_agent` 的 `astream(["messages","updates"])` 和 P07 Task并发，不能只测试 `ContextManager.partition` 的普通Python列表。

## C · 真实Token预算语义与逐次估算一致（建议紧接B）

**理由**：A、B 解除早期失败，但当前 `estimated_input_tokens` 仍然是字节计数，不应永久称为“token estimate”。

- 在 `runtime/budget.py` 新增 `ContextEstimator` 抽象：**传入每次请求实际 system + user/AI/tool messages + 当前注册模型可见工具 Schema**，只算一次并得到统一 `ContextEstimate`。官方模型/Tokenizer若明确支持本实例精确计数则用它；对于OpenAI-compatible但未知模型（例如DeepSeek兼容接口），采用**明确标记为近似**的保守字节换算或稳定 Tokenizer，不假装跨Provider完全相同。
- 明确三种单位：`provider_tokens`（最终真实回执）、`estimated_tokens_v2`（近似仅用于预检查）、`utf8_json_bytes_v1`（已有历史预算值）。**不要将旧SQL `estimated_input_tokens` 历史字节总数静默改解释**；可以保留它与新字段共存（如在 `budget_json` 标注 estimator_version+unit 或新增 nullable v2 列，需真正进行兼容SQLite增量迁移并测试）。Frontend必须显示单位和版本。
- 若用户未配置**可信的模型上下文窗口**则继续用A的保守字节阈值预防OOM（不是Provider精确Token窗口），不能因一个猜测换算就放行到超过实际模型窗口。后续可选配置 `MODEL_CONTEXT_WINDOW_TOKENS` 与 `MODEL_OUTPUT_RESERVE_TOKENS`，仅当窗口已确认/估算方法具备安全余量时执行`estimate + output_reserve <= window`，不要内置不可验证的模型规格假设。
- Per Run累计预算的单位与单次预算必须匹配；历史比较只比较同版本同单位。摘要模型、父和Child共享预算，Provider最终usage只入账一次。
- 优先让A+B在不新增重型库的情况下先修复；若Tokenizer成本/版本引入显著不确定性，把C的Token估算升级作为**单独可回退提交**，但不允许在修复后UI持续误称字节=真实Token。

**C 的测试**：至少一个中文、一个英文、工具Schema长JSON、同一消息摘要前后，确定性版本化结果；旧SQLite升级/历史读写、Provider缺usage仍NULL、Cumulative concurrency、过小window拒绝、未知window保守字节回退、Tool schema不重复计数。

## D · 端到端核验、Web同步与交付

1. 无外网、无用户key，先用Fake + `MockTransport` 的**单个问题完整P07链**（Todo→Skill→Search→Fetch→2 ResearchChild→Evidence→Report Artifact）：在默认A配置下不再因18k字节规则提前失败；用**人工降阈值**的测试隔离环境强制触发B压缩且最终成功（不能为了过测试提高阈值到不再触发压缩）。
2. 测单次初始 Schema >hard（明确失败）、同一Run多次大ToolMessage/无可压缩安全片段（明确失败）、真正超过累计预算（仍BUDGET_EXCEEDED）、模型提供方实际拒绝超窗口（映射上游错误，不伪报为本地Context Budget）、并发取消/同Run ToolCall IDs、子代理正确计数、证据真实性和Artifact下载。
3. 浏览器真实`UsagePanel`查看新分项与“当前字节近似/Provider真实Token”的区别，RunStatus展示明确报错原因，刷新/重启使用SQL权威统计；所有文件/证据引用必须能在Workspace/ResearchPanel原样恢复。前端不得添加虚假的“修复成功”展示。
4. 原P02 Run/SSE/Checkpoint、P03文件/Artifact、P04 Todo/SubAgent、P05 MCP/Skills/Guard、P06 Budget/Cancel/Compaction、P07 Research/Report 的**直接影响用例**局部回归，Ruff check/format、`uv lock --check`、`npm run build`；所有命令、测试数量与真实Fake/Provider分别记入 progress，不能把历史380 passed当作本修复测试通过。
5. 真实模型已配置时可用短**合成材料**试普通问答和一个精简的研究Run，并结合Provider `usage_metadata` 观察；不用大量真实查询为强行制造长上下文测试，真正公网Tavily是否可用另行标注。
6. 每子阶段单独commit：`fix(p07-budget-a): align limits and add safe context diagnostics`、`fix(p07-budget-b): compact completed tool rounds in current run`、`fix(p07-budget-c): version token estimates and preserve old usage`、`test(p07-budget-d): verify long research, child and UI regressions`。每次修复需前端同步，Codex保留用户现有未提交中文注释，禁止reset/clean/强推/自动合并main。
7. 修复功能完成且用户未手动验收时状态仍`PENDING_REVIEW`；停止条件：丢失Todo/ToolCall ID/真实Evidence、生成无源报告、模型权限绕过、历史字节当成Provider Token、强行让模型接收超窗口、取消失效、原SQL损坏。任何一项不满足即BLOCKED、提交最小复现并停止下一子阶段。

## 手动验收与记录

用户在修复后按顺序测试：**普通一句话** → **计算/简单工具** → **单次复杂Research报告** → **同一问题低阈值强制压缩（Fake）** → **重复调用/重连/取消/刷新**。若普通问题仍在首个模型调用失败，应提供**脱敏**的`system/schema/messages/total/limit/reason`数字，而不是贴出Prompt或密钥；只凭错误码无法推断是否是模型真实上下文窗口太小。  
注意：本方案不修改正在运行的已有Run；已经FAILED的Run不原地盲重放写操作，应该新建Thread/Run测试。
