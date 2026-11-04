# Mini DeerFlow — 轻量级通用多智能体任务执行系统

> 项目状态：完整设计已完成，业务代码尚未开始；日期：2026-11-04。
> 本仓库已正式转为 Mini DeerFlow 项目，旧科研工作台方向不再继续。旧版资料只保留在 Git 历史中。
> 开发方式：从零建立自己的模块化单体，不 Fork 或复制 DeerFlow 整体工程；按需研究 DeerFlow 2.0 具体文件。

## 项目定位

构建可自主规划、调用工具、委派子智能体、使用 Skills/MCP、管理长任务与上下文、保存文件产物的通用 AI Agent。以个人使用与工程化学习为第一目标，追求功能完整、行为可靠、代码可解释，而非重建一套企业级 Agent 平台。

## 目标业务

1. 联网深度研究：开放主题 → 规划 → 多源检索 → 子任务分析 → 证据核验 → 可引用的报告。
2. 多文档问答：上传 PDF/Markdown/TXT → 解析与索引 → RAG 检索 → 跨文档分析 → 原文引用。
3. 通用文件任务：多步骤 Todo → 受控工具/文件读写 → 任务执行 → 生成可下载的报告或数据文件。

单轮普通对话和简单工具操作是这三类业务的共同基础。业务功能通过 Tool、Skill 和独立服务接入，不和 Agent 主循环硬耦合。

## 关键能力

Lead Agent、LangGraph 状态、Plan/Todo、Sub-Agent、Tool Registry、MCP、Skills、文件 Workspace、Checkpoint、Run/Task 生命周期、SSE、上下文压缩、Web UI、业务评测。

首版默认单用户、单机、单 FastAPI Worker。不开启不可信 Shell 执行，不提前部署 Redis、RabbitMQ、Kubernetes、微服务或复杂多租户系统。

## 详细文档

| 文件 | 核心内容 |
| --- | --- |
| [01 业务需求与总体架构](docs/01-PRODUCT-AND-ARCHITECTURE.md) | 产品定位、所有业务能力、系统分层、对象模型、端到端链路、状态与安全 |
| [02 完整开发流程](docs/02-DEVELOPMENT-ROADMAP.md) | P00–P12 任务包、顺序、每阶段实现方案、依赖、验收、交付 |
| [03 DeerFlow 源码地图](docs/03-DEERFLOW-SOURCE-MAP.md) | 固定版本、具体源文件、如何借鉴、哪些设计不照搬 |
| [04 模块与接口契约](docs/04-CONTRACTS-AND-DESIGN.md) | Tool / Sub-Agent / Event / API / Workspace 契约与错误语义 |
| [05 测试和 Agent 评测](docs/05-TESTS-AND-EVALUATION.md) | 单测、集成、E2E、故障注入、研究和 RAG 指标、终验 |
| [06 Codex 协作及部署](docs/06-WORKFLOW-AND-OPERATIONS.md) | AI 上下文预算、任务交付模板、Git/安全、环境与部署 |
| [07 决策与进度](docs/07-DECISIONS-AND-PROGRESS.md) | 确认的设计、未决事项、阶段账本、风险与审查记录 |

## 快速理解开发顺序

P00 基线 → P01 单 Agent → P02 API/会话/SSE → P03 Workspace → P04 Plan/Sub-Agent → P05 MCP/Skills → P06 长任务与上下文 → P07 Web UI → P08 Deep Research → P09 文档 RAG → P10 安全与故障恢复 → P11 评测优化 → P12 发布验收。

这是逻辑依赖而不是承诺工期。每一阶段实现最小可运行链路、完成测试、单独提交，再等待人工审核。

## 参考与授权

- DeerFlow 上游：https://github.com/bytedance/deer-flow
- 固定研究基线：v2.0.0，commit 7e7f0410797693cf882594555ba414e0361d4c6f。
- 上游许可：https://github.com/bytedance/deer-flow/blob/v2.0.0/LICENSE （MIT）。若复制/改编任何源码，保留对应版权许可与来源声明。
- 上游使用仅限技术参考；本项目实际功能、性能、测试结果需以自己的代码与证据为准，不能冒充上游成果。

## 当前事实

目前只有设计文档。没有已完成的 Agent、前端、数据库、评测结果或部署性能。首次开发任务是 P00，不可跳过工程基线直接堆砌模块。
