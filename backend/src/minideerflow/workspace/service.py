"""协调安全磁盘与元数据事务，失败只清理本次新建对象。"""

import logging

from minideerflow.workspace.models import (
    ArtifactRecord,
    FileRecord,
    WorkspaceError,
    validate_filename,
)
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

    async def _read_registered(self, record: FileRecord) -> bytes:
        """读取在线程中完成；取消时先回收读取，避免关闭仍在使用的目录fd。"""
        import asyncio

        task = asyncio.create_task(asyncio.to_thread(self.storage.read_registered, record))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception:  # noqa: BLE001 - 取消仍优先传播，不输出底层错误
                logger.error("Workspace read cancelled during cleanup")
            raise

    async def read_text(self, thread_id: str, file_id: str) -> str:
        """先查归属与文本额度，再安全读取完整文本；绝不静默截断。"""
        from minideerflow.workspace.models import READ_LIMIT

        record = await self.repository.get_file_for_thread(thread_id, file_id)
        if record.mime == "application/pdf":
            raise WorkspaceError(
                "UNSUPPORTED_FILE_TYPE", "PDF is stored only; text extraction is unavailable", 422
            )
        if record.size_bytes > READ_LIMIT:
            raise WorkspaceError("TOOL_READ_LIMIT", "Tool read exceeds 64KiB", 413)
        data = await self._read_registered(record)
        try:
            return data.decode("utf-8", errors="strict")
        except UnicodeError:
            raise WorkspaceError("INVALID_FILE_CONTENT", "Text must use valid UTF-8", 422) from None

    async def write_text(self, thread_id: str, run_id: str, filename: str, content: str):
        """只有可信活动Run可以新建产物，双表登记失败清理新UUID，不覆盖旧产物。"""
        await self.repository.check_run(thread_id, run_id)
        name, mime = validate_filename(filename)
        if mime == "application/pdf":
            raise WorkspaceError(
                "UNSUPPORTED_FILE_TYPE", "write_text supports text formats only", 422
            )
        stored = await self.storage.save_text(thread_id, run_id, name, content, mime)
        try:
            self.storage.verify_new(stored)
            return await self.repository.register_artifact(stored.record)
        except BaseException as exc:
            self.storage.discard_new(stored)
            if isinstance(exc, WorkspaceError) or not isinstance(exc, Exception):
                raise
            logger.error("Workspace artifact registration failed")
            raise WorkspaceError(
                "WORKSPACE_UNAVAILABLE", "Artifact registration failed", 503
            ) from None
        finally:
            stored.close()

    async def list_artifacts(self, thread_id: str) -> list[ArtifactRecord]:
        return await self.repository.list_artifacts(thread_id)

    async def download_artifact(
        self, thread_id: str, artifact_id: str
    ) -> tuple[bytes, ArtifactRecord]:
        """先核对所有关联，再读取已验证字节，不让Response重新按路径打开文件。"""
        artifact = await self.repository.get_artifact(thread_id, artifact_id)
        record = await self.repository.get_file_for_thread(thread_id, artifact.file_id)
        return await self._read_registered(record), artifact
