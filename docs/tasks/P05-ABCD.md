# P05-A/B/C/D · ToolRegistry + MCP + Skills — Codex 精确实施合同

> 状态：**READY_FOR_CODE / 尚未实施**。本文件只设计本期必须执行的具体代码，用户“设计 P5”**不等于授权立即运行本地 Codex**。在后续用户明确启动编码时，按 A→B→C→D 连续开发，**每段都必须**前端同步、局部测试、单独提交 SHA；任一关键失败立即停止。  
> 仓库：`Felix0410/Agent`；分支：`feat/p05-tools-mcp-skills`（从包含 P04 全部代码的 `feat/p04-planning-subagents` 派生）。P02/P03/P04 的 `PENDING_REVIEW` 不表示代码缺失，也不应自动改成 ACCEPTED。  
> 合同优先级：[docs/DEVELOPMENT.md P05](../DEVELOPMENT.md) → 本文件 → [AGENTS.md](../../AGENTS.md) → 实际代码/锁版第三方签名。如需设计变更，先报告而不是让本地 AI 重新选型。

## 前置核验：所有子任务共用

1. `git status -sb`、`git log -8 --oneline`、`git branch -vv`、`git fetch`，确认 P05 来自 P04 完整实现。保护未提交改动、用户 .env、已有业务 SQLite 和 Workspace，不执行 reset/clean/force push，不从 main（缺 P02-P04）重新实现。
2. **真实当前文件路径**：`backend/src/minideerflow/agents/{lead,context,state}.py`；`runtime/{runner,streaming,task_registry,plan_repository}.py`；`tools/{calculator,file_tools,todo_tool,task_tool}.py`；`agents/subagents/{config,dispatcher,executor}.py`；`frontend/src/{App.tsx,components/RunStatus.tsx,components/ChatPanel.tsx,api/runtime.ts}`。不要造第二个 Runner、Graph or Workspace；P04 `write_todos` 返回 LangGraph `Command` 且必须完整透传。
3. 配置路径以 backend 为基准，本地 Python 3.12 uv 锁版环境；只对临时模型/SQLite/Workspace/本地 MCP 测试进程进行自动化验证。不从用户真实密钥中推断 MCP 凭据，不记录用户文档正文到日志。
4. 先 Fake 验证 `langchain.agents.middleware.AgentMiddleware.awrap_tool_call` 与当前 `create_agent(middleware=[...])` 的真实调用签名和 ToolRuntime，确保可以把 **Command 保持原对象返回**、ToolMessage ID/status 不丢失，再实施 A。失败立即 BLOCKED，禁止写自制 ToolNode 循环。MCP 相关 API 只根据 A 后的锁定版本进行真实兼容测试。

## P05-A：ToolRegistry + ToolGuardMiddleware + 前端目录

**新增**：
- `backend/src/minideerflow/tools/registry.py`：`ToolDefinition` / `ToolPolicy` / `ToolRegistry`；全局工具名唯一，源 builtin/mcp/skill，权限 read/write/orchestrate，timeout；接口 `register/get/list_allowed/list_catalog` 和 `register_builtin_tools`。注册现有 P04 六工具，重复报 TOOL_DUPLICATE。固定 Run Policy 全部从可信 Server Context 构造，模型没有授权权。
- `backend/src/minideerflow/tools/executor.py`：基于 LangChain `AgentMiddleware.awrap_tool_call` 的 `ToolGuardMiddleware`，先检查工具 ID/name/args、当前可信 Run/Thread、注册表权限、官方 args_schema；按 ToolDefinition 超时（不是为任务统一固定 5 秒）；handler 只执行一次，正常 `ToolMessage/Command` 原样返回，异常生成 `ToolMessage(status="error",tool_call_id=<原ID>,content="ERROR[CODE]: ...")`，不暴露 Python traceback。取消向上传播。对现有 `read_text` 64KiB 的内容不截断，对 MCP 的过大输入输出在 B 阶段处理。
- `backend/src/minideerflow/api/capabilities.py`：`GET /api/tools`，只读安全元信息，不能执行、注册或授权工具；`GET /api/skills` 可以在 C 之前返回 []。
- `frontend/src/api/capabilities.ts`、`frontend/src/components/CapabilityPanel.tsx`：最小列表显示内置工具的来源/权限，MCP/Skill 未启用时明确说明；实际 GET + 刷新按钮，没有假数据或调用按钮。
- `backend/tests/test_tool_registry.py`、`backend/tests/test_tool_guard.py`、`backend/tests/test_capabilities_api.py`：真 Fake Model+Graph+Runtime Test；不只对函数直接调用。

**修改**：
- `agents/lead.py` 支持可选 `middleware` 参数透传到现有 `create_agent`；默认行为不变。
- `agents/context.py` 扩展 `AgentRunContext` 的安全只读依赖，例如 `tool_policy`、`skill_service`（C 才赋实例）；保留 inherited P03 WorkspaceContext 和 P04 ChildContext。
- `runtime/runner.py` 从 Registry/Policy 生成原有六个 Lead 工具，而非继续手工 `tools.extend`；`AgentRunContext.allowed_tools` 与本 Run 的真实允许名称一致。仍旧调用 P04 `build_lead_agent`、`stream_agent`、`task`，不改 `RunService` 准入/Graph 恢复/终态/SSE。
- `main.py` 在 lifespan 创建 Registry，并挂载供 Runner/只读 API；未配置 MCP 不等待网络；`frontend/src/App.tsx` 挂接 CapabilityPanel，不触及 ChatPanel/FilesPanel。
- 必要时最小更新 `runtime/streaming.py` 仅为了保持 ToolTrace 对 Command+error 的语义，**优先不改**。

**A 局部验收**：正确列出六内置工具；重复/越权、模型伪造额外参数被拒；真实 `write_todos` 的 Command+Checkpoint+SQL 快照保留、`task` 的两 child 委派和 SQL 任务成功、`read_text/write_text` 文件归属/产物仍正确、独立 P01 `calculate` 没有新增外部工具；用户切换 Thread 不串 Run。跑 `test_tool_registry.py test_tool_guard.py test_capabilities_api.py` 以及直接影响 `test_todos.py/test_subagents.py/test_runner.py/test_file_tools.py/test_planning_demo.py`，Ruff 和 `npm run build`；提交 `feat(p05-a): unify tools with guarded LangChain execution`，将 SHA/真实数字追加 progress。成功后按授权继续 B。

## P05-B：本机真实 MCP HTTP 工具、审批与故障降级

**新增**：
- `core/mcp_settings.py`：严格 Pydantic 配置。根目录 `MCP_CONFIG_PATH` 缺省空 → 禁用。读取 JSON 最多 2 Servers/每Server 4 approved tools；只能 `http://127.0.0.1:port/mcp`，拒绝重定向、IP/DNS变体、用户名密码/查询/fragment，transport 只能 streamable_http。每工具准确名字与**真实描述/参数 Schema/annotation 元数据**规范化 SHA256 pin 必填；不批准任何隐式发现结果。
- `tools/mcp_adapter.py`：加载 `langchain-mcp-adapters` 的 `MultiServerMCPClient.get_tools`；逐 server 限时发现，按唯一原名验证签名/digest，生成名字 `mcp_<id>_<name>` 的 BaseTool 克隆，注册 read-only ToolDefinition；单 Server 失败只禁用该 server 工具，不破坏 builtin。ToolAdapter 真 ToolMessage/status/isError/异常需在 Fake+真实 MCP 样例中检测，不把 `readOnlyHint` 当授权；工具输出输入长度、超时、纯文本/非文本内容边界按 P05 规格。
- `backend/examples/mcp_readonly_server.py`：由官方 MCP Python SDK 的 FastMCP 运行真实 streamable_http `127.0.0.1:8765/mcp`，一个安全固定字典 `lookup_fact(topic)`，不访问本地文件/网络、无环境变量泄露或 Shell。
- `backend/config/mcp_servers.example.json`：真实工具发现后用当前确定 JSON 规范计算 SHA256，填入**实际可通过签名验证**的 pin；示例 Server 默认不连，用户显式设置 `MCP_CONFIG_PATH=config/mcp_servers.example.json` 才启用。把 pin 计算/核验命令写 README。
- `tests/test_mcp.py`：测试模型真实 LangChain ToolCall + MCP 回执、HTTP 服务关闭/断链、未批准名字/变更 digest、URL/transport/stdio 拒绝、工具重名、超限、恶意返回、非匹配 Schema、响应类型和 ToolTrace error，不消费远程服务或密钥。

**修改**：
- `backend/pyproject.toml`/`uv.lock` 只加 `langchain-mcp-adapters` 和兼容安全版 MCP SDK（验证已知安全补丁，禁止旧版）；
- `main.py` 在 lifespan 在 builtin 后尝试注册批准的 MCP，安全失败只标状态；Runner 使用含 MCP 的当前 Registry 快照；
- `api/capabilities.py` / `frontend/src/components/CapabilityPanel.tsx` 真实显示启用、离线、未批准/不可用状况，server 地址和证书/token 不出现在浏览器列表；
- `.env.example` 追加 `MCP_CONFIG_PATH=` 注释，不能修改用户 `.env`。

**B 局部验收**：使用真实 MCP 进程进行 Streamable HTTP 握手并调用 `mcp_demo_lookup_fact(topic="langgraph")`，在本地 Run 工具轨迹看到调用与回执；模型尝试调用未批准 tool、跨地址、未知参数必须失败；Server 下线时内置 calculate/file/todo/task 仍可用，服务恢复后重启后端能重新注册。测试 + Ruff + TS Build + HTTP Smoke。提交 `feat(p05-b): connect approved local read-only MCP tools`，进度记录后继续 C。

## P05-C：SKILL.md 安全解析与按需 Tool

**新增**：
- `skills/models.py` / `skills/loader.py`：最多10个 `backend/skills/public/<skill-name>/SKILL.md`；限制每 file 16KiB/正文 12KiB；无 symlink/path escape、严格 UTF-8+safe_yaml+元字段白名单、name/description/allowed_tools 格式与长度、重复、恶意 YAML 锚点/别名。发现固定 metadata + digest，按 name 重新确认 inode/digest；Skill 的 required tools 必须属于 Registry 且满足当前 Run 允许名称，否则不可 list/read。
- `tools/skill_tools.py`：ToolRuntime 隐藏可信 ctx，`list_skills()`、`read_skill(name)` 仅返回当前 Run 可访问的本地 Skill 描述/正文；**不会把文本写入 System Prompt、不会改 allowed_tools**。路径只由 loader 管理，模型不接触路径。
- `backend/skills/public/file-analysis/SKILL.md`：合法 YAML，具体步骤：用 `list_files` 找到当前 Thread 上传的文件 ID、`read_text` 获取原始证据、说明缺失信息、用户要求时由 Lead `write_text` 输出。声明 required tools 是 list_files/read_text，不强制写权限。
- `backend/tests/test_skills.py`：合法/未知 YAML key/大文件/非法编码/重名/符号链接/跨目录/路径相似/unknown required tool/未授权 required tool、Skill 不能提权、List 不包含正文、Read 只返回当前 Skill，真实 Agent Tool schema 无路径/身份。
**修改**：
- `pyproject.toml`/`uv.lock` 追加 `PyYAML`；
- `main.py` 创建 SkillCatalog 并注册 list/read 两工具，`AgentRunContext` 注入 SkillService；`agents/lead.py` 对 P05 Run 追加简短方法提示，而不是塞所有 Skill 正文；
- `api/capabilities.py` 的 `GET /api/skills` 和 CapabilityPanel 真实展示 Skill 名称/摘要/需要的工具；P01 独立、P04 Child 仍**不注册 Skill 工具**。

**C 局部验收**：当前 Run 调 `list_skills` 和 `read_skill("file-analysis")`，模型仅得到一个本地 Skill 内容，使用现有文件工具读证据。无 MCP 时 Skill 仍可用；写着不存在工具的 Skill 不能被激活；写着删除/执行 shell 的 Skill 没有新执行权限。测试范围新 Skills 及直接影响 Runner/ToolGuard，Ruff/TS Build。提交 `feat(p05-c): load approved local skills on demand`。

## P05-D：完整 Agent/页面/失败与交付

1. Fake + 临时数据真实 Graph：创建 Thread、上传 `notes.md`、`list_skills→read_skill(file-analysis)→list_files→read_text→write_text(summary.md)`，下载 bytes/sha 正确；另一复杂 Run 通过 `mcp_demo_lookup_fact` 获取实际固定事实，P04 Todo/子代理可继续调用且 Child 没有 MCP/Skills；P01 只保留 calculate。
2. 真实浏览器：CapabilityPanel 显示 builtin + 配置且在线的 MCP + Skill；同 Thread ChatPanel 工具轨迹记录实际工具，Artifact 下载；刷新/重启历史仍存在。MCP 下线时不破坏旧 Runtime，也不将离线工具误报可用。
3. 故障场景：未配置/MCP Server 断线/pin 或描述变化/请求超时/无效参数/重复 Tool/目录符号链接/恶意 YAML/模型提示“我有权限”/Skill 要求写权限/子代理越权，保证模型不能绕开 Policy、SSE 工具结果不假成功；保留 P04 TaskRegistry 3并发4次、P02 Run 150秒、P03 Workspace 的全部安全边界。
4. 本地有真实 Tool Calling 模型时另用合成文本单独实测并记录模型是否真正调用 MCP 与 Skill；只用安全内容、不把服务端工具列表长文本当成提示词注入权限。不要求模型一定选择某工具；不可靠则以 Fake 实际调用证明装配，再报告真模型局限。
5. 每段局部测试**只执行 P05 的新改文件及直接受影响 P01–P04**，真实命令准确写进 progress；`uv lock --check`、`uv run ruff check src tests`/format、前端 `npm ci && npm run build`；SDK真实兼容、安全审核，Git 忽略没有泄露配置用户凭据。P05-D 单独 commit，进度最终 `PENDING_REVIEW`，等待用户手动验收，**不开始 P06**。

## 最后给用户的汇报模板

简洁报告 A/B/C/D 各提交 SHA、实际推送情况、每段测什么和数量、前端现在能单独测什么、MCP Demo 服务真实启动方式、ToolRegistry 保留 P04 Command/ToolRuntime/角色隔离的证据、Skill 只读和工具不提权的测试、Fake/真模型分别结果、未验证/风险、手动 Demo 步骤；绝不把设计当代码、把错误当成功。安全失败则停止本阶段并记录阻塞。
