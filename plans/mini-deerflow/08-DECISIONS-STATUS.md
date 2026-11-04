# 08 · 决策记录、技术风险与进度

## A. 已确认原则（2026-11-04）

- D01：项目定位 Mini DeerFlow，做**轻量通用多智能体任务执行系统**，不是仅科研助手或功能超越 DeerFlow 的产品。
- D02：**全新空项目**增量开发；DeerFlow 2.0 只做模块级参考，不直接 Fork 大仓或删除其源码。
- D03：先有一个可运行、可测试的端到端 Agent 主链，再逐步增加 Plan、Sub-Agent、MCP、Skills、Context、前端、Deep Research、RAG。
- D04：重视本地 AI 的上下文成本，单任务仅读必要源码、维护高密度 CURRENT_STATE。
- D05：暂不引入 Redis、MQ、微服务、K8s；具体技术按需求与测试决定。
- D06：每阶段 Codex 实现和测试后，人工审核通过才进入下一阶段。

## B. 方案建议（尚可调整）

- S01：Python 3.12+、FastAPI、LangChain / LangGraph、SQLite Checkpoint 起步。
- S02：Next.js/React Web UI；独立 API 合同而非严格仿 DeerFlow 全部 Gateway 协议。
- S03：完整目标同时包含 Deep Research、文档 RAG 和基本文件任务；执行顺序先 Agent 主链再业务。
- S04：Sub-Agent 首版有限并发、隔离消息上下文；不宣称任意中途进程崩溃后可精确恢复子任务。
- S05：高风险代码执行延后到容器沙箱。
- S06：当前 GitHub 仅为独立规划分支，未来创建独立新仓库并迁移 docs 是 P00 任务。

## C. 仍需 P00 实际验证的事实

- LangChain/LangGraph 与 Python 版本及依赖兼容性；具体模型 API 适配方式。
- SQLite Checkpointer 与异步 FastAPI 使用条件；前后端流事件接口。
- 模型定价/Token 预算与工具可用性。
- 适合个人项目的具体文档解析器、向量索引存储与部署方式。
- 宿主机环境是否具备 Docker 安全隔离；不具备时禁用代码执行。
- 独立仓库最终名称/位置（不应擅自覆盖现有 PaperWeave 仓库）。

## D. 主要风险

| 风险 | 级别 | 缓解 |
|---|---|---|
| 单个开发任务和 AI 上下文过大 | 高 | 阶段切片、文件索引、CURRENT_STATE |
| Checkpoint 被误认为后台子 Agent 精确恢复 | 高 | 明确状态边界，故障注入，不能盲目重放副作用 |
| Agent 可以未经隔离执行 Shell/访问文件 | 高 | 最小工具白名单、路径隔离、沙箱验证 |
| 规划过多、长期不能运行 | 高 | P01 起每阶段必须可运行可测试 |
| 用大量框架堆叠掩盖核心能力 | 中 | 业务驱动选型、ADR 与性能证据 |
| RAG 引用不真实 | 高 | 原文位置、检索-回答分离的评测 |
| 上游代码使用与个人贡献无法区分 | 中 | 固定来源、MIT 合规、改造日志和可重复评测 |

## E. 实际进度账本

| 任务 | 状态 | 实际成果 |
|---|---|---|
| 项目范围与系统架构规划 | DRAFT_REVIEW | GitHub 隔离分支中的设计文档，不代表功能实现 |
| 上游 DeerFlow 静态源码审查 | PARTIAL_STATIC_REVIEW | 已核查关键目录、部分 Agent/Run/Sub-Agent/Skills/Runtime 代码；未本地启动 |
| P00 | NOT_STARTED | 需创建正式独立仓库并验证工程环境 |
| P01~P10 | NOT_STARTED | 无业务代码、无运行测试、无性能指标 |

## F. 阶段复盘记录模板

阶段编号/标题：
基线 Git SHA → 完成 SHA：
实际变更文件：
实现主流程：
上游参考文件（若使用）及为何参考：
测试命令、结果、耗时/成本（若适用）：
失败/未测试项：
安全与状态一致性风险：
ADR / 技术债：
人工审核状态：NOT_STARTED / IN_PROGRESS / PENDING_REVIEW / ACCEPTED / BLOCKED / DEFERRED。

## G. 现在不执行的事

不启动新模块编码、不把原 DeerFlow 仓库克隆到当前 Agent、不修改 PaperWeave 既有 README/docs/main、不更新任何项目进度为已实现。
