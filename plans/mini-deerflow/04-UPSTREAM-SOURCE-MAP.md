# 04 · DeerFlow 2.0 源码参考地图（按模块最小阅读）

## 1. 来源与审查口径

上游：bytedance/deer-flow。
固定 tag：**v2.0.0**；tag commit：**7e7f0410797693cf882594555ba414e0361d4c6f**。
审查来自 GitHub 仓库目录、部分核心源码/配置/测试的静态读取；**不是已经在本地克隆、运行或证明测试通过**。开发阶段仍要以本地源码与所锁定版本验证。
参考与复用分开：从现有实现学习设计可以；如原样复制源码，须保留相关 MIT 许可和版权归属。

## 2. 模块参考地图

| # | 模块 | 上游源码（固定 v2.0.0） | 阅读目标 / 本项目处理 |
|---|---|---|---|
| 1 | Lead Agent 装配 | [backend/packages/harness/deerflow/agents/lead_agent/agent.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/lead_agent/agent.py) | 研究 make_lead_agent/build_middlewares、模型工具提示词装配；新项目仅实现实际启用的 Middleware |
| 2 | 低耦合 Agent 工厂 | [backend/packages/harness/deerflow/agents/factory.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/factory.py) | 研究 create_deerflow_agent 和 RuntimeFeatures；避免照搬隐藏全局配置依赖 |
| 3 | 图状态与 Reducer | [backend/packages/harness/deerflow/agents/thread_state.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/thread_state.py) | 研究 ThreadState、Todos/Artifacts 合并规则；建立自己的清晰状态 Schema |
| 4 | 系统 Prompt / Skills 宣告 | [backend/packages/harness/deerflow/agents/lead_agent/prompt.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/lead_agent/prompt.py) | 研究提示词组织、Skills 元信息与 Sub-Agent 指导；不复制庞大通用 Prompt |
| 5 | Todo | [backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py) | 研究动态规划和 Todo 工具契约；区分计划文本与真实状态 |
| 6 | 动态上下文 | [backend/packages/harness/deerflow/agents/middlewares/dynamic_context_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/dynamic_context_middleware.py) | 研究注入运行期信息的时机和隔离 |
| 7 | 上下文摘要 | [backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py) | 研究压缩、保留关键 Skill 内容与长工具消息；先简化摘要 |
| 8 | 错误处理 | [backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py) | 研究工具失败规范化及中间件顺序 |
| 9 | 循环检测 | [backend/packages/harness/deerflow/agents/middlewares/loop_detection_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/loop_detection_middleware.py) | 研究重复调用限制；后期按证据加入 |
| 10 | Sub-Agent 委派 Tool | [backend/packages/harness/deerflow/tools/builtins/task_tool.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/tools/builtins/task_tool.py) | 研究 task 工具签名、任务事件、结果合并；首版自己实现较小 Dispatcher |
| 11 | Sub-Agent 执行 | [backend/packages/harness/deerflow/subagents/executor.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/subagents/executor.py) | 研究独立上下文、超时/取消、并发与 checkpointer=False；不要照搬大后台线程调度 |
| 12 | Sub-Agent 配置 | [backend/packages/harness/deerflow/subagents/config.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/subagents/config.py) | 研究角色类型、模型、工具白名单与最大轮次 |
| 13 | 工具统一装配 | [backend/packages/harness/deerflow/tools/tools.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/tools/tools.py) | 研究配置工具/MCP/内置工具合并与去重 |
| 14 | MCP Client | [backend/packages/harness/deerflow/mcp/client.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/mcp/client.py) | 研究 MCP 连接/初始化，优先用现有适配器 |
| 15 | MCP 会话复用 | [backend/packages/harness/deerflow/mcp/session_pool.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/mcp/session_pool.py) | 后期有实际性能问题再参考，不一开始重写连接池 |
| 16 | MCP 工具转换 | [backend/packages/harness/deerflow/mcp/tools.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/mcp/tools.py) | 研究 MCP 结果转换、文件资源与隔离；权限仍需代码检查 |
| 17 | Skill 解析 | [backend/packages/harness/deerflow/skills/parser.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/skills/parser.py) | SKILL.md frontmatter 和描述解析；按需加载全文 |
| 18 | Skill 激活 | [backend/packages/harness/deerflow/agents/middlewares/skill_activation_middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/agents/middlewares/skill_activation_middleware.py) | 研究显式激活；自动匹配可后续实现 |
| 19 | Skill 权限 | [backend/packages/harness/deerflow/skills/tool_policy.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/skills/tool_policy.py) | Skill 限定可用工具；权限不能只依赖 Prompt |
| 20 | Run 管理 | [backend/packages/harness/deerflow/runtime/runs/manager.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/runtime/runs/manager.py) | 研究 Run 冲突、终态、取消、异常恢复；不把它与 Graph Checkpoint 合并 |
| 21 | Run Worker | [backend/packages/harness/deerflow/runtime/runs/worker.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/runtime/runs/worker.py) | 研究 Graph astream、消息事件/异常路径；首版单 Worker |
| 22 | Checkpoint Provider | [backend/packages/harness/deerflow/runtime/checkpointer/provider.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/runtime/checkpointer/provider.py) | 研究 SQLite/Postgres 后端和连接生命周期 |
| 23 | StreamBridge 接口 | [backend/packages/harness/deerflow/runtime/stream_bridge/base.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/runtime/stream_bridge/base.py) | 研究事件发布/订阅接口；首版单进程实现 |
| 24 | Sandbox 生命周期 | [backend/packages/harness/deerflow/sandbox/middleware.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/sandbox/middleware.py) | 理解工具执行前后的沙箱状态 |
| 25 | Local Sandbox | [backend/packages/harness/deerflow/sandbox/local/local_sandbox.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/sandbox/local/local_sandbox.py) | 仅作为本地文件工具/路径映射参考；不是完整安全隔离 |
| 26 | Sandbox 安全规则 | [backend/packages/harness/deerflow/sandbox/security.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/packages/harness/deerflow/sandbox/security.py) | 参考默认禁用宿主机 Bash 的边界 |
| 27 | Gateway 应用 | [backend/app/gateway/app.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/app/gateway/app.py) | 研究 FastAPI 路由和依赖初始化；重写小入口 |
| 28 | Run API | [backend/app/gateway/routers/runs.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/app/gateway/routers/runs.py) | 研究流式请求及 Run 状态 API；不强制兼容上游协议 |
| 29 | Thread API | [backend/app/gateway/routers/threads.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/app/gateway/routers/threads.py) | 研究会话及状态/历史接口；只实现所需子集 |
| 30 | 上传与产物 API | [backend/app/gateway/routers/uploads.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/app/gateway/routers/uploads.py) | 研究文件入站边界 |
| 31 | 产物 API | [backend/app/gateway/routers/artifacts.py](https://github.com/bytedance/deer-flow/blob/v2.0.0/backend/app/gateway/routers/artifacts.py) | 研究工作产物查询/返回 |
| 32 | 前端任务状态 | [frontend/src/core/tasks/context.tsx](https://github.com/bytedance/deer-flow/blob/v2.0.0/frontend/src/core/tasks/context.tsx) | 研究前端子任务状态/事件映射；不复刻整套 UI |
| 33 | 前端 API 流模式 | [frontend/src/core/api/stream-mode.ts](https://github.com/bytedance/deer-flow/blob/v2.0.0/frontend/src/core/api/stream-mode.ts) | 研究流事件模式与前端兼容性 |
| 34 | Deep Research Skill | [skills/public/deep-research/SKILL.md](https://github.com/bytedance/deer-flow/blob/v2.0.0/skills/public/deep-research/SKILL.md) | 研究流程规范；注意它不是向量检索引擎 |
| 35 | 科研综述 Skill | [skills/public/systematic-literature-review/SKILL.md](https://github.com/bytedance/deer-flow/blob/v2.0.0/skills/public/systematic-literature-review/SKILL.md) | 研究来源选择与多篇分析规范；专业功能可后置 |

## 3. 分阶段怎样读源码

- P01：只读 Agent 工厂、Lead Agent、ThreadState、一个 Tool 例子；重点弄清模型→工具→模型闭环。
- P02：只读 RunManager、Worker、Checkpoint Provider、StreamBridge、Gateway 的 Run/Thread 路由；重点弄清业务状态、图状态、流事件三者关系。
- P03：只读 sandbox/security、local_sandbox、upload/artifact 工具与路由；实现安全的 Workspace 子集。
- P04：只读 task_tool、subagents/executor、subagents/config、TodoMiddleware；实现本地有限并发与上下文隔离。
- P05：只读 tools/tools、mcp/client/tools、skills/parser/tool_policy/activation 及一个 SKILL.md；集成成熟适配器。
- P06：只读 summarization、tool_error_handling、loop_detection、运行恢复相关测试；处理上下文和故障。
- P07：只读前端 threads/tasks/streams 及对应组件；不把 DeerFlow 全套页面复制进来。
- P08：阅读 deep-research / systematic-literature-review Skill，抽取业务流程，不把 Skill 当作代码实现。
- P09：无需复制上游 RAG；知识解析和检索以自身可测试接口为边界，必要时再选独立可靠开源组件。

## 4. 关键实现事实与误区

1. 上游 Lead Agent 通过 langchain.agents.create_agent 装配，而不是所有模块都各自有一张手写 LangGraph。
2. TodoMiddleware 解决动态 Todo；并非所有请求都走严格固定 Planner→Executor→Writer。
3. SubagentExecutor 具有独立上下文和任务执行机制，部分子图显式 checkpointer=False；父任务持久化不能保证子任务中途精确续跑。
4. RunManager、Checkpoint、StreamBridge 是不同组件；不能只保留一个 Checkpointer 就认为具备可靠任务管理。
5. 上游 LocalSandbox 可能使用宿主机资源；只有具备真实隔离的进程/容器运行环境才能安全执行模型生成的不可信命令。
6. 原仓库 deep-research/SKILL.md 是检索与综合的方法指南，不等于真实的 PDF 向量库或 pgvector 系统。
7. 上游 Agent 工厂显式参数化不代表工具运行时彻底没有全局配置依赖；独立项目应改善此边界。
8. 不盲目照搬代码或所有中间件，先写测试确定我们需要什么语义。

## 5. 不参考/暂不复用的位置

不读 app/channels 整套 IM 渠道，不引入复杂 Auth/RBAC/SSO、K8s Sandbox Provisioner、Agent 自我修改系统、扩展工具商店、全套多提供商适配和大型前端配置中心。以后出现明确需求再记录 ADR。

## 6. 源码审查方式（适合小上下文 AI）

每次只给 Codex：当前阶段需求 + 1~3 个上游具体源文件 + 当前项目相关 2~5 个文件 + 测试。先写对照笔记：上游为什么这么做 / 我们要保留哪个不变量 / 哪部分有过度设计 / 安全边界。不能以全仓扫描替代明确的调用链阅读。
