# 02 · 总体架构、模块边界与状态模型

## 1. 分层总览

用户 → React / Next.js Web → FastAPI API（会话、Run、SSE、文件） → Agent Harness（Lead Agent + Middleware + Tools + Sub-Agent） → 基础设施（Checkpoint、RunStore、Workspace、MCP、Knowledge）。

单体仓库与单后端进程起步。Harness 不导入 Web/API 实现，业务功能通过 Tool/Service 接口注入。UI 不直接操作数据库。LangGraph 负责图状态，不替代 Run 业务生命周期。

## 2. 建议目录（属于目标结构，不是已存在文件）

- backend/app/api/：FastAPI 入口、threads/runs/files/skills/models API
- backend/app/agents/：Lead Agent 工厂、系统提示、Middleware 装配
- backend/app/agents/subagents/：子 Agent 注册、任务委派、执行器
- backend/app/tools/：Tool Registry、内置工具、MCP 适配器、权限策略
- backend/app/skills/：SKILL.md 发现、解析、加载、允许工具规则
- backend/app/runtime/：RunService、事件、取消、Checkpoint/Store 接入
- backend/app/workspace/：文件隔离、上传、产物、受控文件工具
- backend/app/knowledge/：解析、Chunk、Embedding、Retrieval、Citation（后期）
- backend/app/core/：配置、模型工厂、异常、日志与通用类型
- frontend/：Web 交互界面（先薄界面，再完善）
- tests/：单元、契约、故障注入、E2E
- eval/：固定任务集、评测脚本、真实报告（无假数据）
- docs/：决策、技术记录、阶段进度和本规划

目录可以在 P00 依据实际脚手架微调；禁止先建立大量空实现或互相循环依赖的抽象。

## 3. 组件责任合同

| 模块 | 只负责 | 明确不负责 |
|---|---|---|
| API | 校验/鉴权边界、请求、SSE、HTTP 错误 | LLM 决策与工具执行细节 |
| Lead Agent | 理解任务、规划、选择 Tool/Sub-Agent、综合结果 | 直接操作 SQL、执行宿主机命令 |
| Sub-Agent | 限定范围内自主执行一个子任务、返回结果/失败 | 递归无限委派、继承所有权限 |
| Tool Registry | 工具清单、参数、超时、授权、结果规范 | 业务规划 |
| Skills | 按需加载任务规范、工具约束 | 执行副作用或作为数据库 |
| Context | Token 预算、最近上下文/摘要、重要状态保留 | 替代 Checkpointer |
| RunService | 创建/取消/终结 Run、记录执行状态 | 替代 LangGraph 消息状态 |
| Checkpointer | 持久图状态、按 thread_id 恢复 | 保证外部副作用只执行一次 |
| Workspace | 路径隔离、文件读写、产物下载 | 执行任意未经隔离的代码 |
| Knowledge | 索引/检索/来源定位 | 直接生成业务结论 |
| Evaluation | 记录可重现任务/指标/失败原因 | 声称不存在的性能提升 |

## 4. 核心数据对象（语义优先，不先写 SQL DDL）

- Thread：会话标识、标题、时间；一个 Thread 有多次 Run。
- Run：一次用户请求对应的执行实例；run_id、thread_id、状态、开始结束、错误、取消标记、模型/预算/追踪。
- AgentState：消息、Todos、文件引用、关键上下文；由 LangGraph 图管理。
- DelegatedTask：父 run、task_id、agent_type、输入/输出引用、尝试次数、超时与状态；首版可进程内管理，后续需要时持久化。
- ToolInvocation：调用标识、工具名、输入摘要/脱敏、开始结束、结果分类/耗时与成本。
- Artifact：归属 thread/run 的文件路径/虚拟路径、类型、大小、校验信息。
- SkillDefinition：名称、描述、来源位置、启用/权限信息。
- Document/Chunk/Citation：原文、切片、位置、索引版本与引用映射（RAG 阶段）。
- EvaluationRun：任务数据集版本、代码版本、模型配置、结果、指标和日志。

## 5. 状态与一致性

Run 状态：CREATED → RUNNING → SUCCEEDED | FAILED | CANCELLED | INTERRUPTED。进程重启时的 UNKNOWN/ORPHANED 需单独标记、核对后处理，不能直接宣称成功。
Sub-Agent 状态：PENDING → RUNNING → COMPLETED | FAILED | CANCELLED | TIMED_OUT。未知执行结果按 UNKNOWN 处理，不盲目重试有副作用的工具。
持久化的 Graph State、Run 状态记录、SSE 事件日志各自分离，用 run_id/thread_id/task_id/事件顺序关联。SSE 断开仅表示客户端断开，不自动等同于任务失败或终止。

## 6. 同步和异步边界

API 接受请求并返回 run_id；Graph 在服务管理的任务生命周期内执行；内部可以并行调度有界 Sub-Agent；前端订阅 Run 事件。首版单 Worker，不假设进程重启后后台 Python Task 仍存在；服务启动应检查未终结 Run，记录为可恢复/未知/失败之一。

## 7. 技术路线

- Python 3.12+、FastAPI、Pydantic、LangChain 1.x / LangGraph（版本以 P00 锁定与测试为准）。
- SQLite：开发初期 Checkpoint、Run 元数据与轻量数据存储；分清各库/表，允许分文件。
- React / Next.js：薄前端；SSE 可视化；不追求复杂后台。
- 文件系统：每 Thread/Run 的受限 Workspace，文件大小/数量限制，路径防穿越。
- MCP：官方适配库与少数已审核服务，默认只读。
- 文档 RAG：解析与 pgvector（规模需要时再上 PostgreSQL），不得先搭整套基础设施。
- Docker：后期部署与隔离进程；任意代码执行必须真正隔离。
- Redis/MQ/微服务：只有需求和可重复的瓶颈证据才纳入 ADR。

## 8. 架构原则

先打通最简单的端到端主线，再补边界、安全和测试；每新增模块说明是什么、解决何问题、为什么现在引入、替代方案及退出条件。参考 DeerFlow 的工程解决办法，不把它的整个运行时搬来造成上下文膨胀。文档定义模块的职责，不强行规定每个类的名称。
