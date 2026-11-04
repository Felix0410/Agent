# Mini DeerFlow

轻量级通用多智能体任务执行系统。**独立从零开发，按模块参考 DeerFlow 2.0，不 Fork 原仓库。**

状态：**方案已确定，业务开发尚未开始。** 本仓库此前的 PaperWeave 设计已终止，旧文档仅可从 Git 历史中查阅。

## 要做成什么

一个能在 Web 中使用的任务型 Agent：用户给出目标，主 Agent 直接答复或动态制定 Todo、调用工具、委派 Sub-Agent；系统管理会话、工具权限、文件工作空间与运行状态，最终交付回答或可下载文件。

三个最终演示场景：

1. **Deep Research**：多轮联网检索、多视角子任务、证据汇总、生成带来源的报告。
2. **文档 RAG**：上传 PDF / Markdown / TXT、解析索引、跨文档检索、带原文定位的回答。
3. **文件任务**：按计划操作受控文件工具，生成真正可下载的 Markdown / CSV / JSON 产物。

## 开发方案已固定

- **后端**：Python 3.12、uv、FastAPI、Pydantic、LangChain + LangGraph。
- **模型**：先接入一个验证通过的 OpenAI 兼容聊天模型提供方，统一 ModelFactory。
- **状态**：SQLite + LangGraph SQLite Checkpointer，单 Worker；Run 状态与图状态分离。
- **前端**：React + TypeScript + Vite，薄 Web 工作台；SSE 流式输出。
- **扩展**：统一工具注册、MCP Adapter、按需加载的 SKILL.md。
- **文档知识库**：Docling（文本型 PDF）+ Embedding + Chroma 本地向量索引；先做基础检索，验证后再升级。
- **测试**：**每次只运行本次新增/修改功能的测试，以及直接受影响接口的必要测试；不做每阶段全量回归。**
- **交付**：单机部署，后期 Docker Compose；暂不引入 Redis、RabbitMQ、微服务、K8s、复杂权限体系。

上述技术方向固定；第三方库具体小版本在 P00 实际验证并锁定，如存在兼容性问题需记录调整原因。

## 主文档与阶段进度

| 文档 | 作用 |
|---|---|
| [总体业务与系统架构](docs/ARCHITECTURE.md) | 功能范围、真实业务流程、模块边界、状态、接口、技术栈、DeerFlow 源码参考 |
| [完整开发方案](docs/DEVELOPMENT.md) | P00–P09 增量开发任务、局部测试规则、每阶段验收、Codex 协作 |
| [阶段进度记录](docs/progress/) | P00–P09 每阶段独立记录真实代码变更、局部测试、Commit 与审核结论 |

**执行原则**：一次一个阶段中的一个小任务；先最小可运行链路；测试当前变更；记录 Git SHA 和真实结果；等用户审核通过再继续。P00 尚未启动。

参考上游：[bytedance/deer-flow v2.0.0](https://github.com/bytedance/deer-flow/tree/v2.0.0)，固定 commit 为 `7e7f0410797693cf882594555ba414e0361d4c6f`。参考实现不等于复用全部源码；实际复制或改编受许可代码时保留适用的 MIT 版权与许可声明。
