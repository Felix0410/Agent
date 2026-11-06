"""协调安全磁盘与元数据事务，失败只清理本次新建对象。"""

import logging

from minideerflow.workspace.models import FileRecord, WorkspaceError, validate_filename
from minideerflow.workspace.repository import WorkspaceRepository
from minideerflow.workspace.storage import WorkspaceStorage

logger = logging.getLogger("minideerflow")


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository, storage: WorkspaceStorage) -> None:
        self.repository, self.storage = repository, storage

    async def upload(self, thread_id: str, upload) -> FileRecord:
        """先验证归属与内容，安全发布后才登记；SQLite 失败不留下可访问的假记录。"""
        # 1. 先确认 Thread，显示名只入元数据，不进入任何磁盘寻址。
        await self.repository.check_thread(thread_id)
        name, mime = validate_filename(upload.filename or "")
        stored = await self.storage.save_upload_stream(thread_id, upload, name, mime)
        try:
            # 2. 固定目录 fd 跨越登记边界，异常/取消清理不重新解析路径。
            self.storage.verify_new(stored)
            return await self.repository.register_upload(stored.record)
        except BaseException as exc:
            self.storage.discard_new(stored)
            if isinstance(exc, WorkspaceError) or not isinstance(exc, Exception):
                raise
            logger.error("Workspace metadata registration failed")
            raise WorkspaceError("WORKSPACE_UNAVAILABLE", "File registration failed", 503) from None
        finally:
            stored.close()

    async def list_files(self, thread_id: str) -> list[FileRecord]:
        return await self.repository.list_files(thread_id)
