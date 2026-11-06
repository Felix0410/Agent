"""POSIX fd 安全存储：名字不参与磁盘寻址，发布从不覆盖已有对象。"""

import codecs
import hashlib
import os
import stat
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
    """登记前继续持有目录 fd，失败清理不重新解析可能被替换的路径。"""

    record: FileRecord
    directory_fd: int

    def close(self) -> None:
        if self.directory_fd >= 0:
            os.close(self.directory_fd)
            self.directory_fd = -1


class WorkspaceStorage:
    """只信任自己打开的目录 inode；不提供按用户路径读写的方法。"""

    def __init__(self, root: Path) -> None:
        if not root.is_absolute() or ".." in root.parts:
            raise WorkspaceError("INVALID_FILE_PATH", "Workspace root must be absolute", 422)
        self.root = root
        self._root_fd = -1

    def open(self) -> None:
        """逐级 no-follow 打开/创建根目录，缺少安全能力时拒绝启动。"""
        required = (os.open, os.mkdir, os.stat, os.link, os.unlink)
        if (
            os.name != "posix"
            or not hasattr(os, "O_NOFOLLOW")
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
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

    @staticmethod
    def _trusted_directory(fd: int) -> None:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise WorkspaceError("INVALID_FILE_PATH", "Unsafe workspace directory", 422)

    def close(self) -> None:
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def _assert_location(self, thread_id: str, fd: int) -> None:
        """核对已钉住 fd 与当前目录项；替换竞争不能转向 symlink 的目标。"""
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
        """分块读取 UploadFile，不信任客户端 MIME 或 Content-Length。"""

        async def chunks() -> AsyncIterator[bytes]:
            while chunk := await upload.read(CHUNK_SIZE):
                yield chunk

        limit = PDF_UPLOAD_LIMIT if mime == "application/pdf" else TEXT_UPLOAD_LIMIT
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
        directory = -1
        file_fd = -1
        temporary = ".tmp-" + uuid4().hex
        key = uuid4().hex
        temporary_created = published = success = False
        try:
            # 1. 只用内部 UUID 在固定的 Thread fd 下创建独占临时文件。
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
                size += len(chunk)
                if size > limit:
                    raise WorkspaceError("FILE_TOO_LARGE", "File exceeds the permitted size", 413)
                if mime != "application/pdf":
                    decoder.decode(chunk, final=False)
                    if b"\x00" in chunk:
                        raise WorkspaceError(
                            "INVALID_FILE_CONTENT", "Text contains binary data", 422
                        )
                header = (header + chunk[:5])[:5]
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(file_fd, view)
                    if not written:
                        raise OSError("short write")
                    view = view[written:]
            if mime == "application/pdf":
                if not header.startswith(b"%PDF-"):
                    raise WorkspaceError("INVALID_FILE_CONTENT", "Invalid PDF signature", 422)
            else:
                decoder.decode(b"", final=True)
            # 2. fsync 后用 link 原子无覆盖发布；目标即使同时存在也必须失败。
            os.fsync(file_fd)
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise WorkspaceError("INVALID_FILE_PATH", "Unsafe file object", 422)
            self._assert_location(thread_id, directory)
            os.link(
                temporary, key, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False
            )
            published = True
            os.unlink(temporary, dir_fd=directory)
            temporary_created = False
            os.fsync(directory)
            self._assert_location(thread_id, directory)
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
            return StoredFile(record, directory)
        except UnicodeError:
            raise WorkspaceError("INVALID_FILE_CONTENT", "Text must use valid UTF-8", 422) from None
        except OSError:
            raise WorkspaceError("INVALID_FILE_PATH", "Secure file operation failed", 422) from None
        finally:
            # 3. 取消和所有异常都清理本次新文件，不解析路径、不删除碰撞的旧目标。
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
        try:
            os.unlink(key, dir_fd=fd)
        except OSError:
            # 已移走/删除时仅尽力清理；未登记文件永不通过 API 暴露。
            pass

    def discard_new(self, stored: StoredFile) -> None:
        """仅清理本次已发布的新 UUID，不操作用户给定文件名。"""
        self._unlink(stored.directory_fd, stored.record.storage_key)
        stored.close()

    def verify_new(self, stored: StoredFile) -> None:
        try:
            self._assert_location(stored.record.thread_id, stored.directory_fd)
        except OSError:
            raise WorkspaceError("INVALID_FILE_PATH", "Workspace directory changed", 422) from None

    def read_registered(self, record: FileRecord) -> bytes:
        """无跟随打开并复核登记大小/哈希后返回字节，禁止 FileResponse 再次开路径。"""
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
        """小文本使用同一安全发布机制，大小按UTF-8字节而非字符计数。"""
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
