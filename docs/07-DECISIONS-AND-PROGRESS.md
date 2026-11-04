# 07 · 已确认决策、风险、状态与后续记录

日期：2026-11-04；本次操作：项目主线全面转向 Mini DeerFlow，旧方向不再作为当前仓库需求。旧文档被替换，但 Git 历史保留可追溯。

## 一、已确认决策

D01：定位“轻量级通用多智能体任务执行系统”，功能完整、可靠、可解释，不追求超过 DeerFlow。
D02：新建自己项目，按模块参考 DeerFlow 2.0 固定版本，不 Fork/大量删改成熟大仓库。
D03：核心包括 Lead Agent、Todo、Sub-Agent、Tools/MCP、Skills、Context、Run/Checkpoint、Workspace、Web UI。
D04：业务三条：Deep Research、文档 RAG、多步骤文件任务；依附共享 Agent 底座。
D05：先最小运行主线，再按 P00–P12 逐阶段引入；每阶段人工审核。
D06：严格控制本地 AI 的上下文，通过 CURRENT_STATE 与指定参考文件进行任务交付。
D07：不因简历目的强行引入 Redis、RabbitMQ、微服务、K8s、复杂认证/平台外围。
D08：所有评测/功能完成状态以未来真实运行证据为准，不能冒用上游成绩。
D09：不可信代码执行必须经过隔离审查，不能默认允许宿主机 Shell。

## 二、暂定技术方案（允许开发阶段以 ADR 调整）

Python 3.12+、LangChain/LangGraph、FastAPI、Pydantic、SQLite Checkpointer、React/Next.js、pytest；MCP 使用成熟 Adapter；文档 RAG 小规模索引先验证，后考虑 pgvector；Docker Compose 用于交付。锁定具体版本与环境兼容性是 P00 工作，当前不宣称可运行。

## 三、当前实际进度（不可虚标）

| 事项 | 状态 | 已有证据 |
| --- | --- | --- |
| 完整业务与总体架构 | DESIGN_READY | 01 文档 |
| 分阶段开发任务 | DESIGN_READY | 02 文档 |
| DeerFlow 固定参考地图 | STATIC_REVIEW | 03 文档；未本地跑上游 |
| Tool/API/Run 状态合同 | DESIGN_READY | 04 文档 |
| 测试与评测方案 | DESIGN_READY | 05 文档 |
| Codex 协作与部署规则 | DESIGN_READY | 06 文档 |
| P00 工程基线 | NOT_STARTED | 无运行项目 |
| P01–P12 业务与交付 | NOT_STARTED | 无代码、无测试成绩 |

## 四、关键风险与防线

R1：一口气建太多模块，造成学习困难与上下文爆炸。防线：一次一任务包，按需读上游 1–3 个文件。
R2：把父 Graph Checkpoint 当成子任务精确续跑。防线：单独 Run/Task 状态和故障注入，未知副作用不自动重试。
R3：工具权限过大、模型可执行宿主机命令。防线：ToolPolicy、文件白名单与容器沙箱。
R4：对 Deep Research/RAG 的引用和证据来源夸大。防线：真实 EvidenceRef 与人工核查。
R5：为简历堆 Redis/MQ/K8s 而延缓主功能。防线：有业务和实测证据再引入。
R6：不断更换框架/模板失去基线。防线：上游固定 v2.0.0、依赖锁、ADR 管理更新。
R7：文档与项目实际能力不一致。防线：CURRENT_STATE 只写已实现，不把规划当完成。

## 五、技术决策记录格式（ADR）

- 日期 / ID / 问题与业务触发；
- 事实与测试证据；
- 候选方案和优缺点；
- 决定及原因；
- 运行/安全/回退影响；
- 必要修改的文档与验收；
- 何时重新评估。

## 六、任务进度格式

Pxx / 标题 / 当前基线 SHA / 目标 / 实际变更 / 上游参考 / Mock 测试 / 集成测试 / 真实 E2E / 失败未测项 / 新 SHA / 风险 / 人工审核结果。

状态：NOT_STARTED → IN_PROGRESS → PENDING_REVIEW → ACCEPTED；或 BLOCKED / DEFERRED。仅用户明确审核后可进入 ACCEPTED。未经批准不自动开始下一阶段。

## 七、下一动作

仅启动 P00：核实新项目工程环境、创建最小目录、依赖锁、健康检查、测试与密钥隔离。P00 不实现 Agent 业务、DB 扩容、前端或 MCP。P00 完成后等待审核再执行 P01。
