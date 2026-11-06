"""文件元数据复用现有业务连接，配额与登记在同一 SQLite 事务内。"""

import aiosqlite

from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.workspace.models import (
    THREAD_BYTES_LIMIT,
    THREAD_FILE_LIMIT,
    FileKind,
    FileRecord,
    WorkspaceError,
    validate_uuid,
)


class WorkspaceRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def _thread(self, conn: aiosqlite.Connection, thread_id: str) -> None:
        async with conn.execute("SELECT 1 FROM threads WHERE id=?", (thread_id,)) as cursor:
            if await cursor.fetchone() is None:
                raise WorkspaceError("THREAD_NOT_FOUND", "Thread not found", 404)
        validate_uuid(thread_id)

    async def check_thread(self, thread_id: str) -> None:
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)

    async def _quota(self, conn: aiosqlite.Connection, file: FileRecord) -> None:
        async with conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes),0) FROM files WHERE thread_id=?",
            (file.thread_id,),
        ) as cursor:
            count, size = await cursor.fetchone()
        if count >= THREAD_FILE_LIMIT or size + file.size_bytes > THREAD_BYTES_LIMIT:
            raise WorkspaceError("WORKSPACE_QUOTA_EXCEEDED", "Thread file quota exceeded", 409)

    async def _insert_file(self, conn: aiosqlite.Connection, file: FileRecord) -> None:
        await conn.execute(
            """INSERT INTO files(id,thread_id,run_id,display_name,storage_key,kind,mime,
               size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                file.id,
                file.thread_id,
                file.run_id,
                file.display_name,
                file.storage_key,
                file.kind.value,
                file.mime,
                file.size_bytes,
                file.sha256,
                file.created_at,
            ),
        )

    async def register_upload(self, file: FileRecord) -> FileRecord:
        """配额检查与插入共用事务，不能因两个并行上传越过额度。"""
        if file.kind != FileKind.UPLOAD or file.run_id is not None:
            raise WorkspaceError("INVALID_FILE_PATH", "Invalid upload metadata", 422)
        async with self.database.transaction() as conn:
            await self._thread(conn, file.thread_id)
            await self._quota(conn, file)
            await self._insert_file(conn, file)
        return file

    async def list_files(self, thread_id: str) -> list[FileRecord]:
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                "SELECT * FROM files WHERE thread_id=? ORDER BY created_at,id",
                (thread_id,),
            ) as cursor:
                return [FileRecord(**dict(row)) for row in await cursor.fetchall()]

    async def get_file(self, file_id: str) -> FileRecord:
        async with self.database.transaction() as conn:
            async with conn.execute("SELECT * FROM files WHERE id=?", (file_id,)) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise WorkspaceError("FILE_NOT_FOUND", "File not found", 404)
            return FileRecord(**dict(row))
