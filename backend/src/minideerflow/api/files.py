"""文件 HTTP 边界：只使用 WorkspaceService，不拼接宿主机路径。"""

from fastapi import APIRouter, HTTPException, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from minideerflow.workspace.models import FileRecord, WorkspaceError

router = APIRouter()


def workspace_http_error(exc: WorkspaceError) -> HTTPException:
    return HTTPException(exc.status, detail={"code": exc.code, "message": exc.safe_message})


@router.post("/api/threads/{thread_id}/files", status_code=201, response_model=FileRecord)
async def upload_file(thread_id: str, request: Request) -> FileRecord:
    """只接受一个 file 字段；限制 multipart 数量，并始终关闭临时上传句柄。"""
    try:
        # UploadFile 内容由服务逐64KiB读取；multipart本身允许受控磁盘spool。
        async with request.form(max_files=1, max_fields=0) as form:
            items = form.multi_items()
            if (
                len(items) != 1
                or items[0][0] != "file"
                or not isinstance(items[0][1], StarletteUploadFile)
            ):
                raise HTTPException(
                    422, detail={"code": "INVALID_FILE_CONTENT", "message": "Upload one file"}
                )
            upload: UploadFile = items[0][1]
            return await request.app.state.workspace.upload(thread_id, upload)
    except WorkspaceError as exc:
        raise workspace_http_error(exc) from None
    except StarletteHTTPException as exc:
        if exc.status_code == 400:
            raise workspace_http_error(
                WorkspaceError("INVALID_FILE_CONTENT", "Upload exactly one valid file", 422)
            ) from None
        raise


@router.get("/api/threads/{thread_id}/files", response_model=list[FileRecord])
async def list_files(thread_id: str, request: Request) -> list[FileRecord]:
    try:
        return await request.app.state.workspace.list_files(thread_id)
    except WorkspaceError as exc:
        raise workspace_http_error(exc) from None
