# P03-A/B/C · Workspace + File Tools + Artifact 连续执行合同

> 状态：**READY_FOR_CODE，尚未编码**  
> 用户 2026-11-06 指令“启动 P3”。先执行本文指定的完整 P03-A→B→C 顺序；每段分别同步前端、跑局部测试并提交 SHA；除非关键失败/需更改合同，无需反复让本地 AI 设计架构。P02 远端最新代码为继承基线，P02 的用户手动 Demo 状态保留 `PENDING_REVIEW`，不伪造 ACCEPTED。  
> **唯一规格**：[docs/DEVELOPMENT.md · P03](../DEVELOPMENT.md) + [AGENTS.md](../../AGENTS.md)；本文件负责把实际执行文件、步骤和局部测试细化，若两文冲突以 P03 正式合同为准，必须报告而不是自行重构。

## 0. 强制前置核验

1. 仓库根目录 `git status --short --branch`、`git log -8 --oneline`、`git branch -vv`，核对远端分支 `feat/p03-workspace-artifacts` 基于 `feat/p02-runtime-web`。有未提交文件先保护并报告，不 reset/clean/force push。不得从 `main`（缺 P02）重建代码。
2. 核对实际 `backend/src/minideerflow/{main.py,config.py,runtime/db.py,runtime/repository.py,runtime/runner.py,runtime/streaming.py,agents/lead.py,agents/service.py}`，`frontend/src/{App.tsx,api/runtime.ts,components/ChatPanel.tsx}`，P02 tests。**现有代码已经有 FastAPI、RuntimeDatabase、RunService、AsyncSqliteSaver、ThreadList、ChatPanel，不允许另写一套服务/数据库/Agent**。
3. 用已安装锁版依赖检验 `create_agent(context_schema=...)`、`ToolRuntime[WorkspaceContext]` 参数能隐藏模型可见 schema，`CompiledStateGraph.astream(...,context=...)` 真正可把 Context 注入文件工具；允许最小局部样例。任何不支持则停止并写可复现信息，不改成进程级全局 CURRENT_THREAD_ID。
4. 保留现有 `backend/.venv`、根目录 `.env`、默认 `backend/data/`、用户本地文件。不可上传已有用户文件到测试系统，不打印/提交 key；后端仅本机回环。

## 1. P03-A：安全存储、元数据、上传与文件列表

**需要执行的文件**（仅当前 A）：

| 文件 | 具体编码 |
|---|---|
| `backend/pyproject.toml` / `backend/uv.lock` | `uv add python-multipart` 且锁定版本可 `uv sync --locked --group dev`；不要升级无关依赖 |
| `backend/src/minideerflow/config.py` / `.env.example` | `workspace_root_path` 默认 `backend/data/workspaces`；从 backend 解析相对路径，不依赖 cwd；大小限制优先模块常量，不大量增加 Settings |
| `backend/src/minideerflow/runtime/db.py` | 在现有 `SCHEMA` 后追加 `files`、`artifacts`、索引与约束；不重建/破坏已有表；P02 DB 测试依旧能过 |
| `backend/src/minideerflow/workspace/models.py` | `FileRecord`、`ArtifactRecord`、`FileKind`、`WorkspaceError(code,safe_message,status)`、`WorkspaceContext`、严格显示名校验及四文本+PDF 白名单 |
| `backend/src/minideerflow/workspace/storage.py` | `WorkspaceStorage` 创建 Thread 目录、secure dir_fd 与 O_NOFOLLOW、上传分块写临时文件→校验 sha/大小→原子无覆盖发布→清理；下载读取安全 fd、对元数据 size/sha 复核；**磁盘名只能是后端 UUID** |
| `backend/src/minideerflow/workspace/repository.py` | `WorkspaceRepository` 复用现有 `RuntimeDatabase.transaction()`：Thread 存在、50 files/30MiB 额度、上传登记、按 Thread ID 列表和按 file_id 读取元数据 |
| `backend/src/minideerflow/workspace/service.py` | `WorkspaceService.upload(thread_id,UploadFile)`：先查 Thread→规范显示名/类型→分块安全存→事务登记→失败清理；`list_files(thread_id)` |
| `backend/src/minideerflow/api/files.py` | `POST /api/threads/{thread_id}/files`（201，表单键 file），`GET /api/threads/{thread_id}/files`（200）；按 WorkspaceError 映射脱敏 HTTP code |
| `backend/src/minideerflow/main.py` | 把 WorkspaceStorage/Repository/Service 注入 `app.state.workspace`，注册 Files Router；生命周期原有 Runner→EventBus→Saver→DB 关闭顺序不变 |
| `frontend/src/api/files.ts` | `uploadFile(threadId,file)` 用 FormData 不设置 Content-Type；`listFiles(threadId)`；严格使用后端 DTO |
| `frontend/src/components/FilesPanel.tsx` | 当前会话选文件、上传、文件列表、大小/类型/错误说明、重新加载；PDF 显示“仅存储，暂不解析”；暂不显示不存在的产物 |
| `frontend/src/components/ChatPanel.tsx` / `App.tsx` / `styles.css` | 在当前 Thread 工作台组合可用 FilesPanel，切换 Thread 后清理上传状态/重新加载，不移除 P02 聊天、SSE 和 P01 调试能力 |
| `backend/tests/test_workspace.py` / `test_files_api.py` | 使用 tmp_path + Temp SQLite + Fake/无模型测试上传/list；再覆盖符号链接、文件名、超长/非法 UTF8/PDF、绝对/相对路径穿越、大小/配额、取消/失败清理 |

**不可放宽的实现细节**：

- 每个 Thread 映射 `root/{validated UUID}/`；用户 `filename` 仅显示字段不进入磁盘 `os.open`；硬编码或正则“允许字符”不是唯一防护。文件在 `dir_fd` 下按 UUID 存储；安全验证使用 `O_DIRECTORY|O_NOFOLLOW`、`O_EXCL`、`fstat` 等，并结合 `os.link`（目标已存在时失败）或等效 no-clobber 原子发布。
- 单次只允许一个 `UploadFile`，流式 `read(65536)`，不 `read()` 全部。文本仅严格 UTF-8、<=2MiB，PDF 仅存储/校验 PDF 开头、<=10MiB；Thread 50 项总 30MiB。拒绝 NUL、斜杠、反斜杠、`..`、控制字符等文件名；UTF-8 非法内容明确定义错误。
- 即使本地上传者尝试通过现有 symlink 或替换 workspace 目录竞争也不得逃出根目录；测试需包括恶意 thread 目录 symlink、文件 symlink、UUID 目录替换的可模拟场景。无法安全实现则 BLOCKED，禁止用裸 `Path.write_bytes` 糊弄。
- 上传只在成功登记后 API 返回真实 `file_id`、`sha256`、`size_bytes`；注册失败清理本次新文件；API 不暴露真实存储路径。
- A 的前端只展示**真实已上传文件**，内部纯逻辑无 UI 时说明原因，不能放假 Artifact 下载入口。

**A 验证及提交**：`uv sync --locked --group dev`，`uv run pytest -q tests/test_workspace.py tests/test_files_api.py tests/test_config.py tests/test_health.py`（根据实际受影响增减），`uv run ruff check src tests`，`uv run ruff format --check src tests`；`cd frontend && npm ci && npm run build`；真实临时后端 HTTP 与浏览器上传/刷新，不消费模型。通过后提交 `feat(p03-a): add secure uploads and thread file list`，在 `docs/progress/P03.md` 记 A 真实 SHA / 前端 / 测试后自动进入 B。

## 2. P03-B：文件 ToolRuntime、Artifact 与 Web 下载

**必须执行文件**：

1. `workspace/repository.py` 补 `register_artifact`、`list_artifacts`、`get_artifact`、`get_file_for_thread`：在 SQLite 事务里核对 file/Run/Thread 归属，`ArtifactRecord` 只引用真实 `FileRecord(kind=ARTIFACT)`；同 Thread Artifact display_name 唯一，不覆盖。可能的 SQLite 唯一冲突映射为 `ARTIFACT_NAME_CONFLICT`，不能把 SQL 原文返回给模型。
2. `workspace/service.py` 实现 `read_text(thread_id,file_id)`（64KiB 完整上限，禁止 PDF）、`write_text(thread_id,run_id,filename,content)`（UTF-8 最多128KiB，真实生成 Artifact）、`list_artifacts(thread_id)`、`download_artifact(thread_id,artifact_id)`（safe fd 读取登记内容，返回 bytes+安全 metadata）。所有文件 ID 操作必须先检验归属后才触碰存储。
3. `api/files.py` 补 `GET /api/threads/{thread_id}/artifacts` 与 `GET /api/artifacts/{artifact_id}?thread_id=<id>`；检查 PDF/文本 MIME、严格下载 `Content-Disposition` 和无 symlink fd 读取，不能用不安全 `FileResponse` 二次打开真实路径。没有身份认证只能强调本地单用户，不宣称远程多租户权限。
4. `tools/file_tools.py` 使用 `@tool` 定义 `list_files(runtime)`、`read_text(file_id,runtime)`、`write_text(filename,content,runtime)`；`runtime: ToolRuntime[WorkspaceContext]` 自动注入，模型可见 Schema **不出现** runtime/thread_id/run_id/path/root；内部使用 Context 中的 WorkspaceService 校验身份。提供易理解、准确的英文 Tool 描述以保证模型 Tool Calling，不将中文注释强行变成模型描述。预期失败返回 `ERROR[CODE]: safe message`，与 P02 `ToolTrace.ok=false` 一致。
5. `agents/lead.py` 在现有工厂上增加可选 `context_schema`；`runtime/streaming.py` 增加可选 `context` 并显式传入 `agent.astream`；`runtime/runner.py` 注入可选 WorkspaceService，当前持久 Run 才使用三个文件工具并构造 `WorkspaceContext(thread_id,run_id,workspace_service)`。旧 `run_agent_once` / `/api/demo/agent` / CLI 保持只有 calculate，不能绕过 Run。对旧 P02 假模型测试保留没有 workspace 的注入途径。
6. `frontend/src/api/files.ts` 增加 `listArtifacts`、`downloadArtifact`；`FilesPanel.tsx` 展示 Artifacts、点击下载和失败提示。P02 `RunStatus` 不应把模型文字中的“生成文件”当作已完成，**Run 结束后重新拉取真实文件列表**，有需要仅展示已登记 artifact_id 的链接。文件面板与会话线程切换完全隔离。

**B 必测**：不读用户真实 `.env` 的 FakeChatModel 真正通过 ToolRuntime 调用三项工具；在 Tool Call schema 中不出现 runtime/thread/run/hostPath；上传 `notes.md` 后同 Thread list/read 得到真实正文，再 write 出 `summary.md`，ToolMessage 关联 ID 正确，Run 终态与 Artifact 存在；浏览器下载 bytes 与写入一致、SHA 相同。跨 Thread file_id、未知 file_id、伪造 Thread ID、PDF read、超大 read、越界写、同名产物、非法文件名、文件被替换成 symlink 都应失败并且不泄露路径；工具失败不能默认为 ok=true。保留 P01 calculate 与 P02 单 Thread 并发行为。

**B 测试命令**：`uv run pytest -q tests/test_file_tools.py tests/test_workspace.py tests/test_files_api.py tests/test_runner.py tests/test_lead.py tests/test_runs_api.py`（实际受影响范围为准），Ruff，`npm run build`，Fake HTTP + Web；记录 SHA 并提交 `feat(p03-b): add scoped file tools and downloadable artifacts`，通过后自动进入 C。

## 3. P03-C：端到端收尾、异常、重启与最终 Demo

1. 真实临时两库 + Workspace 实测：上传（多种文本 + PDF）→ Agent 真 Tool Calling 读取上传内容 → 实际 `write_text("summary.md",...)` → 通过 Thread artifacts 列表和 GET artifact 下载 → 后端正常关闭再启动 → 文件/Artifact/Run 历史不丢且当前 Thread 仍能访问。另一个 Thread 无法传自己的 context 读取它们。
2. 故障注入：目录/文件 symlink、非文本、超限、恶意文件名、无覆盖并发竞争、下载文件字节变更、SQLite 注册失败、Run 内工具失败/中断、绝对路径字符串、重启后无登记 orphan；旧合法文件不损坏。P02 模型/Tool/SSE 轨迹不应把错误写作成功，Run 状态只按真实 Agent 终态决定。
3. 真实前端：新建/选择 Thread → 上传 `notes.md` → 发送“读取我上传的 notes.md，生成 summary.md 并让我下载” → 看到实际工具轨迹、真实产物链接并下载文件 → 刷新仍可查询；没有模型配置则上传/文件列表可独立验证，并记录 `REAL_MODEL_FILE_SMOKE_BLOCKED`。**如果本地已配支持 Tool Calling 的模型**，在不打印密钥/原始文档的前提下使用专门的临时文本样例实测，Mock 与真实结果分别写明。
4. 复核关闭/异常的清理顺序：RunService 最先 shutdown，之后 Workspace/Events/Saver/DB；文件元数据只从 Repository 读出，不能通过磁盘扫描直接当登记结果。单 Worker 规则和本机监听不变。
5. `README.md` 增 P03 文件与工具操作、大小与格式限制、命令及已知边界；更新 `docs/progress/P03.md` 三阶段 SHA/实际测试/前端能力/未验证事项。核心 Python、TS 函数中文注释，长流程 `# 1/# 2/# 3` 或 `//` 分段，不能仅用注释掩盖不清晰代码。若真正运行了某命令才记录通过。
6. 最终局部 pytest（P03 新模块及**直接受影响**的 P02/P01）、Ruff check/format、`npm ci && npm run build`、真实 HTTP/Fake 页面 Smoke。三段提交，最终状态 `PENDING_REVIEW`；等待用户 Demo 手验。**禁止自动进入 P04、禁止把 P02 进度改为虚假的 ACCEPTED**。

## 4. 最终向用户的一次性报告

只需汇报一次：A/B/C 三个 SHA 和推送结果；每段文件职责与前端真实能力；测试命令与准确通过数；安全路径/归属/上传/Artifact 下载/Checkpoint+SSE 的验证；Mock 与真模型 Smoke 边界；用户 Demo 启动和操作方法；尚未实测/阻塞项。推送失败如实汇报，不强推、不修改用户凭据。若有阻塞，立即停在最近的可验证提交，报告重现方式及已提交 SHA，不做伪成功。
