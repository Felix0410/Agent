# P07 原生自动摘要重构进度

状态：PENDING_REVIEW（R0–R3已实现并完成本地验证，待用户手动验收）。分支：`refactor/p07-native-summarization`，方案基线 `2ebf6910a1e91c447fd9a647bf26a94fe3f1fc1a`。P07仍PENDING_REVIEW，不合并main、不进入P08。

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

## R3 · 同Thread连续多问、重启、浏览器与真实模型（2026-11-18）

- R0本地提交`2a633fd`，R1`aaa6ffa`，R2`d60ccdf`。新增test_native_multiturn、test_child_native_trace；后者强制Child摘要掉早期read_text后仍保留真实file_id，错误read即便从Graph移除也仍为SUBTASK_TOOL_ERROR。修正旧TaskRegistry测试桩：该用例把create_agent替为Slow且model=None，故只为该队列/超时独立用例显式关闭摘要，不修改其取消/并发断言或生产策略。
- 离线真实HTTP/Run/SQLite/Checkpoint/Fake+MockTransport：仅创建一个Thread，连续15问，首问完整Research（Todo/Skill/Search/Fetch/两个并发ResearchChild/Evidence/Report），后续普通追问、计算、Skill及再次Research混合；缩小摘要触发为256 Token或8条消息、keep4、trim2000，而非提高硬门禁。第二问首次父模型请求前已触发摘要，全部SUCCESS；lifespan关闭两库后重开同Thread第16问成功。每个模型请求逐条验证ToolCall/ToolMessage配对，流式输出无NATIVE_SUMMARY_ONLY；旧Run来源/Usage/报告字节不变。
- 最终直接影响回归命令（backend）：

```bash
.venv/bin/pytest -q tests/test_native_summarization.py tests/test_native_multiturn.py tests/test_child_native_trace.py tests/test_usage_observation.py tests/test_context_research_flow.py tests/test_context_estimator.py tests/test_budget.py tests/test_usage.py tests/test_budget_demo.py tests/test_output_budget.py tests/test_cancel_recovery.py tests/test_runner.py tests/test_repository.py tests/test_runs_api.py tests/test_task_registry.py tests/test_tasks_api.py tests/test_events.py tests/test_todos.py tests/test_subagents.py tests/test_tool_guard.py tests/test_planning_demo.py tests/test_tools_demo.py tests/test_mcp.py tests/test_skills.py tests/test_file_tools.py tests/test_files_api.py tests/test_workspace.py tests/test_config.py tests/test_checkpoint.py tests/test_research_tools.py tests/test_research_child.py tests/test_research_demo.py tests/test_research_report.py tests/test_research_repository.py
```

- **326 passed in31.06s**；首次广回归323 passed/1 failed是上述None模型的调度测试桩不再满足摘要构造接口，已最小修正后重跑通过。Ruff check/format覆盖当前102文件通过，uv lock --check通过78依赖；npm run build通过43 modules。无新框架/库、无锁文件升级，没有P08/P09测试。各阶段数量有重叠，不累加为总量。
- **浏览器真实UI + 跨Python进程重启（来源/模型均Fake）**：ego-browser TaskSpace1，隔离8018，Thread `98b296d7-b756-4ac5-bb43-072c9c23a20c`；前15问全部SUCCEEDED，99模型/38工具/44次摘要，第二Run `dcab9756-9007-41d6-88d4-f9324f5444b5` 的SQL模型调用顺序明确为`summary,parent`。Checkpoint在15问后仅6条消息；强触发统计不代表正常6000/24默认值下的摘要频率。
- 停止PID4934，保留隔离两库/Workspace，启动新PID16133；浏览器刷新、选择同Thread，继续第16问Run `8eba0eb8-1eac-45d3-8b81-839c4d0de68d` SUCCEEDED，calculate真实返回60，4模型（含2摘要）/1工具，Checkpoint仍6条。最后一次摘要消息7→5、近似Token463→422，UI如实显示摘要设置/次数/消息数，未显示旧48k/480k最大执行额度。
- 首份1371-byte报告，浏览器重启前下载与重启后HTTP下载一致，SHA256 `90588088d0a66d2b21eb6f81105f6db9df22905bd14ab7f8db27d526c930ed5f`。截图`/tmp/minideerflow-native-usage.png`已实际查看；脱敏数字证据`/tmp/minideerflow-native-browser*.json`、报告和脚本留/tmp。浏览器自动滚动对长页面曾超时，读取DOM确认未重复发Run后用instant滚动恢复；等待发送按钮的旧条件误把空输入禁用当成运行未完成，已按真实完成数及填入后的可用状态修正自动化，不改产品行为。最终实际16问均成功。
- TaskSpace已finish，隔离服务已关闭、专用临时两库/Workspace已清理；未进入/改写用户业务库。两套本地解释器均为LangChain1.4.9，已在临时数据目录用main.py直接启动并GET /health=200后关闭；8000留给用户PyCharm。GUI断点未验证。
- **真实Provider，单Thread三问合成材料**：Thread `ce07fa45-ffcc-436e-9404-3b1e25fc8f9b`，三问均SUCCEEDED，第二问保留SNOW/123合成事实；5次真实模型调用含2次官方摘要，Provider输入5913/输出1438 tokens。临时隔离关闭Tavily，没有联网搜索/真实用户材料；三轮结果及脱敏诊断在`/tmp/minideerflow-native-real-results.json`，临时两库已清理，不记录账单金额。
- 真实Smoke仅为强制触发设置trigger128/keep2；第二问消息3→3、近似Token145→453，第三问消息5→3但Token502→662，说明极短文本生成结构化摘要可能扩张，不能声称每次摘要必然减少Token。这些数值完整保留，不用其作为正常默认值；正常本地.env仍6000 Token/24消息、keep8、trim4000，模型实际窗口未确认，不猜容量。
- README和旧P07修复进度已指向当前原生方案；旧页作为历史证据保留，不再误导当前字节执行配置。中文注释覆盖官方扩展点、回调唯一记账/取消收尾、Child已完成工具观察、状态与历史兼容，根System提示词/工具描述/授权集合不变。
- 尚未验证：真实Tavily公网来源支持度、实际模型窗口规格/账单、用户手动验收、PyCharm GUI及其它OS。任意大新问题/工具Schema仍可能超过真实模型窗口，官方摘要失败/图循环/超时会准确失败；旧FAILED Run不自动重放。P07保持PENDING_REVIEW，不合并main、不开始P08。
