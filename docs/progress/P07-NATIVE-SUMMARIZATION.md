# P07 原生自动摘要重构进度

状态：IN_PROGRESS。分支：`refactor/p07-native-summarization`，方案基线 `2ebf6910a1e91c447fd9a647bf26a94fe3f1fc1a`。P07仍PENDING_REVIEW，不合并main、不进入P08。

## R0 · 诊断冻结与原版核对（2026-11-17）

- 开始工作区干净，原本地/远端基线`c1e124c79b5d9210d6dd600e86198000bcfb1f7d`；通过GitHub连接器读取并逐个核验新方案3个Git对象，切换到方案分支，未重写共享历史或修改用户SQLite/Checkpoint。
- 当前真实模型标识`deepseek-flash`，已配置认证；MODEL_CONTEXT_WINDOW_TOKENS未配置，未取得可信窗口数据，不根据兼容模型名称猜容量。新摘要默认将使用明确标注的近似Token/消息数触发，不照搬DeerFlow的32k示例。
- 已实际读取DeerFlow `v2.0.0` 的`config.example.yaml`、`backend/packages/harness/deerflow/agents/lead_agent/agent.py`和`agents/middlewares/summarization_middleware.py`：原版继承官方SummarizationMiddleware，配置trigger/keep/trim；TAG_NOSTREAM屏蔽摘要流，另有Skill救援和企业记忆hook。本项目直接复用官方分区、裁剪、滚动摘要和状态替换，精简Skill救援/记忆hook，只增加本项目必要的观察/取消与账务接线。
- 本地锁版LangChain **1.4.9**源码已读：支持公开`summarizer` Runnable扩展点，`abefore_model`调用官方`_determine_cutoff_index/_partition_messages`保护工具成对，官方摘要Human标注`lc_source=summarization`；默认摘要使用with_retry，公开Runnable允许项目逐次统计摘要模型并保持零自动重试。不会复制旧cutoff或滚动摘要算法。
- 离线原实现真实Graph+临时SQL/Checkpoint重现同Thread两问：Thread `e4afda8d-951c-4e90-acd5-68c6adda506c`，第一Run `8a51e57f-daa4-49da-9c9c-e830c0038017`：两次各6k合成工具结果，SUCCEEDED，3模型/2工具、6条Checkpoint消息、最终请求13375字节近似。第二Run `38409508-fcb1-4b47-b767-60d607a2aeab`：追加1800个合成中文字，FAILED/CONTEXT_BUDGET_EXCEEDED，首次模型调用前0模型/0工具；7条消息、18975总字节、hard15000、reason=UNCOMPRESSIBLE。原Run累计是0，继承的是Thread消息，不是跨Run余额。
- 重现脚本`/tmp/minideerflow-native-r0.py`，只用Fake模型/合成工具/临时两库，已清理临时数据。未改.env、未碰用户库、未调用真实Provider；R0无业务代码变更。

## R1 · 观察与执行许可解耦

- 修改runtime/budget、agents/middleware、runner、subagents/executor、config、.env.example和UsagePanel：新Run mode=observe_only；ModelUsageMiddleware/ToolUsageMiddleware只记录唯一调用、耗时/Provider usage，移除40/30、单请求/累计字节和猜测模型窗口门禁。旧类名仅兼容；历史SQL及诊断保留。取消、TimeoutError、OUTCOME_UNKNOWN、ToolGuard和Research SQL额度未删除。移除生产自研ContextCompaction装配，R2接入官方。
- 显式废弃旧.env限额配置，Pydantic extra=ignore兼容旧条目；未修改用户密钥。45次并发模型/35工具、900000字节真实登记且不被旧上限拒绝；大System/Schema只作脱敏观察。UI新Run不再展示最大次数/字节额度，历史Run注明仅历史诊断，Provider真实Token仍显示。
- 局部命令：pytest tests/test_usage_observation.py tests/test_budget.py tests/test_usage.py tests/test_budget_demo.py::test_real_model_hook_usage_and_child_shared tests/test_budget_demo.py::test_legacy_call_limit_no_longer_blocks_second_model tests/test_cancel_recovery.py tests/test_subagents.py tests/test_research_tools.py tests/test_research_child.py tests/test_config.py：**60 passed in8.02s**；Ruff check/format通过本次Python文件，npm run build通过43 modules。
- 原自研分区测试将在R2随生产旧文件删除改为官方机制测试，不用旧“必须预算失败”的断言误验新行为；本阶段尚未声称多轮摘要修复完成。

## R2 · 官方自动摘要接入

- 直接装配锁版SummarizationMiddleware的薄子类ObservedSummarizationMiddleware，调用super().abefore_model，不重写分区/cutoff/裁剪/滚动算法。使用公开summarizer=同配置BaseChatModel浅副本，加TAG_NOSTREAM与AsyncCallbackHandler逐次记录真实摘要尝试，保留官方只读摘要重试/ContextOverflow处理；没有改框架私有Runnable。
- 与DeerFlow v2差异及证据：原版额外Skill救援/记忆flush本项目不需要；本锁版公开summarizer允许更薄接线。唯一额外账务适配是取消时等待框架shield回调完成；实际取消测试最初观察到PENDING晚收尾，现用同一回调锁确保终态发布前UNKNOWN入账。Child用旁路ToolTraceObserver保留已完成回执，避免原生摘要后丢失先前失败和file_id；不参与分区、不重放工具、不提升权限。
- 删除生产context_manager.py和其旧6条保护/字节估算框架，移除对应实现型测试，替换为真实Graph/Checkpoint/流式/配对测试。旧context_summary字段及旧Human锚点仍可读，测试证明不清库、Todo保留、新问题继续工作；摘要内容不成为assistant_delta/final/ToolTrace。
- 新配置：SUMMARIZATION_ENABLED=true、TRIGGER_TOKENS=6000、TRIGGER_MESSAGES=24、KEEP_MESSAGES=8、TRIM_TOKENS=4000。未知模型用官方近似Token/消息数OR触发，非精确窗口；已确认MODEL_CONTEXT_WINDOW_TOKENS只收紧摘要trigger/trim。父/Child同策略，保留600s/35s和图递归约束。
- 新Run日志/Usage记录近似Token前后、消息数、摘要耗时与source，不记录正文；Provider/历史v1/v2仍独立，UI不展示新Run“最大字节额度”。MODEL_CONTEXT_WINDOW_EXCEEDED / SUMMARY_FAILED / AGENT_RECURSION_LIMIT区分真实原因，不伪报本地预算。
- 本地.env仅移除三个旧字节执行配置，添加上述5项摘要参数，原有摘要自定义值/凭据均保留。未配置或猜测真实模型窗口；配置改动后需重启用户后端，新轮不占用8000影响PyCharm。
- 局部：pytest tests/test_native_summarization.py tests/test_context_research_flow.py tests/test_config.py tests/test_research_demo.py tests/test_research_child.py tests/test_budget_demo.py tests/test_context_estimator.py tests/test_usage_observation.py tests/test_budget.py tests/test_usage.py tests/test_subagents.py tests/test_cancel_recovery.py：**66 passed in10.32s**；Ruff与format通过修改Python文件；npm run build通过43 modules。空摘要/取消失败不替换旧Checkpoint；摘要与父各7/2合成usage只记一次；真实模型窗口异常/循环异常HTTP分类通过。
- P07研究全链默认/低触发均完成报告、两Child、15证据；逐个检验模型实际收到的ToolCall/ToolMessage成对。原始用户输入保留业务Run，Graph内容由官方摘要管理，不再强行保留原Human全文。真实模型/连续15问/跨进程重启证据在R3单列。
