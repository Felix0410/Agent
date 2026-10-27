# 11 · PaperWeave V2 执行进度账本

**本次状态：仅完成设计文档入库，尚未导入原版业务代码，也未进行任何 V2 编码/测试。**
更新日期：2026-10-27。任务状态在 Codex 完成后仍需人工审核。

## 状态约定

NOT_STARTED（未开始） / IN_PROGRESS（执行中） / PENDING_REVIEW（待人工审核） / ACCEPTED（已验收） / BLOCKED（阻塞） / DEFERRED（主动延后）。

## 任务表

| 任务 | 名称 | 状态 | Commit SHA | 验收证据 |
| --- | --- | --- | --- | --- |
| T00 | 上游审计与引入方案 | NOT_STARTED | — | — |
| T01 | 引入上游并建立旧版基线 | NOT_STARTED | — | — |
| T02 | 共享科研服务接口 | NOT_STARTED | — | — |
| B01 | 层级知识构建 | NOT_STARTED | — | — |
| B02 | 上下文/多视角索引 | NOT_STARTED | — | — |
| B03 | 分层检索与消融 | NOT_STARTED | — | — |
| T03 | Research Task 模型与 API | NOT_STARTED | — | — |
| T04 | 最小 ResearchTaskGraph | NOT_STARTED | — | — |
| T05 | 结构化科研事实抽取 | NOT_STARTED | — | — |
| T06 | 跨论文比较与报告 | NOT_STARTED | — | — |
| T07 | 文献自动发现与确认 | NOT_STARTED | — | — |
| T08 | Checkpoint、取消与恢复 | NOT_STARTED | — | — |
| T09 | Research Tasks 前端 | NOT_STARTED | — | — |
| T10 | Research Agent Eval / Trace | NOT_STARTED | — | — |
| T11 | GitHub MCP Client | NOT_STARTED | — | 第二优先级 |
| T12 | 集成、安全与最终交付 | NOT_STARTED | — | — |

## 每次任务后增加一条记录

### 记录模板

**任务编号：**  
**基线 SHA / 结束 SHA：**  
**Codex 开始与完成时间：**  
**变更文件摘要：**  
**核心设计选择：**  
**单测/集成/回归真实命令与结果：**  
**评测样本/模型/指标与报告路径（如适用）：**  
**失败或未运行项及原因：**  
**兼容性、安全与数据迁移风险：**  
**人工审核结论：ACCEPTED / 修复后复审 / BLOCKED**  
**相关 ADR：**

## 工作日志

- 2026-10-27：建立 V2 最终设计文档集，约定采用原版科研工作台 + BRAG Build 改进 + 独立 Deep Research Agent 的路线；文档提交不代表任何业务功能已实现。

## 下一动作

向 Codex **仅提交 T00**，审计上游架构、最新版本、许可和迁移方式。通过审核后再执行 T01。不得立即启动 B01 或 T04 编码。
