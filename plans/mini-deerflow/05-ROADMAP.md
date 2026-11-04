# 05 · 从零建设 Mini DeerFlow 的全流程路线图

总规则：每阶段先最小可运行链路，再补异常、测试和文档；**用户审核通过后才进入下一阶段**。以下是阶段级计划，Codex 一次只执行当前阶段中一个明确任务包，不可自动连跑。阶段没有承诺工期。

## 阶段总览与依赖

P00 项目初始化/架构决策
→ P01 最小 Agent（模型与一项 Tool）
→ P02 Thread/Run、Checkpoint、SSE
→ P03 Workspace 与受控文件工具
→ P04 Todo + Sub-Agent
→ P05 Tool Registry + MCP + Skills
→ P06 上下文管理与可靠性
→ P07 Web 前端与运行可视化
→ P08 Deep Research 业务闭环
→ P09 文档 RAG 业务闭环
→ P10 评测、部署与交付

可调整跨阶段任务顺序，但变更需 ADR 并保留既有功能回归。项目满足 P08 时已具备较强的通用 Agent 演示；P09/P10 构成完整目标。

## P00：独立仓库与工程基线

- 目标：建立全新的空代码仓库，把本规划移入 docs；记录 DeerFlow 固定参考版本、MIT 使用规则。
- 内容：Python/FastAPI 项目布局、环境变量模板、最低测试入口、格式化/静态检查、依赖锁；只有足够支撑 P01 的目录。
- 非目标：不搬 DeerFlow 源码，不一次性建所有数据库/缓存/微服务。
- 验收：清洁环境能安装项目；基础健康测试通过；无密钥提交；架构/版本/许可记录完整；Git SHA 可追溯。

## P01：一个真正能用工具的 Agent

- 目标：输入任务 → LangGraph/agent 选择工具 → 读回工具结果 → 返回回答。
- 内容：模型工厂、最小系统提示、1 个只读 Tool、Agent factory、CLI 或 pytest 入口；真实模型 Smoke + Mock 单测。
- 来源：04 的 Agent 工厂/Lead Agent/ThreadState/Tools。
- 验收：测试模型/tool 故障能返回明确错误；正常路径真实调用工具且有验证证据；没有重型平台组件。

## P02：服务化、会话状态与流式输出

- 目标：由一个脚本升级为能多轮对话、查询 Run 的 FastAPI 服务。
- 内容：Thread、Run、统一 ID、SQLite Checkpoint、最小 RunStore、SSE、单活跃 Run、取消接口的基础语义。
- 来源：04 的 RunManager/Worker/Checkpoint/StreamBridge/Gateway。
- 验收：多轮历史正确；run_id/thread_id 对齐；流事件顺序正确；重启后保存的会话可读取；失败/取消不显示成功。

## P03：文件 Workspace 和产物

- 目标：用户上传文件，Agent 使用安全文件工具读取与写出结果。
- 内容：每会话目录、上传限额、路径校验、只允许白名单操作、产物 API、原子写入。
- 来源：04 的 sandbox/security/local_sandbox、uploads/artifacts。
- 验收：读取/写入/下载端到端；拒绝 ../、符号链接越权、绝对路径逃逸与超额文件；不允许任意宿主机 Shell。

## P04：动态计划与多 Agent 协作

- 目标：复杂任务可规划，并把子任务分配给独立上下文的研究/通用子 Agent。
- 内容：Todo、TaskDispatcher、任务上下文/工具白名单、基本 TaskEvent、并发上限、超时/取消、结果汇总。
- 来源：04 的 Todo/task_tool/subagents/executor/config。
- 验收：简单任务无需强制规划；复杂任务有真实可更新 Todo；多个子任务并发不超限；失败/超时不误报成功，父图与子任务状态界限清楚。

## P05：工具扩展与 Skills

- 目标：不改 Agent 核心就能增加新工具和任务流程。
- 内容：统一 Tool Registry、MCP Adapter（先选一个只读 Server）、SKILL.md Parser、按需激活、工具使用策略与权限。
- 来源：04 的 tools/tools、mcp/client/tools、skills/parser/activation/tool_policy。
- 验收：新增工具不改 Lead Agent 主循环；MCP 成功/断连/超时均可测试；禁用工具不可通过 Skill 或子 Agent 绕过。

## P06：长任务上下文与可靠执行

- 目标：长任务能受控运行，失败有可观察状态；模型上下文不会无限膨胀。
- 内容：Token/成本记录、工具输出预算、摘要压缩、关键 Todo/引用保护、循环限制、取消与启动孤儿 Run 核查。
- 来源：04 的 summarization/error_handling/loop_detection 与 runtime。
- 验收：触发摘要后任务目标不丢；重复调用有上限；故障注入后状态一致；未经证明不承诺精确恢复进程内子任务。

## P07：可实际使用的 Web 工作台

- 目标：从浏览器完成任务，查看流事件、Todo、子任务、文件与历史。
- 内容：Next.js/React 薄 UI，表单、聊天流、事件归并、运行状态、取消、产物下载、空态/错误态。
- 来源：04 的 frontend/src/core/tasks、frontend/src/core/api/stream-mode、Gateway 契约。
- 验收：一个浏览器用户可完成多轮/子任务/文件操作；刷新后可读取服务端状态；前端不根据 AI 文字自行判断成功。

## P08：Deep Research 业务闭环

- 目标：通用底座上完成第一种完整复杂业务。
- 内容：联网检索、去重、引用归档、计划与子任务调研、核验步骤、报告 Skill、Markdown 产物。
- 来源：04 的 deep-research/SKILL.md 和多 Agent 工具链。
- 验收：真实问题→真实来源→带引用报告；来源缺失被明确标记；至少有一组固定 Research 场景回归。

## P09：多文档 RAG 业务闭环

- 目标：支持上传多个文档并进行有出处的知识问答与比较。
- 内容：解析、Chunk/元数据、Embedding/向量索引、检索 Tool、引用对齐和小规模金标检索测试。先小型索引，规模需要时再引入 PostgreSQL/pgvector。
- 来源：参考 DeerFlow 的工具接入、文件 Skill，但 RAG 内部由独立业务模块实现。
- 验收：能够从真实 PDF 找到原文证据，引用与文件/章节/页码一致；无命中/解析失败有准确状态；对照基础检索可复跑。

## P10：评测、发布与面试材料

- 目标：交付稳定、可复现、有明确个人贡献的完整项目。
- 内容：单测/契约/E2E/故障注入、固定 Eval 数据集、Token/延时/任务质量统计、Docker、README、架构图、设计决策与来源声明。
- 验收：清洁环境部署；三条业务演示有真实记录；评测脚本和失败样例可复跑；无暴露凭证、越权文件路径和未经隔离的危险命令。

## 各阶段共同交付合同

- 最小可运行入口与业务场景；没有可运行代码就不算完成阶段。
- 测试命令、真实结果、失败项、截图或事件/文件产物路径；不能用模型自述成功替代测试。
- 功能与安全边界、必要的设计决策 ADR。
- 单独 Git Commit、变更清单、准确 SHA。
- 进度改为 PENDING_REVIEW，只有用户明确审核通过才改 ACCEPTED，之后才能下达下一阶段。

## 防止过度设计的停止规则

没有实际需求，不新增 DB / Redis / MQ / 微服务 / K8s；没有真实评测收益，不新增复杂 Planner、双层记忆、递归 Agent 或特殊 RAG 路由。新特性进入项目必须写清业务价值、最小实现、测试、回退方案。
