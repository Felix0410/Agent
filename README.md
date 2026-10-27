# PaperWeave Research Agent — V2 设计与开发仓库

> 当前仓库状态：**设计文档已启动，应用代码尚未导入；所有 V2 功能均为规划，不代表已经实现。**
>
> 更新日期：2026-10-27。开发原则：保留 PaperWeave 科研论文工作台，增强 BRAG 式知识构建，独立新增 Deep Research，并通过可重复评测验收；不扩展到通用办公。

## 一句话产品定义

面向个人研究者的**证据可追溯科研工作台**：管理和精读论文，从论文、章节、图表与算法中检索证据；在此基础上执行长程文献调研、论文发现、结构化抽取、跨论文可比性分析及研究报告交付。

## 文档导航

| 文件 | 用途 |
| --- | --- |
| [00 产品决策](docs/00-CHARTER.md) | 目标、边界、版本与开发原则 |
| [01 完整功能说明](docs/01-FULL-PRODUCT-SPEC.md) | **原版全部主要功能 + V2 新增功能 + 各模块技术实现路线** |
| [02 目标架构](docs/02-ARCHITECTURE.md) | 数据流、模块职责、状态与新旧隔离 |
| [03 BRAG 改进](docs/03-BRAG-BUILD.md) | B01/B02/B03：分层知识、多视角索引、分层检索 |
| [04 Deep Research](docs/04-DEEP-RESEARCH.md) | 长研究任务、科研事实模型、对比与报告 |
| [05 Tools / MCP / Memory](docs/05-TOOLS-MCP-MEMORY.md) | 工具层、GitHub MCP、任务记忆与安全 |
| [06 测试和评测](docs/06-EVALUATION.md) | Baseline、消融、任务级评分和运行回归 |
| [07 任务拆分](docs/07-ROADMAP.md) | T00–T12 + B01–B03，逐包可验收 |
| [08 Codex 协作规范](docs/08-CODEX-RULES.md) | 实施约束、提交格式、证据与审批 |
| [09 终验与演示](docs/09-ACCEPTANCE-DEMOS.md) | 验收门槛、必备演示路径 |
| [10 上游事实核验](docs/10-UPSTREAM-BASELINE.md) | 原版 PaperWeave 已有的能力、边界及来源 |
| [11 进度](docs/11-PROGRESS.md) | 实施进度、提交、阻塞、验收记录 |
| [12 参考与设计决策](docs/12-REFERENCES-DECISIONS.md) | BRAG 参考、架构决策及变更规则 |

## 启动开发的顺序

首先由 Codex 执行 [T00 架构审计](docs/07-ROADMAP.md)，确认上游仓库、代码引入方式、许可证与目录情况；然后 T01 将原版源码安全引入当前仓库并建立基线，绝不可删除上述设计文档。完成 T02 公共接口后，按路线图依次推进独立任务。

**执行节奏：每次只执行一个任务包；测试、文档、Git SHA 与审核通过后，才进入下一个任务。**

## 项目出处与声明

- 原版： [PaperWeave / Agentic RAG Paper Assistant](https://github.com/zebir-sir/agentic-rag-paper-assistant)。
- BRAG 设计借鉴：小米技术公开介绍的 [Mi-BRAG](https://weibo.com/ttarticle/p/show?id=2309405174583971152010)。本项目不是小米官方产品，不声称复现其未公开的内部实现。
- 迁移上游源码时保留其许可证、版权声明与必要归属；README 中区分继承功能和本项目新增贡献。
- 本仓库当前尚未导入原版业务源码，文档涉及源码与技术栈的结论基于截至 2026-10-27 的上游文档及部分静态审查，须经 T00/T01 本地复核。
