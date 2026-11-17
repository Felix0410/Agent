# P07 原生自动摘要重构进度

状态：IN_PROGRESS。分支：`refactor/p07-native-summarization`，方案基线 `2ebf6910a1e91c447fd9a647bf26a94fe3f1fc1a`。P07仍PENDING_REVIEW，不合并main、不进入P08。

## R0 · 诊断冻结与原版核对（2026-11-17）

- 开始工作区干净，原本地/远端基线`c1e124c79b5d9210d6dd600e86198000bcfb1f7d`；通过GitHub连接器读取并逐个核验新方案3个Git对象，切换到方案分支，未重写共享历史或修改用户SQLite/Checkpoint。
- 当前真实模型标识`deepseek-flash`，已配置认证；MODEL_CONTEXT_WINDOW_TOKENS未配置，未取得可信窗口数据，不根据兼容模型名称猜容量。新摘要默认将使用明确标注的近似Token/消息数触发，不照搬DeerFlow的32k示例。
- 已实际读取DeerFlow `v2.0.0` 的`config.example.yaml`、`backend/packages/harness/deerflow/agents/lead_agent/agent.py`和`agents/middlewares/summarization_middleware.py`：原版继承官方SummarizationMiddleware，配置trigger/keep/trim；TAG_NOSTREAM屏蔽摘要流，另有Skill救援和企业记忆hook。本项目直接复用官方分区、裁剪、滚动摘要和状态替换，精简Skill救援/记忆hook，只增加本项目必要的观察/取消与账务接线。
- 本地锁版LangChain **1.4.9**源码已读：支持公开`summarizer` Runnable扩展点，`abefore_model`调用官方`_determine_cutoff_index/_partition_messages`保护工具成对，官方摘要Human标注`lc_source=summarization`；默认摘要使用with_retry，公开Runnable允许项目逐次统计摘要模型并保持零自动重试。不会复制旧cutoff或滚动摘要算法。
- 离线原实现真实Graph+临时SQL/Checkpoint重现同Thread两问：Thread `e4afda8d-951c-4e90-acd5-68c6adda506c`，第一Run `8a51e57f-daa4-49da-9c9c-e830c0038017`：两次各6k合成工具结果，SUCCEEDED，3模型/2工具、6条Checkpoint消息、最终请求13375字节近似。第二Run `38409508-fcb1-4b47-b767-60d607a2aeab`：追加1800个合成中文字，FAILED/CONTEXT_BUDGET_EXCEEDED，首次模型调用前0模型/0工具；7条消息、18975总字节、hard15000、reason=UNCOMPRESSIBLE。原Run累计是0，继承的是Thread消息，不是跨Run余额。
- 重现脚本`/tmp/minideerflow-native-r0.py`，只用Fake模型/合成工具/临时两库，已清理临时数据。未改.env、未碰用户库、未调用真实Provider；R0无业务代码变更。
