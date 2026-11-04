# 03 · 业务流程、协议边界与故障路径

## 1. 通用任务的完整生命线（系统核心）

1. 用户发送任务（文本、可选文件和模式），API 验证输入、生成/定位 Thread。
2. RunService 为本次执行创建 Run，确认同 Thread 是否允许并发（首版默认同 Thread 只有一个活跃 Run）。
3. 构建 RunnableConfig（thread_id、run_id、预算、工具权限）及 LangGraph Checkpointer。
4. Lead Agent 读当前消息与状态，选择直接回答、工具调用、Todo 或 Sub-Agent。
5. 工具和子任务经统一执行接口进行白名单/超时/错误包装，结果和重要事件写入状态/事件流。
6. Graph 迭代并汇总。对长内容启用摘要、保留 Todo、证据引用和文件引用。
7. 输出回答/可下载 Artifact，Run 进入终态；SSE 返回最终状态，页面可回放。
8. 用户可以继续同 Thread 对话；重复调用需要新的 run_id，不能误读旧任务的终态。

> 关键：模型的“我已经完成”文本不等于服务层 SUCCEEDED；需要 Graph 正常结束且结果与产物满足业务验证。

## 2. 场景 A — Deep Research

输入示例：比较三种 Agent 编排框架，指出适用场景并生成报告。
Lead Agent：先规划搜索方向和报告标准 → 多轮检索 → 对比来源/去重 → 需要时委派两名 research Sub-Agent → 汇总并检查重要结论的真实来源 → 写出 Markdown。
子 Agent 返回：结构化发现、使用过的真实 URL、歧义和失败，不只返回没有证据的结论。
最终：自然语言摘要 + 来源列表 + research-report.md + 可检索的运行轨迹。
失败：联网不可用时停止新增事实或标记未知；一个分支失败不把它伪装成已验证结论。

## 3. 场景 B — 文档知识库 / RAG

上传文档 → 记录 Artifact → 提取文本与页码/章节 → 校验解析质量 → 分块/元数据 → Embedding 和索引。
用户提问 → Agent 调用 search_knowledge(scope,query,top_k) → 返回原文片段、文档名与位置 → 必要时重检索/重排 → 生成有证据的答案；引用应对应实际命中。
失败：PDF 解析失败、表格不可可靠提取、查询无命中、索引版本缺失，都必须向用户解释；不能用模型猜测填补缺少的原文证据。
边界：首版文档类型限定常见 PDF/Markdown/TXT；复杂扫描 OCR、海量文件与表格精确抽取后置。

## 4. 场景 C — 文件与多步骤任务

用户上传 CSV 与说明 → Agent 写 Todo → 使用受控文件读取工具分析内容 → 使用确定性变换工具生成摘要或文件 → 输出报告与下载路径。
本地文件工具只能访问当前 Workspace 的允许路径，限制文件大小和覆盖行为。需要执行任意 Python/Shell 时，必须进入额外审批/沙箱阶段，不允许简单开放宿主机 Shell。

## 5. 子任务委派子流程

Lead Agent 选择 subagent_type、描述、最小所需工具/Skills和上下文 → TaskDispatcher 生成 task_id → 限流 → 子 Agent 在隔离消息上下文中执行 → 状态/事件流更新 → 返回摘要或明确失败 → Lead Agent 继续。
初期先同步等待与严格超时，后实现并发数量限制；避免无界后台工作池。默认禁止子 Agent 递归使用 task 工具，除非未来独立设计。
重要：父图 Checkpoint 不能自动恢复进程内执行到一半的子 Agent；重启后只能按已保存结果、幂等规则、工具副作用类型决定重调度或终止。

## 6. API 最小契约（建议，不是已存在接口）

- POST /threads：创建会话；GET /threads：历史会话；GET /threads/{id}：详情。
- POST /threads/{id}/runs：开始一次执行，返回 run_id。
- GET /runs/{id}：状态与结构化概要。
- GET /runs/{id}/events：SSE 订阅与事件回放入口。
- POST /runs/{id}/cancel：请求取消；要能区分已终结、取消中、已取消。
- POST /threads/{id}/files：上传；GET /threads/{id}/artifacts：产物清单。
- GET /skills：列出启用的 Skill；/models、/mcp 配置后续按需开放。

首版优先保持前后端自己的稳定契约，不承诺完全兼容 DeerFlow / LangGraph Platform API。

## 7. SSE 最小事件类型

run_started、assistant_delta、tool_started、tool_finished、todo_updated、subtask_started、subtask_finished、artifact_created、run_succeeded、run_failed、run_cancelled。每条包含 run_id、event_id、time、type 与可序列化 payload；建议包含 task_id 以关联子任务。
前端不应直接依赖模型自然语言来更新任务状态。断线重连与历史事件回放按阶段实现，明确是否支持和可恢复范围。

## 8. 异常与安全语义

- 工具失败：规范成错误结果，限次重试；未知执行状态的写工具默认不重试。
- 模型断连：Run 按真实状态记录；如果有 Checkpoint，则按图状态恢复能力测试。
- 用户取消：设置取消信号，阻止新工具调用，已启动外部操作可能无法强制撤销；UI 显示真实状态。
- 重启恢复：先识别非终态 Run，做一致性核查；不宣称原地恢复所有后台子任务。
- Prompt Injection：网页/MCP/PDF 返回均为不可信数据，不能改变工具策略与授权。
- 产物：必须在受限目录、原子写入；用户下载要有归属校验和路径检查。
