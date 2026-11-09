"""仅持久Run注册的文件工具，身份经ToolRuntime注入而非模型参数。"""

import json

from langchain.tools import ToolRuntime, tool

from minideerflow.workspace.models import WorkspaceContext, WorkspaceError
from minideerflow.workspace.service import WorkspaceService


async def _context(runtime: ToolRuntime[WorkspaceContext]) -> WorkspaceContext:
    """获取并验证工作空间上下文"""
    context = runtime.context
    # 验证上下文类型
    if not isinstance(context, WorkspaceContext) or not isinstance(
        context.workspace_service, WorkspaceService
    ):
        raise WorkspaceError("WORKSPACE_UNAVAILABLE", "Trusted workspace context is required", 503)
    # 验证Run与Thread归属
    await context.workspace_service.repository.check_run(context.thread_id, context.run_id)
    return context


def _error(exc: WorkspaceError) -> str:
    """格式化工作空间错误信息"""
    return f"ERROR[{exc.code}]: {exc.safe_message}"


@tool
async def list_files(runtime: ToolRuntime[WorkspaceContext]) -> str:
    """List registered files in the current conversation. Use file_id to read text. PDF is stored only."""
    try:
        context = await _context(runtime)
        files = await context.workspace_service.list_files(context.thread_id)
        return json.dumps(
            [
                {
                    "file_id": f.id,
                    "name": f.display_name,
                    "kind": f.kind.value,
                    "size": f.size_bytes,
                    "mime": f.mime,
                }
                for f in files
            ],
            ensure_ascii=False,
        )
    except WorkspaceError as exc:
        return _error(exc)
    except Exception:
        return "ERROR[WORKSPACE_UNAVAILABLE]: File operation failed"


@tool
async def read_text(file_id: str, runtime: ToolRuntime[WorkspaceContext]) -> str:
    """Read a registered UTF-8 text file by file_id in the current conversation. Maximum 64KiB; PDF is unsupported."""
    try:
        context = await _context(runtime)
        return await context.workspace_service.read_text(context.thread_id, file_id)
    except WorkspaceError as exc:
        return _error(exc)
    except Exception:
        return "ERROR[WORKSPACE_UNAVAILABLE]: File operation failed"


@tool
async def write_text(filename: str, content: str, runtime: ToolRuntime[WorkspaceContext]) -> str:
    """Create a new downloadable UTF-8 artifact. Use a safe txt/md/csv/json filename, maximum 128KiB. Existing artifact names cannot be overwritten."""
    try:
        context = await _context(runtime)
        artifact = await context.workspace_service.write_text(
            context.thread_id, context.run_id, filename, content
        )
        return json.dumps(
            {
                "artifact_id": artifact.artifact_id,
                "file_id": artifact.file_id,
                "filename": artifact.display_name,
                "size": artifact.size_bytes,
            },
            ensure_ascii=False,
        )
    except WorkspaceError as exc:
        return _error(exc)
    except Exception:  
        return "ERROR[WORKSPACE_UNAVAILABLE]: File operation failed"


# 禁用额外参数
for scoped_tool in (list_files, read_text, write_text):
    scoped_tool.args_schema.model_config["extra"] = "forbid"
    scoped_tool.args_schema.model_rebuild(force=True)
