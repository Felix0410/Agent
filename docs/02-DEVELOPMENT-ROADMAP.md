# 02 · 从零开发 Mini DeerFlow 的完整实施流程

版本：v1.0；状态：计划，所有 P00–P12 尚未开始。总体目标参见 01。
本文件既是阶段路线图，也是 Codex 交付合同。任何阶段都不能为了赶进度跳过可运行主线与真实性测试；每次只发一个任务包，人工审核后再进入下一阶段。

## 一、开发总原则和任务治理

1. 第一优先级是“最小、干净、可运行、可验证”的端到端链路，不是目录数量或依赖丰富度。
2. 引入任何新技术先解释：是什么、解决什么问题、为什么在当前阶段需要、关键执行过程、替代方案。
3. 独立开发，不 Fork 或一次性克隆 DeerFlow。只阅读本阶段相关源码，取其必要不变量与经验。
4. 共享 Agent Harness，三项业务（Research / 文档 RAG / 文件任务）通过 Skills、Tools、Services 扩展。
5. 不提前引入 Redis、RabbitMQ、K8s、微服务、多租户或复杂高可用。
6. 每阶段明确输入、输出、成功路径、失败路径、状态约束、单元/集成/真实 Smoke 测试与 Git SHA。
7. 禁止用模拟响应作为真实 E2E 成功证明；Mock 单测与真实模型测试分别记录。
8. 设计变更需 ADR；重要边界被推翻时先暂停，讨论后再改。
9. 阶段完成后只总结与审核，不自动开展下一阶段。

## 二、总体阶段及交付定义

| 阶段 | 主题 | 完成后真正具备的能力 | 关键依赖 |
| --- | --- | --- | --- |
| P00 | 独立工程基线 | 可以安装/测试/启动基础服务 | 无 |
| P01 | 最小 Agent 及 Tool | 用户请求→模型→真实工具→结果 | P00 |
| P02 | API、Thread、Run 与 SSE | 多轮会话、状态、流式响应 | P01 |
| P03 | 文件 Workspace / Artifact | 上传→受控读取→保存/下载 | P02 |
| P04 | Todo 与 Sub-Agent | 动态计划、子任务委派与并发 | P02、P03 |
| P05 | 工具注册、MCP、Skills | 能按需扩展工具和任务规范 | P04 |
| P06 | 上下文与预算管理 | 摘要、Token 预算、循环与输出限制 | P02–P05 |
| P07 | Web Workspace | 浏览器可完成基础/复杂任务 | P02–P06 |
| P08 | Deep Research | 真实联网调研并交付引用报告 | P04–P07 |
| P09 | 文档 RAG | 多文档问答和证据回溯 | P03、P05、P07 |
| P10 | 稳健性/安全/恢复 | 真实故障和取消条件下行为正确 | P02–P09 |
| P11 | Agent 评测与优化 | 固定任务集、消融、延时成本报告 | P08–P10 |
| P12 | 完整交付 | 可部署、可复现、可演示、有源码归属 | 全部 |

虽然以编号表示顺序，允许基于依赖重排非核心任务，但需记录原因、确认当前仍可测试并由用户批准。

## 三、P00 — 工程初始化与真实环境核对

目的：为新项目建立小型稳定工程，而不是先写十几个空模块。

范围：
- 核实仓库仅有规划时的真实内容、Git 分支与工作区，不覆盖未授权文件。
- 选择 Python 版本、包管理方式与依赖锁、FastAPI/Pydantic/LangChain/LangGraph 兼容组合。
- 构建最小 Python Package、环境变量模板（不写真实密钥）、基础健康检查、pytest/ruff 等简单工具。
- Git 忽略本地密钥、缓存、向量索引、用户文件和生成产物。
- 迁移本文档并建立 docs/CURRENT_STATE.md（简短当前真实状态）、docs/DECISIONS.md、docs/PROGRESS.md。
- 核实 DeerFlow 固定 v2.0.0 版本及 MIT，记录源码引用方式；不引入整仓源码。

非目标：不实现 Agent、不上 DB、Docker、Redis、前端、MCP。
必验：干净环境 install / lint / pytest / 启动 health 均有真实结果；无密钥进 Git；README 写清运行命令与状态。
风险：依赖版本冲突、本地模型 API 兼容差；必须在报告中记录。
参考：03 的 AgentFactory、backend/pyproject.toml（理解而非盲目复制）。
任务拆包：P00A 环境/仓库审查；P00B 最小工程与测试基线。

## 四、P01 — 单 Agent 最小主链

目的：模型真正调用一个只读工具，并根据工具结果回答。

实现步骤：
- 定义 Provider-neutral ModelFactory（只实现一个主要模型提供方）；设置超时、重试上限。
- 使用当前 LangChain/LangGraph 认可的 Agent 构造 API（参考 DeerFlow create_agent 思路），一开始不自己写复杂 StateGraph。
- 实现一个具有明确输入输出 Schema 的只读工具，例如计算/已知数据查询；工具运行有日志和出错语义。
- 模型收到消息 → 决定 Tool Call → 工具执行 → 模型观察 ToolMessage → 返回最终回答。
- 最小 CLI 或 HTTP Debug 入口；Mock LLM 单测验证调用次序，真实模型 Smoke 验证至少一次真实 Tool Call。
- 在此阶段不实现 Sub-Agent、RAG、上下文摘要。

关键设计：Prompt 不应承诺不存在的功能；Tool 不能用“返回假数据”制造成功。
验收：能运行无工具对话和工具对话；模型异常和工具异常可测试；程序退出资源正确关闭；至少一次真实工具调用的脱敏记录。
参考：agents/factory.py、agents/lead_agent/agent.py、tools/tools.py。
拆包：P01A 模型与 Agent；P01B Tool 合同和完整 Smoke。

## 五、P02 — 服务化：Thread / Run / Checkpoint / SSE

目的：从单次脚本转为带状态、多轮、流式的服务。

实现：
- 定义 Thread 与 Run ID，创建最小 FastAPI Router；一个 Thread 同时最多一个活动 Run。
- LangGraph Checkpointer 使用兼容的 SQLite Async 实现，按 thread_id 绑定图状态。
- RunRepository 管理 CREATED/RUNNING/SUCCEEDED/FAILED/CANCELLED 等业务状态及合法转换。
- RunExecutor 启动 Graph 并统一处理异常；EventPublisher 把 messages/tool events 映射为稳定 SSE Envelope。
- 增加查询 Run、历史会话及取消入口；明确断开 SSE 不等于取消 Run。
- 失败时 Run 终态与 Checkpointer 记录按实际情况处理；不承诺自动恢复进行中的任意 Tool。
- 建 API 结果/错误的最小契约和前端订阅示例。

验收：多轮对话从 SQLite 状态读回；Run 终态正确；SSE 能收到开始、增量和终结；取消幂等；重启后历史可查询；同 Thread 并发冲突有确定错误。
参考：runtime/runs/manager.py、worker.py、runtime/stream_bridge/base.py、runtime/checkpointer/async_provider.py、app/gateway/routers/threads.py。
拆包：P02A Thread/Run；P02B Checkpoint；P02C SSE/取消与契约测试。
风险：混用同步 Checkpointer 与异步 astream；事件结束与状态落库顺序。

## 六、P03 — Workspace、上传及可下载产物

目的：让 Agent 的文件操作具备真实业务价值和安全边界。

实现：
- 每会话建立私有 Workspace 根目录，分 uploads / workspace / outputs；运行时只暴露虚拟路径。
- API 上传文件校验类型、大小、数量、文件名、内容类型与归属；生成 Artifact 元数据。
- 实现 list_files、read_file、write_file 或等价受控工具；限制读写范围，不可执行宿主机 Shell。
- 文件写入使用临时文件+原子替换；同名覆盖有明确策略；防止并发写互相踩踏。
- 实现成果文件列表和下载接口，返回正确 MIME、大小、内容。
- 无论 Tool 直接调用还是 MCP 提供文件引用，都要校验路径归属。

验收：上传/读取/写入/下载真实文件 E2E；../ 穿越、符号链接、绝对路径、超大文件、越权访问被拒绝；产物下载正确；服务端日志不泄露敏感文件内容。
参考：sandbox/security.py、sandbox/local/local_sandbox.py、sandbox/tools.py、Gateway uploads/artifacts 路由。
拆包：P03A 存储与安全；P03B Tool/API/Artifact；P03C 安全测试。
风险：LocalSandbox 不等于独立安全沙箱，严禁在此阶段打开任意 Bash。

## 七、P04 — Todo、任务规划与 Sub-Agent

目的：Lead Agent 能对复杂目标进行动态计划与有限并发分工。

实现：
- 增加结构化 Todo，支持创建、更新、状态合并和事件通知；简单任务可不规划。
- SubAgentConfig 包含 type/prompt/model/tools/skills/max_turns/timeout；初期保留 general 与 research 角色，避免每个角色大量自定义代码。
- task 工具委派给 Dispatcher，生成 task_id，分配隔离消息上下文与子工具白名单。
- 子 Agent 可继承明确允许的 Workspace/来源引用，不继承父全部消息与秘密。
- 并发限额、超时、取消、结果归并和每个任务状态；工具授权不可由 Prompt 绕过。
- 父任务 Checkpoint 不等于子任务恢复；首次不做分布式/跨进程持久子任务执行。
- 加入子任务的流式开始、进行、成功和失败事件。

验收：一项任务拆为两个独立子任务；工具调用真实可见；达到并发限额时排队/拒绝确定；某子任务失败父任务不会误报所有子任务成功；禁止子 Agent 递归 task；超时终态正确。
参考：tools/builtins/task_tool.py、subagents/executor.py、subagents/config.py、agents/middlewares/todo_middleware.py、thread_state.py。
拆包：P04A Todo；P04B 串行子任务委派；P04C 并发/超时/取消；P04D 隔离测试。
风险：线程/任务池内存状态、工具副作用结果未知、父子 Checkpointer 继承错误。

## 八、P05 — Tools / MCP / Skills 扩展体系

目的：新增工具与业务指导不需要修改 Lead Agent 核心。

实现：
- Tool Registry 统一名称、参数 Schema、权限、超时、错误、成本标签和去重。
- MCP Client 使用成熟 SDK/Adapters，选择一个只读外部 MCP Server，连接/超时/失败降级有测试。
- Skills 实现 SKILL.md frontmatter（名称、描述、约束）、目录发现、显式激活、与任务匹配后的按需加载。
- 将 allowed_tools / deny_tools 真正接入执行器和子 Agent，而非只写 Prompt。
- 精简配置并保持注入接口；不实现复杂工具市场、动态自动安装和未经审核的远程代码。
- 对 MCP 返回的数据、URL、文件路径进行不可信数据处理。

验收：不改 Lead Agent 可以新增已注册工具；MCP 实际调用成功；工具同名冲突确定；无权工具不会因 Skill 或委派被放行；坏 SKILL.md 有清晰报错。
参考：tools/tools.py、mcp/client.py、mcp/tools.py、skills/parser.py、skills/tool_policy.py、agents/middlewares/skill_activation_middleware.py。
拆包：P05A Registry；P05B MCP；P05C Skills；P05D 权限回归。

## 九、P06 — 上下文管理、成本和循环防护

目的：让多步任务在 Token/时间受控的情况下运行。

实现：
- 统计每次调用的输入/输出 Token（支持提供方可用字段）、Run 汇总与各 Sub-Agent 贡献。
- 定义请求级预算：最大工具调用次数、最大迭代、最大 wall-clock 时间、最大输出文本长度。
- 工具输出过大时保存在 Workspace，只向 Agent 提供摘要/摘录/引用；ToolMessage 可追踪原产物。
- 根据估算 Context Size 触发 Summarization；保护最新交互、当前 Todo、用户约束、已验证证据、文件引用。
- 引入循环调用检测和可解释终止；摘要本身是额外模型调用，应计入预算和 Trace。
- 先比较“无摘要/有摘要”效果，再追求复杂策略；不加入长期记忆以拖延主线。

验收：长任务不会无限调用；触发摘要之后仍记得目标与待办；预算触发时产生明确状态；每 Run 输出 Token/耗时/工具调用统计；对照结果记录。
参考：summarization_middleware.py、tool_output_budget_middleware.py、loop_detection_middleware.py、token_usage_middleware.py。
拆包：P06A Budget/Usage；P06B Summary；P06C Tool Output/Loop；P06D 回归与对比。
风险：错误摘要导致证据丢失、模型 token 估算不准。

## 十、P07 — Web Workspace

目的：在浏览器中真实使用现有 Agent，而不是创建一个好看的静态演示。

实现：
- React/Next.js 项目、基础布局与会话侧栏；Web Client 调用自己的 API/DTO。
- 聊天输入、SSE token、Tool / Todo / Sub-Agent 事件归并；按 run_id 管理 UI。
- 运行中/取消/失败/完成状态；重新加载后从服务端恢复当前可查询信息。
- 文件上传、浏览、下载；提供简单模型/任务设置，不做完整平台管理中心。
- 兼容空结果、超时、网络断线、历史 Thread 无数据等错误态。
- 不能为 UI 便利而修改服务端的状态语义；必要时更新 API 合同和 E2E 同步验证。

验收：从浏览器新建会话、对话、查看子任务、使用上传文件、下载真实产物和取消运行；前端编译与 E2E 通过；不展示假进度。
参考：frontend/src/core/tasks/context.tsx、frontend/src/core/api/stream-mode.ts、frontend/src/components/workspace/，仅借鉴交互和事件设计。
拆包：P07A 薄 UI；P07B 运行事件；P07C 文件/UI 状态；P07D E2E。

## 十一、P08 — Deep Research 业务

目的：用已有底座交付第一条完整复杂任务链路。

实现：
- 设计 Research Skill 的输入、研究目标、来源策略、报告模板、停止条件。
- 增加 search_web / fetch_page 工具适配；返回真实 URL、抓取时间、标题和可信源摘要；建立 EvidenceRecord。
- 多轮搜索去重与覆盖面检查；根据研究主题选择 Sub-Agent 并行调查；收敛证据。
- 输出 Markdown：背景、关键发现、对比、来源、局限和未验证项；引用指向实际检索过的页面。
- 对可核验事实建立引用核查流程（至少来源存在与人工抽样核对）；生成真实 Artifact。
- 能对搜索超时、页面不可读和某个子任务失败正确降级。
- 不自动下载收费/未授权全文，不宣称实现通用学术系统综述。

验收：至少五个固定问题可复跑；至少一个真实复杂任务展示多次工具调用和委派；报告与引用文件实际存在；模型生成的虚构 URL 被检测/标记。
参考：skills/public/deep-research/SKILL.md、systematic-literature-review/SKILL.md 和上游 task 工具。
拆包：P08A Source Adapter；P08B Research Skill/Flow；P08C Evidence/Report；P08D 真实 E2E。
风险：API 搜索配额、访问限制、伪来源与失效网页。

## 十二、P09 — 文档解析与 RAG

目的：在独立 KnowledgeService 中构建真实可检索的文档知识库。

实现：
- 选择实际可复现的文本型 PDF 解析方案；抽取页码/章节并保留原文与文件版本。
- 定义 Chunking、Embedding 与 Metadata；小规模索引先跑通，后根据规模决定是否上 pgvector。
- 实现 search_knowledge 工具；结果包含真实片段、文档 ID、页码/章节、得分和引用位置。
- 可以引入简单混合检索与 rerank，但必须先有基础版对照，测到增益再选择默认策略。
- 支持用户选择文档 scope、跨文档问题、无证据拒答、引用输出和文档更新/重建索引。
- UI 关联上传状态、解析/索引进度和文档引用。
- 不把生成的补充说明当成原文；扫描 OCR、复杂表格/图片和海量文档后置。

验收：至少两份真实 PDF 成功索引；至少十个金标 QA/检索问题；可定位原始段落；无命中不编造；文档版本变更和索引一致性有测试。
参考：上游文件工具和 Skills 的接入机制；RAG 具体解析/检索需要独立验证相关开源库，不能把 Deep Research Skill 当成 RAG 实现。
拆包：P09A Parser/Chunk；P09B Index/Retrieval；P09C Tool/Citation；P09D QA/Eval。
风险：解析质量、页码映射、Embedding 版本迁移、索引更新原子性。

## 十三、P10 — 可靠性、安全和恢复边界

目的：形成能真实解释取消、重试与服务重启行为的单用户系统。

实现：
- Run/Task 幂等终态与取消协作；服务启动核查未终结 Run。
- 根据无副作用/有副作用工具分类，决定可自动重试、需人工确认或保持 UNKNOWN。
- 限制文件/网络权限，MCP 只读白名单，Prompt Injection、敏感信息和路径攻击测试。
- 故障注入：LLM 超时、MCP 断连、Sub-Agent 超时、SSE 中断、服务器中断、SQLite 锁冲突。
- 若需要执行任意 Python/Shell，必须先设计并验证容器沙箱隔离；否则该功能不交付。
- 测试不同失败路径下真实的 Run / Event / Checkpoint 一致性，保留缺陷记录。

验收：无错误假成功；取消不继续发起新增危险工具；孤儿 Run 能被识别；外部写状态未知不会被自动盲重试；越权文件操作被拒绝。
参考：runtime/runs/manager.py、runtime/runs/worker.py、Gateway 启动恢复与 sandbox/security 及上游对应测试。
拆包：P10A 状态与恢复；P10B 安全；P10C 故障注入；P10D 资源与性能。

## 十四、P11 — 评测、消融和专项优化

目的：让项目结果可复现、可比较、可以在面试中说明。

实现：
- 建固定 Research、RAG、文件任务三类数据集，每样本包含可核验要求和评分方法。
- 构建运行 Snapshot：Git SHA、模型、Prompt/Skill 版本、工具版本、输入数据、执行时间与环境。
- 执行单 Agent vs Sub-Agent、无摘要 vs 摘要、基础检索 vs 改进检索等有意义消融，明确不同任务适用条件。
- 度量任务完成率、引用正确率/支持率、RAG Recall@K、失败状态正确率、Token、成本与 P50/P95 耗时。
- 对失败案例做根因分类，不做只展示好案例的成功率图。
- 只在真实数据证明有业务价值时引入更复杂机制。

验收：评测脚本可运行、样本可访问或合法提供，结果带版本、失败样例和原始统计；不预设分数或声称上游成果。
参考：DeerFlow 现有 tests 的思想；实际指标由自己执行产生。
拆包：P11A Eval Harness；P11B Baseline；P11C 消融；P11D 结论/回归。

## 十五、P12 — 最终集成、部署与求职展示

目的：成为真正可展示、可维护的独立 Agent 项目。

实现：
- README 只写真实已实现能力；快速启动、环境变量、演示与常见问题。
- 提供可复现本地运行或 Docker Compose（单机），明确外部 API/模型需要的配置。
- 核查密钥、许可证、依赖安全、文件隔离与 API 对外风险。
- 三条业务演示真实运行，产物与来源可追踪，错误状态可重复。
- 架构图、设计决策、与 DeerFlow 区别、自主设计模块、真实评测、核心故障案例形成项目材料。
- 清理无用脚手架、禁用不支持能力，保持 CI/文档与实际代码一致。

验收：在干净环境按 README 能启动；基础与三条业务 E2E 可执行；无伪造数据；官方 MIT 许可和借鉴来源处理正确。
拆包：P12A 部署；P12B 安全审查；P12C 演示与文档；P12D 最终验收。

## 十六、阶段交付统一模板

每个任务包必须提交：
- 任务 ID、用户需求、范围/不做项、源代码参考（固定路径）。
- 当前最小端到端流程、关键数据合同与安全边界。
- 变更文件和主要设计决策，实际可运行命令。
- 单元/集成/真实模型测试逐项结果、失败或未运行原因。
- 真实日志/产物/指标位置（脱敏）、Commit SHA。
- 与上游设计的差异、回退方案、已知风险和下次待办。
- 最终状态 PENDING_REVIEW；等待用户反馈，不自动继续任务。

## 十七、进度与暂停原则

状态：NOT_STARTED / IN_PROGRESS / PENDING_REVIEW / ACCEPTED / BLOCKED / DEFERRED。
只有人工明确验收后阶段变为 ACCEPTED。出现测试失败、外部数据权限不明、工具越权、重复副作用、状态不一致等则 BLOCKED，先修复当前阶段。
在 P00 前不声称有可运行功能。详细测试合同见 05，协作和部署规则见 06。
