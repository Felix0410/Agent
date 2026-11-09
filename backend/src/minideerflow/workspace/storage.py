"""POSIX fd 安全存储：名字不参与磁盘寻址，发布从不覆盖已有对象。"""

import codecs
import hashlib
import os
import stat
import unicodedata
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from minideerflow.runtime.models import utc_now_iso
from minideerflow.workspace.models import (
    CHUNK_SIZE,
    PDF_UPLOAD_LIMIT,
    TEXT_UPLOAD_LIMIT,
    FileKind,
    FileRecord,
    WorkspaceError,
    validate_uuid,
)


@dataclass
class StoredFile:
    """存储的文件记录，包含文件记录和目录 fd。"""

    record: FileRecord
    directory_fd: int

    def close(self) -> None:
        """关闭目录 fd，释放资源。"""
        if self.directory_fd >= 0:
            os.close(self.directory_fd)
            self.directory_fd = -1


class WorkspaceStorage:
    """工作空间存储类，负责安全存储文件。"""

    def __init__(self, root: Path) -> None:
        """初始化工作空间存储类，指定根目录。"""
        if not root.is_absolute() or ".." in root.parts:
            raise WorkspaceError("INVALID_FILE_PATH", "Workspace root must be absolute", 422)
        self.root = root
        self._root_fd = -1

    def open(self) -> None:
        """打开工作空间存储，确保根目录存在且安全。"""
        required = (os.open, os.mkdir, os.stat, os.link, os.unlink)
        if (
            os.name != "posix"
            or not all(
                hasattr(os, flag)
                for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "O_CLOEXEC")
            )
            or os.link not in os.supports_follow_symlinks
            or any(function not in os.supports_dir_fd for function in required)
        ):
            raise WorkspaceError(
                "WORKSPACE_UNAVAILABLE", "Secure local storage is unavailable", 503
            )
        fd = os.open("/", self._directory_flags())
        try:
            # 1. 不用 Path.resolve 消掉恶意 symlink；每一级都经 dir_fd + O_NOFOLLOW。
            for part in self.root.parts[1:]:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, self._directory_flags(), dir_fd=fd)
                os.close(fd)
                fd = child
            self._trusted_directory(fd)
            self._root_fd, fd = fd, -1
        except OSError:
            raise WorkspaceError(
                "WORKSPACE_UNAVAILABLE", "Workspace directory is unsafe", 503
            ) from None
        finally:
            if fd >= 0:
                os.close(fd)

    @staticmethod
    def _directory_flags() -> int:
        """目录打开标志"""
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

    @staticmethod
    def _trusted_directory(fd: int) -> None:
        """验证目录 fd 是否安全"""
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise WorkspaceError("INVALID_FILE_PATH", "Unsafe workspace directory", 422)

    def close(self) -> None:
        """关闭工作空间存储，释放所有资源。"""
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def _assert_location(self, thread_id: str, fd: int) -> None:
        """验证文件流位置"""
        root = os.stat(self.root, follow_symlinks=False)
        opened = os.fstat(self._root_fd)
        named = os.stat(thread_id, dir_fd=self._root_fd, follow_symlinks=False)
        current = os.fstat(fd)
        if (
            not stat.S_ISDIR(root.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or (root.st_dev, root.st_ino) != (opened.st_dev, opened.st_ino)
            or (named.st_dev, named.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise WorkspaceError("INVALID_FILE_PATH", "Workspace directory changed", 422)
        self._trusted_directory(fd)

    def _thread_directory(self, thread_id: str, *, create: bool) -> int:
        """打开或创建 Thread 目录"""
        validate_uuid(thread_id)
        if create:
            try:
                os.mkdir(thread_id, mode=0o700, dir_fd=self._root_fd)
            except FileExistsError:
                pass
        fd = os.open(thread_id, self._directory_flags(), dir_fd=self._root_fd)
        try:
            self._assert_location(thread_id, fd)
            return fd
        except BaseException:
            os.close(fd)
            raise

    async def save_upload_stream(self, thread_id: str, upload, name: str, mime: str) -> StoredFile:
        """保存上传流"""

        # 1. 分块读取上传流
        async def chunks() -> AsyncIterator[bytes]:
            while chunk := await upload.read(CHUNK_SIZE):
                yield chunk

        # 2. 验证文件大小
        limit = PDF_UPLOAD_LIMIT if mime == "application/pdf" else TEXT_UPLOAD_LIMIT
        # 3. 保存文件流
        return await self._save(thread_id, name, mime, chunks(), limit)

    async def _save(
        self,
        thread_id: str,
        name: str,
        mime: str,
        chunks: AsyncIterator[bytes],
        limit: int,
        *,
        kind: FileKind = FileKind.UPLOAD,
        run_id: str | None = None,
    ) -> StoredFile:
        """保存文件流"""
        # 1. 初始化变量，设置临时文件名防止误读取失败文件
        directory = -1
        file_fd = -1
        temporary = ".tmp-" + uuid4().hex
        key = uuid4().hex
        temporary_created = published = success = False
        try:
            # 2. 打开或创建 Thread 目录
            directory = self._thread_directory(thread_id, create=True)
            file_fd = os.open(
                temporary,
                os.O_WRONLY | os.O_NOFOLLOW | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                mode=0o600,
                dir_fd=directory,
            )
            temporary_created = True
            digest, size, header = hashlib.sha256(), 0, b""
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            async for chunk in chunks:
                # 3. 验证文件大小
                size += len(chunk)
                if size > limit:
                    raise WorkspaceError("FILE_TOO_LARGE", "File exceeds the permitted size", 413)
                # 4. 验证文本文件内容
                if mime != "application/pdf":
                    decoded = decoder.decode(chunk, final=False)
                    if any(
                        unicodedata.category(char) == "Cc" and char not in "\t\r\n"
                        for char in decoded
                    ):
                        raise WorkspaceError(
                            "INVALID_FILE_CONTENT", "Text contains binary data", 422
                        )
                header = (header + chunk[:5])[:5]
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    # 5. 写入文件内容
                    written = os.write(file_fd, view)
                    if not written:
                        raise OSError("short write")
                    view = view[written:]
            if mime == "application/pdf":
                if not header.startswith(b"%PDF-"):
                    raise WorkspaceError("INVALID_FILE_CONTENT", "Invalid PDF signature", 422)
            else:
                decoder.decode(b"", final=True)
            # 6. 同步文件数据到磁盘
            os.fsync(file_fd)
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size:
                raise WorkspaceError("INVALID_FILE_PATH", "Unsafe file object", 422)
            self._assert_location(thread_id, directory)
            # 7. 将临时文件链接到最终文件名
            os.link(
                temporary, key, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False
            )
            published = True
            # 8. 删除临时文件
            os.unlink(temporary, dir_fd=directory)
            temporary_created = False
            os.fsync(directory)
            self._assert_location(thread_id, directory)
            target = os.stat(key, dir_fd=directory, follow_symlinks=False)
            written = os.fstat(file_fd)
            if (
                not stat.S_ISREG(target.st_mode)
                or target.st_nlink != 1
                or (target.st_dev, target.st_ino) != (written.st_dev, written.st_ino)
            ):
                raise WorkspaceError("INVALID_FILE_PATH", "Published file changed", 422)
            record = FileRecord(
                id=str(uuid4()),
                thread_id=thread_id,
                run_id=run_id,
                display_name=name,
                kind=kind,
                storage_key=key,
                mime=mime,
                size_bytes=size,
                sha256=digest.hexdigest(),
                created_at=utc_now_iso(),
            )
            success = True
            # 9. 返回已登记的文件元数据和目录描述符
            return StoredFile(record, directory)
        except UnicodeError:
            raise WorkspaceError("INVALID_FILE_CONTENT", "Text must use valid UTF-8", 422) from None
        except OSError:
            raise WorkspaceError("INVALID_FILE_PATH", "Secure file operation failed", 422) from None
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            if not success and directory >= 0:
                if temporary_created:
                    self._unlink(directory, temporary)
                if published:
                    self._unlink(directory, key)
                os.close(directory)

    @staticmethod
    def _unlink(fd: int, key: str) -> None:
        """删除文件或目录项"""
        try:
            os.unlink(key, dir_fd=fd)
        except OSError:
            pass

    def discard_new(self, stored: StoredFile) -> None:
        """删除新文件"""
        self._unlink(stored.directory_fd, stored.record.storage_key)
        stored.close()

    def verify_new(self, stored: StoredFile) -> None:
        """验证新文件位置"""
        try:
            self._assert_location(stored.record.thread_id, stored.directory_fd)
        except OSError:
            raise WorkspaceError("INVALID_FILE_PATH", "Workspace directory changed", 422) from None

    def read_registered(self, record: FileRecord) -> bytes:
        """读取已登记文件内容"""
        directory = file_fd = -1
        try:
            if UUID(record.storage_key).hex != record.storage_key:
                raise WorkspaceError("INVALID_FILE_PATH", "Invalid internal file key", 422)
            directory = self._thread_directory(record.thread_id, create=False)
            file_fd = os.open(
                record.storage_key,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=directory,
            )
            before = os.fstat(file_fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_uid != os.getuid()
            ):
                raise WorkspaceError("INVALID_FILE_PATH", "Unsafe file object", 422)
            if before.st_size != record.size_bytes or not 0 <= before.st_size <= PDF_UPLOAD_LIMIT:
                raise WorkspaceError("INVALID_FILE_CONTENT", "Registered file has changed", 422)
            data = bytearray()
            while chunk := os.read(file_fd, CHUNK_SIZE):
                data.extend(chunk)
                if len(data) > record.size_bytes:
                    raise WorkspaceError("INVALID_FILE_CONTENT", "Registered file has changed", 422)
            after = os.fstat(file_fd)
            self._assert_location(record.thread_id, directory)
            if (
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or len(data) != record.size_bytes
                or hashlib.sha256(data).hexdigest() != record.sha256
            ):
                raise WorkspaceError("INVALID_FILE_CONTENT", "Registered file has changed", 422)
            return bytes(data)
        except (OSError, ValueError):
            raise WorkspaceError("INVALID_FILE_PATH", "Secure file read failed", 422) from None
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            if directory >= 0:
                os.close(directory)

    async def save_text(
        self, thread_id: str, run_id: str, name: str, content: str, mime: str
    ) -> StoredFile:
        """保存文本文件"""
        from minideerflow.workspace.models import WRITE_LIMIT

        try:
            data = content.encode("utf-8", errors="strict")
        except UnicodeError:
            raise WorkspaceError("INVALID_FILE_CONTENT", "Text must use valid UTF-8", 422) from None
        if len(data) > WRITE_LIMIT:
            raise WorkspaceError("FILE_TOO_LARGE", "Tool write exceeds 128KiB", 413)

        async def chunks():
            for start in range(0, len(data), CHUNK_SIZE):
                yield data[start : start + CHUNK_SIZE]

        return await self._save(
            thread_id, name, mime, chunks(), WRITE_LIMIT, kind=FileKind.ARTIFACT, run_id=run_id
        )
