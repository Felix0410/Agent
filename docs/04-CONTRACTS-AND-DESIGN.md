# 04 · 核心模块、接口契约与设计细则

本文定义概念合同，不要求 Codex 机械复刻所有字段名。具体 schema、路径、数据库类型可在各阶段依据框架和实际依赖确定，但变更不得破坏以下语义。

## 一、运行时对象关系与生命周期

Thread 是对话历史的归属单位；一次用户请求是 Run；一个 Run 内可有多个 Task、ToolInvocation、Artifact 和 Event。Run 业务状态与 LangGraph Checkpointer 分开记录。任务可重试并不意味着可以重复副作用操作。

### Run 状态

建议：CREATED、RUNNING、CANCELLING、SUCCEEDED、FAILED、CANCELLED、INTERRUPTED、UNKNOWN。
基本规则：只有 RUNNING 能向正常终态推进；终态不允许再次转为 RUNNING；重试应产生新 attempt 或明确的续跑记录。服务启动扫描此前 RUNNING：核查是否有存活 Worker，非存活记录标 ORPHANED/UNKNOWN 供后续修复，不自动声称完成。

### Task 状态

PENDING → RUNNING → COMPLETED / FAILED / CANCELLED / TIMED_OUT / UNKNOWN。
配置：type、prompt、timeout、max_turns、allowed_tools、skills、parent_run_id、task_id、attempt。
父 Agent 只消费 Task 的终态结果和必要结构化证据；避免把子 Agent 全量工具日志和消息历史塞回主上下文。

### 幂等与结果未知

只读检索重复执行通常可接受；文件写、外部提交和远程修改可能有副作用。必须记录 tool_call_id/idempotency_key 或输入摘要，依据实际支持决定重试；如果工具超时但无法确认是否执行，保持 UNKNOWN，不自动重复写入。

## 二、AgentState、Reducer 与中间件边界

建议起步状态只有 messages、todos、artifacts、context_summary、pending_action_refs；后续按需求添加 research evidence references 等字段。State 合并规则需要显式处理并行消息/文件的竞争；不要把多个子 Agent 的消息历史直接合并成一个杂乱列表。

Middleware 分为：
- 运行环境：ThreadData、Workspace、Uploads；
- 模型前：动态上下文、Skill 注入、Token 预算和摘要；
- 工具前后：权限、调用日志、超时、错误、输出截断；
- 模型后：循环/安全中止、统计；
- Agent 完成后：标题/使用量/轻量记忆（后期）。

顺序可能影响实际行为，不能只根据类型名任意重排。简化项目中每种 Middleware 先有一个清晰的测试用例，确需扩展才加入新中间件。

## 三、工具规范

所有工具应具有稳定唯一名称、说明、结构化参数 Schema、结构化结果、权限级别、timeout、最大输出长度与日志脱敏策略。
建议统一 ToolResult 语义：
- success：boolean；
- content：结构化数据或对模型友好的短文本；
- artifact_refs：如大结果保存在文件；
- evidence_refs：用于引用和审计；
- error_code、retryable、side_effect_unknown：明确失败类型；
- metadata：耗时、工具版本、远程来源、用量。

不要让模型解析随意的异常字符串决定是否重试；对于网络、限流、权限、参数错误分别返回明确类别。工具由 ToolExecutor 执行权限检查，Skill 和 Agent Prompt 不能提升权限。
用户授权应基于任务/工具策略，而不是“模型觉得需要”就允许删除文件或外部写操作。

## 四、MCP 执行契约

ConnectorConfig：server_id、transport、command/url、env_secret_refs、enabled、allowlist、timeout。
加载时校验来自受信配置，禁止未经审核的任意命令安装；工具枚举后映射 Tool Registry 并进行名称冲突与 Schema 验证。
执行结果是外部不可信数据，需要大小、文件 URL、工具输出内容的严格检查；远程 MCP 失败不得导致整个系统失去内部安全策略。
首版只读服务：搜索、文档/仓库内容获取；写操作须在后续阶段有清晰确认及审计。
开发后期再考虑会话池、动态目录、OAuth 和缓存，不抢占主链路。

## 五、Skills 约定

SKILL.md 使用 YAML Frontmatter，基本字段 name/description，内部正文是流程与规范。系统只将可用 Skill 的元信息呈现在合适的提示位置；被选择或显式激活后再加载必要正文，避免一直加载全部。
Skill 不等于程序、工具或数据源。一个要求“调研论文”的 Skill 只能指导如何调用已经存在且获得授权的搜索/文件/RAG 工具。
Skill 中可包含需要工具的建议，但实际工具授权以 ToolPolicy 为准；未信任 Skill 不允许自动安装依赖、修改系统 Prompt 或升级权限。
Skill 失败（格式不合法、内容过长、引用不存在）应可见、可禁用，不影响其他能力。

## 六、Sub-Agent 规范

父任务指定目标、输入上下文裁剪、工具/Skill 白名单、时间/轮次预算、输出 Schema。子任务可以并行但须有 semaphore 或等价控制，默认不可再次调 task 防止递归失控。
子任务与父任务共享 Trace ID、run_id、可授权的文件引用，不共享完整对话历史、内部提示词或秘密。
Result 建议包含 task_id、status、summary、evidence_refs、artifact_refs、usage、error。
父任务等待结果时应有明确超时/取消策略；子任务“后台进程中”与“已经持久化”是两种不同状态，应用重启时不能误以为所有 Task 可恢复。

## 七、API 合同草案

- POST /api/threads：创建会话（返回 thread_id）。
- GET /api/threads、GET /api/threads/{thread_id}：列表与详情。
- POST /api/threads/{thread_id}/runs：创建 Run（返回 run_id、状态及订阅位置）。
- GET /api/runs/{run_id}：查询运行状态、统计和必要错误。
- POST /api/runs/{run_id}/cancel：幂等取消；终态 Run 返回明确的 AlreadyTerminal 结果。
- GET /api/runs/{run_id}/events：订阅 SSE，支持可选 Last-Event-ID（真正实现回放后才宣称支持）。
- POST /api/threads/{thread_id}/files：受控文件上传。
- GET /api/threads/{thread_id}/artifacts：产物列表。
- GET /api/artifacts/{artifact_id}：下载并校验归属。
- GET /api/skills：当前启用的 Skill 概况；模型和 MCP 配置端点按阶段补充。

错误响应建议统一 code、message、request_id、details，例 THREAD_BUSY、RUN_NOT_FOUND、TOOL_DENIED、FILE_PATH_INVALID、MODEL_TIMEOUT、MCP_UNAVAILABLE、BUDGET_EXCEEDED。
API 模型必须可版本管理；首版没有义务兼容 DeerFlow 原有 Gateway 或 LangGraph Platform 的所有接口。

## 八、SSE Event Envelope 约定

字段：event_id（Run 内递增）、run_id、thread_id、task_id?、type、timestamp、payload。
最小类型：run_started、assistant_delta、tool_started、tool_finished、todo_updated、subtask_started、subtask_finished、artifact_created、run_succeeded、run_failed、run_cancelled、heartbeat。
前端对事件去重并按 event_id 排序，不以文字判断是否成功。SSE 断开不修改后端 Run 状态；若后端没有持久 EventStore，重连只能查询最新 Run 状态，不能虚构中间事件回放。

## 九、文件与 Artifact 契约

FileRef 对外是虚拟路径/ID，不能暴露宿主机真实路径；按 Thread/Run 划分目录，所有读写先规范化、再做根目录归属校验和链接处理。
上传：类型/大小/路径/数量/并发/文件名验证；失败必须可清理半成品。
写入：限制容量，先临时文件再原子提交；同名覆盖需要明确可重复行为；输出记录 hash、MIME 和关联 run_id。
下载：仅访问已登记的 Artifact，验证所属 Thread；不能通过任意 URL 参数读取本地绝对路径。
不允许直接把本地“进程执行”当作合法 File Tool 功能。

## 十、Knowledge/RAG 契约

Document 保留原始文件 hash、parser 版本、文本结构、索引状态。
Chunk 包含 source_text、retrieval_text（可等同 source_text）、page/section/offset、embedding_model/version。
search_knowledge(input_scope, query, top_k) 返回一个排序的 Evidence 列表，每条有真实原文、文档/页码、score 与稳定引用 ID。
Agent 生成引用必须绑定 Evidence ID；无来源或来源未读取时不得伪装成文档事实。
解析、索引和查询分离，失败时保留状态；重建版本要可回滚或至少不会混用新旧索引。

## 十一、Research 业务合同

ResearchQuestion 定义任务目标和范围；ResearchPlan 存在模型生成的 Todo 中；SearchHit 存真实来源链接；EvidenceRecord 记录引用使用与状态；ResearchReport 包含正文和可核对引用。
子 Agent 应输出一组结构化发现或明确失败，而不是一句“研究完成”。
最后报告至少有执行摘要、研究方法、关键发现、对比、主要来源、局限和未验证项。最终交付是可下载的 Artifact。
对事实核验分层：URL/来源有效性自动检查；内容支持率需人工核验或明确不确定评价。不可声称所有 LLM 事实已经被百分百核实。

## 十二、变更兼容与审查

修改 API、Event、ToolResult 或 RunState 属于合同级变更，必须记录原因、向后兼容/迁移方案、对应契约测试、失败风险并经审核。禁止为了某个 UI 特效随意改变后端完成/取消/错误语义。
