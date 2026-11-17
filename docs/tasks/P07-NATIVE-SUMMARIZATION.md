# P07 稳定性重构：移除自研上下文硬预算，采用 LangChain 原生自动摘要

> **设计完成 / 代码未实施。** 2026-11-17 用户连续两次提问就遇到预算失败。基线分支 `fix/p07-context-budget-exceeded`；本阶段新分支 `refactor/p07-native-summarization`。在本分支编码并完成连续对话实际测试前，不将问题标为修复，不改变 P07 的 `PENDING_REVIEW`。用户明确希望删除反复误阻断正常对话的预算机制，**不要把本任务写成再次调大 48k/480k**。

## 1. 决策与原版参考

经 GitHub 核对 DeerFlow `v2.0.0`：
- `config.example.yaml` 启用 Summarization，`trigger=("tokens",32000)`、`keep=("messages",10)`、`trim_tokens_to_summarize=15564`（示例值，**不可不顾模型实际窗口照搬**）；
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py` 根据配置构造 `DeerFlowSummarizationMiddleware`，后者继承官方 `langchain.agents.middleware.SummarizationMiddleware`；在before_model根据消息Token计数触发，使用 `RemoveMessage(REMOVE_ALL_MESSAGES)` 替换旧消息加摘要+保留尾部；
- `tool_output_budget_middleware.py` 负责外置长工具结果；`token_usage_middleware.py` 负责观察Token；`loop_detection_middleware.py` 限制重复工具循环，**并非将UTF-8 JSON字节累加当成所有会话的模型执行许可**。
- 官方文档：https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware；v2源：
  https://github.com/bytedance/deer-flow/blob/v2.0.0/config.example.yaml
  https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py

本项目错误根源：
- P07 `runtime/budget.py` 对消息/Schema估算UTF-8 JSON字节，soft24k/hard48k、Run累计480k，`UsageBudgetMiddleware` 在真正发给模型前硬拒绝；
- `agents/context_manager.py` 自写轮次切分与“最近六条保护”，第二问前未必能压缩第一问，滚动摘要也可能重复占预算；
- 自研限制与模型真实context window、Provider真实token_usage分离，且过多耦合 P06取消、调用次数/Usage，造成一问正常第二问失败。**跨Run累计额度本来是重置的，真正继承的是同Thread Checkpoint；不能把跨轮历史增长误说成跨Run余额耗尽。**

## 2. 目标与明确取舍

**删除执行路径中的自研上下文/累计字节硬拦截**，用官方`SummarizationMiddleware`管理同Thread滚动摘要。允许用户连续问很多轮，不因自造字节阈值自动失败。摘要只在必要时运行，消息原文可从业务Run/ToolTrace和Evidence/Artifact追溯，Graph只持有紧凑可继续工作状态。

**保留（但解耦）**：P06 Run用量统计（Provider真实usage和注明近似的本地诊断）、取消登记/传播、outcome_unknown、Checkpoint、Run/SSE、P03 Workspace与长工具结果外置、P04 Todo/受控子Agent、P05 ToolGuard/MCP/Skills、P07 EvidenceStore真实引用；保留合理timeout/工具超时/独立API搜索6次提取8次/只读子代理/并发限制、LangGraph递归/任务循环保护。不可为了简单把这类安全、成本和可恢复性一起删掉。

**取消普通路径的限制**：40次模型调用、30次工具调用、48k单请求字节拦截、480k单Run累计输入字节拦截，均不再构成执行许可。这些指标可以在Usage展示，是否未来提供可选用户花费上限是另一个独立产品决策，**本次不加新的隐藏硬上限**。模型真实上下文窗口仍客观存在；若Provider明确拒绝，准确返回“模型窗口不足或摘要失败”而非伪造本地预算错误，不能保证任意长度单轮输入必然可被接受。

## 3. 逐文件改造责任

| 文件 | 必须改成什么 |
|---|---|
| `agents/middleware.py` | 去掉 `UsageBudgetMiddleware` 的字节/次数检查；将其拆为**纯观察** `ModelUsageMiddleware` 和 `ToolUsageMiddleware`（原唯一invocation SQL和Provider usage去重保留），不预扣硬额度。不再挂 `ContextCompactionMiddleware` 自研分区/summary。摘要交给**官方`SummarizationMiddleware`**，必要时写一个**只有观察/状态记数的薄子类**，不能复制/重新实现旧cutoff逻辑或硬拦截 |
| `agents/context_manager.py` | 退出生产路径；旧 `partition`/6条保护/手写滚动摘要彻底废止。确认所有消费者解除后删除文件或仅留弃用适配文档（优先删除）。历史已写入Checkpoint的`context_summary`和特殊Human消息必须向后兼容，不清理/重建用户库 |
| `runtime/budget.py` | 从 **执行门禁** 改为 **只记录/取消信号的运行上下文**；`RunBudgetTracker.check` 仍检查用户取消/真实运行超时；`outcome_unknown`保留；`reserve/finish` 只保持真实调用日志+耗时，不再因累计输入字节/模型40/工具30阻断；保留已存在的 v1/v2数据以供旧Run查询，明确其非Token实际值。不要删除被ResearchService/ToolGuard/ToolOutput/Task引用的必需取消信号 |
| `runtime/usage.py`、`runtime/db.py` | 不丢历史 run_usage/usage_calls，新增或复用summary调用分类/压缩次数；记录Model本身与摘要模型实际usage；`estimated_input_tokens`旧列继续注明字节近似，旧Budget JSON仅历史兼容，**新Run不再使用其max_input作为硬限制**；慎重保持唯一ID、并发和NULL usage语义 |
| `runtime/runner.py` | 直接使用官方`SummarizationMiddleware(model=...,trigger=...,keep=...,trim_tokens_to_summarize=...)` 放在主 Agent middleware；注意顺序，summary调用不能作为用户可见assistant_delta重复流出。移除所有主动设置context_soft/hard/cumulative硬上限的检查和旧异常映射；将模型/工具调用监控与Checkpointer配合。给Child对应独立非持久图使用同样策略（child仅35秒，可配置低阈值） |
| `agents/subagents/executor.py` | Child不受18k/48k自造门禁；保留35秒和只读Guard，防止工具调用重复计数。根据需要为Child挂同一官方摘要中间件，Child上下文独立，**仍不能借父权限写文件/重试** |
| `config.py` / `.env.example` | 弃用`CONTEXT_SOFT_LIMIT_ESTIMATE/CONTEXT_HARD_LIMIT_ESTIMATE/RUN_MAX_INPUT_TOKENS_ESTIMATE`作为执行配置；新增可调`SUMMARIZATION_ENABLED=true`、`SUMMARIZATION_TRIGGER_TOKENS`、`SUMMARIZATION_KEEP_MESSAGES`、`SUMMARIZATION_TRIM_TOKENS`。数值根据用户**确认过的模型上下文容量/摘要模型能力**选择；DeerFlow示例32k是示例，不能将其直接强制用于小窗口模型。未知模型采用保守的消息数/估算Token触发，并将实际阈值明确展示/记录。禁止用“每字节=1真实Token”伪装Provider的Tokenizer |
| `agents/lead.py` / `agents/state.py` | 保留现有系统提示/Todo、原生State与Checkpoint，不复制 Summary逻辑；从旧自研Summary锚点迁移时确保不把它误判为新的用户目标 |
| `tools/output_budget.py` / `research/service.py` | 原有长结果外置与Evidence引用不变；只解开对计数硬拦截的依赖。Tavily的6/8请求SQL限额属于**外部API治理**，本次保留 |
| `frontend/src/components/UsagePanel.tsx`、`RunStatus.tsx`、`frontend/src/api/runtime.ts` | 新Run不再显示“48k/480k最大Token额度”；显示真实Token/调用数/摘要次数/输出外置量。历史Run字节v1/v2可以继续展示并注释是旧诊断，不要误导“额度耗尽”；取消/错误/重启查询工作正常 |

## 4. 核心机制与配置

对一个Thread：
- 首次新消息：从Checkpoint恢复现有紧凑历史+最新用户消息；before_model调用官方Summarization，未达触发则直接模型请求；
- 达阈值：LangChain自主把旧消息切为“待摘要”与“保留尾部”，保护AIMessage.tool_calls和ToolMessage对应关系，摘要生成后同Graph状态写回Checkpoint；
- 第二/第三/第N次追问：同Thread只加载**摘要+少量近期消息+新问题**；达到阈值再次滚动摘要，不因固定“最近六条”错拒旧回合；
- 单次复杂Run工具消息过多：官方中间件在模型调用前同样评估，超长工具回执先由P06 ToolOutputBudget外置，P07 Search/Evidence返回短ID和摘要，不重复上载长网页；
- 当前仍可能遇到**真实模型窗口不足**、单个工具Schema/不可分割的新问题大于窗口、摘要模型自身失败、超过LangGraph递归步数或Run超时；须明示真实原因，不把所有失败硬编码成 `CONTEXT_BUDGET_EXCEEDED`。

**参数建议**：先验证当前真实模型窗口；官方自动摘要可以基于可信窗口的约60–75%触发，`keep=("messages", 8~10)`，`trim_tokens_to_summarize`根据摘要模型支持范围选合理值；未知模型容量则保守设置绝对估算Token触发，并允许配置，不沿用旧JSON字节门禁。另加入观察“压缩前后tokens估算、当前Thread消息条数、触发原因、压缩调用耗时”但不写任何私密正文。

## 5. 分任务执行（Codex须逐步提交+前端同步）

- **R0 诊断冻结**：记录原用户本地工作区状态、当前真实模型类型和经过验证的窗口；检查本地`.env`但不输出key，清楚区分此时仅GitHub/源码可见。先用旧实现离线Fake重现“同一Thread第一问复杂工具调用→第二问失败”，记录Run ID/脱敏统计。禁止修改或清理现有用户SQLite/Checkpoint。
- **R1 移除硬门禁**：拆分`UsageBudgetMiddleware`、`RunBudgetTracker`为无硬阻断的用量/取消组件（如为兼容暂保旧类名也要明示Deprecated），移除40/30/48k/480k造成的阻断，保留SQL调用记录/取消/资源治理；局部测试与前端同步/提交。
- **R2 官方摘要接入**：用锁版LangChain `SummarizationMiddleware`代替自写`ContextManager`，根据真实模型context窗口确定默认参数；通过Checkpoint读写/工具配对/单Human Research/跨轮对话、流式回执、Summary不变成最终回复/不污染ToolTrace的真实Graph测试；局部测试/前端同步/提交。
- **R3 多轮与真实Demo**：同一个真实Thread下依次发送至少**15条**用户消息（第1条复杂Research，后续追问、普通问答、计算、Skill、再次Research混合），要求持续正常完成、摘要至少2次且最少1次在第二问首次模型调用前触发；无需手动建新会话，Restart后继续第16问。用**缩小测试触发阈值**而非增大本地硬上限让压缩触发；至少1项真实模型合成材料Smoke确认 Provider usage/摘要模型行为、可配置时公网Search单独标注。P06 Cancel/ToolGuard/Workspace/SSE/P07 Artifact/Evidence权限回归，Ruff/npm build，记录真实通过数量、失败、Provider账单未知。**旧Run FAILED不自动重放有副作用的工具**。提交R3并更新P07独立修复记录，仍PENDING_REVIEW。

## 6. 严格约束与停止条件

- 禁止直接删除`RunBudgetTracker`导致取消/OUTCOME_UNKNOWN消失；不能丢 `run_usage` SQL历史或伪造Provider tokens；不能允许ResearchChild写文件、跨Run引用或任意URL本机HTTP；
- 必须证明“**同Thread连续15问**”而不是仅一个问题/测试中人为换Thread；必须记录摘要次数与Checkpoint中消息数量确实下降；不能靠提高预算躲掉触发；
- 不修改用户未提交中文注释或本地`.env`中的密钥；不重置Checkpoint/DB/历史Run，不合并main或强推，不添加Redis/MQ/新的LLM框架；
- 若官方SummarizationMiddleware和当前锁版LangChain在streaming/ToolMessages语义不兼容，先用最小复现确认再采用其公开扩展点，不能复制现有失败的分区算法重新命名。
