# 03 · DeerFlow 2.0 逐模块源码参考地图

固定版本：bytedance/deer-flow v2.0.0，commit 7e7f0410797693cf882594555ba414e0361d4c6f。
上游：https://github.com/bytedance/deer-flow/tree/v2.0.0
许可：https://github.com/bytedance/deer-flow/blob/v2.0.0/LICENSE （MIT）。
本地图中路径为该 tag 下的相对路径，链接以该版本固定。审查依据为 GitHub 目录与关键文件的静态检查，不代表上游可在本机运行或通过测试。

## 一、正确使用参考源码的方法

1. 只在正在开发某一能力时读取对应的上游文件；不要一次克隆/通读整库。
2. 先回答：源码解决什么问题？数据流、状态不变量和失败路径是什么？我们哪些业务真正需要？
3. 再决定：直接使用成熟框架能力、借鉴接口/流程自己实现、或明确暂不实现。
4. 引入代码前检查上游许可证与上下文依赖；简单复制单个函数可能隐含上下文变量或配置单例。
5. 不把源码文件名当成必须一致的模块命名，不为了“和 DeerFlow 一样”进行无用设计。
6. 参考代码以固定 tag 为准；后续安全修复可以另行确认，但不默默跟随 main 发生大范围架构变化。

## 二、Agent 工厂、状态与 Middleware

| 范畴 | 路径（v2.0.0 下） | 参考内容 | 我们的计划 |
| --- | --- | --- | --- |
| Agent 工厂 | backend/packages/harness/deerflow/agents/factory.py | create_deerflow_agent、RuntimeFeatures 装配 | P01 小型工厂，显式依赖 |
| Lead Agent | backend/packages/harness/deerflow/agents/lead_agent/agent.py | make_lead_agent、工具/模型/Middleware 装配 | P01/P04/P05 分阶段添加 |
| 系统提示 | backend/packages/harness/deerflow/agents/lead_agent/prompt.py | Prompt、Skill 元信息与 Sub-Agent 使用指导 | P01 简短规则，避免过长模板 |
| 共享状态 | backend/packages/harness/deerflow/agents/thread_state.py | ThreadState、Reducer、Todos/Artifact 合并 | P02/P04 明确类型与状态更新 |
| 功能开关 | backend/packages/harness/deerflow/agents/features.py | 可选 Middleware 特性 | P05 只保留实际需要的开关 |
| Todo | backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py | 可更新计划与工具契约 | P04 |
| 动态上下文 | backend/packages/harness/deerflow/agents/middlewares/dynamic_context_middleware.py | 运行时上下文注入 | P02/P06 |
| 错误处理 | backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py | Tool 异常转消息、封装顺序 | P01/P05/P10 |
| 工具输出预算 | backend/packages/harness/deerflow/agents/middlewares/tool_output_budget_middleware.py | 对过长工具输出限制 | P06 |
| 消息清理 | backend/packages/harness/deerflow/agents/middlewares/dangling_tool_call_middleware.py | ToolCall 消息配对 | P02/P10 |
| 摘要压缩 | backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py | 摘要触发、Skill 内容保护 | P06 |
| 循环检测 | backend/packages/harness/deerflow/agents/middlewares/loop_detection_middleware.py | 防重复无效工具循环 | P06 |
| Token 统计 | backend/packages/harness/deerflow/agents/middlewares/token_usage_middleware.py | 使用量收集 | P06/P11 |
| Skill 激活 | backend/packages/harness/deerflow/agents/middlewares/skill_activation_middleware.py | 显式 Skill 激活 | P05 |

注意：create_deerflow_agent 的参数化组装不意味着全运行时完全无全局配置；其注入的 task_tool 等可能在调用时访问 AppConfig。我们需要使自己的服务边界尽可能显式。

## 三、子智能体与执行链

| 模块 | 路径 | 源码重点 | 不照搬部分 |
| --- | --- | --- | --- |
| Task Tool | backend/packages/harness/deerflow/tools/builtins/task_tool.py | 将委派构造成工具，结果和进度事件返回主 Agent | 不搬复杂后台轮询细节 |
| Executor | backend/packages/harness/deerflow/subagents/executor.py | 独立上下文、模型/工具过滤、并发、取消超时 | 初期不用完整线程池/隔离事件循环 |
| 子任务 Registry | backend/packages/harness/deerflow/subagents/registry.py | 子任务类型发现 | 固定少量类型即可 |
| 子任务配置 | backend/packages/harness/deerflow/subagents/config.py | 角色、超时、轮次、模型、工具等 | 精简配置 |
| 配置模型 | backend/packages/harness/deerflow/config/subagents_config.py | custom_agents、禁止工具、模型继承 | 先用本地声明 |
| 并发中间件 | backend/packages/harness/deerflow/agents/middlewares/subagent_limit_middleware.py | 最大并发数 | P04 并发限制 |
| 父子 Checkpointer 隔离测试 | backend/tests/test_subagent_checkpointer_isolation.py | 子 Agent checkpointer=False 与父图隔离 | 严格测试异步上下文 |

关键事实：DeerFlow 子 Agent 可通过 task_tool 在独立上下文执行；部分构造明确禁用继承的 Checkpointer。父 Agent 的图快照不等于进程中运行的所有子任务均可原地恢复。我们的 P04/P10 必须保留这一区分。

## 四、工具、MCP、Skills

| 模块 | 路径 | 我们学习的能力 |
| --- | --- | --- |
| Tool 装配 | backend/packages/harness/deerflow/tools/tools.py | 配置工具、内置工具、MCP 整合与去重 |
| Builtin Tools | backend/packages/harness/deerflow/tools/builtins/ | 工具参数、结果结构、文件呈现 |
| MCP Client | backend/packages/harness/deerflow/mcp/client.py | 外部 MCP Server 的连接配置 |
| MCP 工具转换 | backend/packages/harness/deerflow/mcp/tools.py | 返回转换、资源引用、隔离 |
| MCP 会话池 | backend/packages/harness/deerflow/mcp/session_pool.py | 可选连接复用，先不造轮子 |
| MCP 缓存 | backend/packages/harness/deerflow/mcp/cache.py | 启用/禁用工具的管理方式 |
| Skill Parser | backend/packages/harness/deerflow/skills/parser.py | SKILL.md frontmatter、合法性 |
| Skill Types | backend/packages/harness/deerflow/skills/types.py | Skill 数据对象与存储来源 |
| Skill Tool Policy | backend/packages/harness/deerflow/skills/tool_policy.py | 工具范围限制 |
| Skill Storage | backend/packages/harness/deerflow/skills/storage/local_skill_storage.py | 本地 Skills 管理 |
| Deep Research Skill | skills/public/deep-research/SKILL.md | 系统性研究步骤、覆盖与核查 |
| 文献审阅 Skill | skills/public/academic-paper-review/SKILL.md | 专业分析与证据要求 |
| 系统综述 Skill | skills/public/systematic-literature-review/SKILL.md | 多篇文献分工与汇总 |

Skills 是任务操作规范，不能替代 Search、PDF Parser、Embedding 或 Vector Index；不能把技能描述里的“可以解析 PDF”当成真实解析能力已经存在。

## 五、运行时、Checkpointer 与 API

| 模块 | 路径 | 参考目标 |
| --- | --- | --- |
| RunManager | backend/packages/harness/deerflow/runtime/runs/manager.py | Run 创建、状态、冲突、取消、孤儿处理 |
| Run Worker | backend/packages/harness/deerflow/runtime/runs/worker.py | agent.astream 调用、SSE 事件与异常路径 |
| Run Store | backend/packages/harness/deerflow/runtime/runs/store/ | Run 元数据与存储边界 |
| Checkpointer | backend/packages/harness/deerflow/runtime/checkpointer/provider.py | memory/sqlite/postgres 的配置与生命周期 |
| Async Checkpointer | backend/packages/harness/deerflow/runtime/checkpointer/async_provider.py | FastAPI async 执行的 Saver 选择 |
| LangGraph Store | backend/packages/harness/deerflow/runtime/store/provider.py | 与 Checkpoint 区分的 KV/长期数据 |
| StreamBridge | backend/packages/harness/deerflow/runtime/stream_bridge/base.py | 事件发布/订阅抽象 |
| Run Journal | backend/packages/harness/deerflow/runtime/journal.py | 执行信息与事件记录 |
| Gateway 入口 | backend/app/gateway/app.py | FastAPI lifespan、Router/中间件装配 |
| Run 路由 | backend/app/gateway/routers/runs.py | stream/wait 与 Run 查询 |
| Thread Run 路由 | backend/app/gateway/routers/thread_runs.py | Thread/Run 生命周期接口 |
| Thread 路由 | backend/app/gateway/routers/threads.py | 会话及状态读取 |
| Upload 路由 | backend/app/gateway/routers/uploads.py | 文件上传 API |
| Artifact 路由 | backend/app/gateway/routers/artifacts.py | 产物获取 |
| Run 生命周期测试 | backend/tests/test_runtime_lifecycle_e2e.py | HTTP → Run → Graph → Stream → Persist |
| Gateway 恢复测试 | backend/tests/test_gateway_run_recovery.py | 重启后孤儿 Run 处理 |

设计警告：RunManager、Checkpoint、StreamBridge 管理不同问题，不能省掉 Run 记录只留下 Checkpointer，也不能用 SSE 事件代替业务终态。单机首版优先保障这三类数据的语义一致性。

## 六、工作空间、沙箱和前端

| 模块 | 路径 | 参考目标 |
| --- | --- | --- |
| SandboxMiddleware | backend/packages/harness/deerflow/sandbox/middleware.py | 获取/释放执行环境 |
| LocalSandbox | backend/packages/harness/deerflow/sandbox/local/local_sandbox.py | 虚拟路径、文件操作，非可信进程隔离 |
| SandboxSecurity | backend/packages/harness/deerflow/sandbox/security.py | 默认禁止 Host Bash 的判断 |
| Sandbox Tools | backend/packages/harness/deerflow/sandbox/tools.py | 文件工具界面和错误 |
| Sandbox Security Tests | backend/tests/test_sandbox_tools_security.py | 路径穿越/映射/越权案例 |
| 前端任务数据 | frontend/src/core/tasks/context.tsx | 子任务进度事件归并 |
| 前端流模式 | frontend/src/core/api/stream-mode.ts | SSE/Graph stream 模式处理 |
| 前端 Workspace | frontend/src/components/workspace/ | 聊天/工具/Todo/产物界面 |
| 前端会话 | frontend/src/core/threads/ | API 状态、历史视图 |

LocalSandbox 是目录和命令封装，不应作为运行不可信模型代码的充分隔离。P03 只写受限文件工具，真正代码执行须满足容器级安全验收。

## 七、禁止大面积照搬的内容

- app/channels/ 各种聊天 IM 接入；
- 复杂 auth、SSO、多租户/组织模型；
- 全套自我创建 Agent、动态升级 Agent 功能；
- Kubernetes、远程沙箱 Provider 与跨节点任务架构；
- 所有模型供应商、搜索供应商、音视频生成工具；
- 复杂前端平台设置/营销/文档网站。

这些模块可能优秀，但与个人 Mini DeerFlow 目标无关。上游文件路径仅供定位，是否复制需逐段判断，保留 MIT 许可声明。
