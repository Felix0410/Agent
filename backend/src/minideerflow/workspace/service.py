"""协调安全磁盘与元数据事务，失败只清理本次新建对象。"""

import asyncio
import logging
from typing import cast

from minideerflow.workspace.models import (
    ArtifactRecord,
    FileKind,
    FileRecord,
    WorkspaceError,
    validate_filename,
)
from minideerflow.workspace.repository import WorkspaceRepository
from minideerflow.workspace.storage import StoredFile, WorkspaceStorage

logger = logging.getLogger("minideerflow")


class WorkspaceService:
    """工作空间服务类，协调安全磁盘与元数据事务。"""

    def __init__(self, repository: WorkspaceRepository, storage: WorkspaceStorage) -> None:
        """初始化工作空间服务类，指定仓库和存储。"""
        self.repository, self.storage = repository, storage

    async def upload(self, thread_id: str, upload) -> FileRecord:
        """上传文件"""
        # 1. 确认 Thread 存在
        await self.repository.check_thread(thread_id)
        # 2. 验证文件名
        name, mime = validate_filename(upload.filename or "")
        # 3. 保存文件流
        stored = await self.storage.save_upload_stream(thread_id, upload, name, mime)
        # 4. 登记文件
        return cast(FileRecord, await self._register_new(stored))

    async def _register_new(self, stored: StoredFile) -> FileRecord | ArtifactRecord:
        """登记新文件"""
        try:
            # 1. 验证新文件位置
            self.storage.verify_new(stored)
            # 2. 登记文件元数据
            operation = (
                self.repository.register_upload(stored.record)
                if stored.record.kind == FileKind.UPLOAD
                else self.repository.register_artifact(stored.record)
            )
            # 3. 等待登记完成
            registration = asyncio.create_task(operation)
            try:
                # 4. 登记完成，返回登记结果
                return await asyncio.shield(registration)
            # 5. 登记取消
            except asyncio.CancelledError:
                if not registration.done():
                    await asyncio.gather(registration, return_exceptions=True)
                raise
        except BaseException as exc:
            # 6. 登记失败，清理登记任务
            await self._cleanup_failed_registration(stored)
            if isinstance(exc, WorkspaceError) or not isinstance(exc, Exception):
                raise
            logger.error("Workspace metadata registration failed")
            raise WorkspaceError("WORKSPACE_UNAVAILABLE", "File registration failed", 503) from None
        finally:
            stored.close()

    async def _cleanup_failed_registration(self, stored: StoredFile) -> None:
        """清理登记失败的文件"""
        try:
            # 1. 获取已登记文件元数据
            registered = await self.repository.get_file(stored.record.id)
        except WorkspaceError as exc:
            if exc.code == "FILE_NOT_FOUND":
                self.storage.discard_new(stored)
                return
            logger.error("Workspace registration state unavailable during cleanup")
            return
        except Exception:  # noqa: BLE001 - 边界统一脱敏，保持取消和既有失败语义
            logger.error("Workspace registration state unavailable during cleanup")
            return
        # 2. 检查文件位置是否一致
        if registered.storage_key != stored.record.storage_key:
            # 3. 文件位置不一致，删除新文件
            self.storage.discard_new(stored)
        # 4. 检查文件类型是否一致
        elif registered.kind == FileKind.UPLOAD:
            try:
                # 5. 文件类型一致，删除已登记文件以及新文件流
                await self.repository.discard_upload(registered)
                self.storage.discard_new(stored)
            except Exception:  # noqa: BLE001 - 边界统一脱敏，保持取消和既有失败语义
                logger.error("Workspace upload compensation failed")

    async def list_files(self, thread_id: str) -> list[FileRecord]:
        """列出指定Thread下的所有文件。"""
        return await self.repository.list_files(thread_id)

    async def _read_registered(self, record: FileRecord) -> bytes:
        """读取已登记文件的内容。"""
        # 1. 确认文件存在
        task = asyncio.create_task(asyncio.to_thread(self.storage.read_registered, record))
        try:
            # 2. 读取文件内容
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception:  # noqa: BLE001 - 边界统一脱敏，保持取消和既有失败语义
                logger.error("Workspace read cancelled during cleanup")
            raise

    async def read_text(self, thread_id: str, file_id: str) -> str:
        """读取指定Thread下的指定文件的文本内容。"""
        from minideerflow.workspace.models import READ_LIMIT

        # 1. 获取文件元数据
        record = await self.repository.get_file_for_thread(thread_id, file_id)
        # 2. 检查文件类型
        if record.mime == "application/pdf":
            raise WorkspaceError(
                "UNSUPPORTED_FILE_TYPE", "PDF is stored only; text extraction is unavailable", 422
            )
        # 3. 检查文件大小
        if record.size_bytes > READ_LIMIT:
            raise WorkspaceError("TOOL_READ_LIMIT", "Tool read exceeds 64KiB", 413)
        # 4. 读取文件内容
        data = await self._read_registered(record)
        try:
            # 5. 解码文件内容
            return data.decode("utf-8", errors="strict")
        except UnicodeError:
            raise WorkspaceError("INVALID_FILE_CONTENT", "Text must use valid UTF-8", 422) from None

    async def write_text(self, thread_id: str, run_id: str, filename: str, content: str):
        """写指定Thread下的指定文件的文本内容。"""
        await self.repository.check_run(thread_id, run_id)
        name, mime = validate_filename(filename)
        if mime == "application/pdf":
            raise WorkspaceError(
                "UNSUPPORTED_FILE_TYPE", "write_text supports text formats only", 422
            )
        stored = await self.storage.save_text(thread_id, run_id, name, content, mime)
        return cast(ArtifactRecord, await self._register_new(stored))

    async def list_artifacts(self, thread_id: str) -> list[ArtifactRecord]:
        """列出指定Thread下的所有产物。"""
        return await self.repository.list_artifacts(thread_id)

    async def download_artifact(
        self, thread_id: str, artifact_id: str
    ) -> tuple[bytes, ArtifactRecord]:
        """下载指定Thread下的指定产物的文件内容。"""
        artifact = await self.repository.get_artifact(thread_id, artifact_id)
        record = await self.repository.get_file_for_thread(thread_id, artifact.file_id)
        return await self._read_registered(record), artifact
