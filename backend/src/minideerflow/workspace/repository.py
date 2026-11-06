"""文件元数据复用现有业务连接，配额与登记在同一 SQLite 事务内。"""

import aiosqlite

from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.workspace.models import (
    THREAD_BYTES_LIMIT,
    THREAD_FILE_LIMIT,
    ArtifactRecord,
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

    async def _run(self, conn: aiosqlite.Connection, thread_id: str, run_id: str) -> None:
        validate_uuid(run_id)
        await self._thread(conn, thread_id)
        async with conn.execute(
            "SELECT 1 FROM runs WHERE id=? AND thread_id=? AND status='RUNNING'",
            (run_id, thread_id),
        ) as cursor:
            if await cursor.fetchone() is None:
                raise WorkspaceError("INVALID_FILE_PATH", "Run is not active in this thread", 422)

    async def check_run(self, thread_id: str, run_id: str) -> None:
        """文件工具只允许当前真实 Run 使用本 Thread，Prompt/JSON 不提供身份。"""
        async with self.database.transaction() as conn:
            await self._run(conn, thread_id, run_id)

    async def get_file_for_thread(self, thread_id: str, file_id: str) -> FileRecord:
        """归属不符与未知 ID 均返回404，校验完成后调用方才能触碰磁盘。"""
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                "SELECT * FROM files WHERE id=? AND thread_id=?", (file_id, thread_id)
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise WorkspaceError("FILE_NOT_FOUND", "File not found", 404)
            return FileRecord(**dict(row))

    async def register_artifact(self, file: FileRecord) -> ArtifactRecord:
        """真实文件与Artifact双表原子登记，同时检查Run归属、额度与同名冲突。"""
        from uuid import uuid4

        if file.kind != FileKind.ARTIFACT or file.run_id is None:
            raise WorkspaceError("INVALID_FILE_PATH", "Invalid artifact metadata", 422)
        artifact = ArtifactRecord(
            artifact_id=str(uuid4()),
            file_id=file.id,
            thread_id=file.thread_id,
            run_id=file.run_id,
            display_name=file.display_name,
            size_bytes=file.size_bytes,
            mime=file.mime,
            created_at=file.created_at,
        )
        async with self.database.transaction() as conn:
            # 1. 登记前再次验证活动Run，不能只依赖磁盘写入前的快照。
            await self._run(conn, file.thread_id, file.run_id)
            await self._quota(conn, file)
            try:
                # 2. 两表同事务，名称冲突由部分UNIQUE索引无覆盖兜底。
                await self._insert_file(conn, file)
                await conn.execute(
                    "INSERT INTO artifacts(id,file_id,thread_id,run_id,created_at) VALUES(?,?,?,?,?)",
                    (artifact.artifact_id, file.id, file.thread_id, file.run_id, file.created_at),
                )
            except aiosqlite.IntegrityError as exc:
                if "files.thread_id, files.display_name" in str(exc):
                    raise WorkspaceError(
                        "ARTIFACT_NAME_CONFLICT", "Artifact name already exists", 409
                    ) from None
                raise WorkspaceError(
                    "WORKSPACE_UNAVAILABLE", "Artifact registration failed", 503
                ) from None
        return artifact

    _ARTIFACT_QUERY = """SELECT a.id AS artifact_id, a.file_id, a.thread_id, a.run_id, a.created_at,
        f.display_name, f.size_bytes, f.mime FROM artifacts a
        JOIN files f ON f.id=a.file_id AND f.thread_id=a.thread_id AND f.run_id=a.run_id
        JOIN runs r ON r.id=a.run_id AND r.thread_id=a.thread_id
        WHERE f.kind='ARTIFACT' """

    async def list_artifacts(self, thread_id: str) -> list[ArtifactRecord]:
        """只列出file/run/thread关联一致的真实产物，不按磁盘扫描推测。"""

        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                self._ARTIFACT_QUERY + "AND a.thread_id=? ORDER BY a.created_at,a.id",
                (thread_id,),
            ) as cursor:
                return [ArtifactRecord(**dict(row)) for row in await cursor.fetchall()]

    async def get_artifact(self, thread_id: str, artifact_id: str) -> ArtifactRecord:
        """归属错配与未知产物均不可读取，不泄露其它会话的资源。"""

        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                self._ARTIFACT_QUERY + "AND a.id=? AND a.thread_id=?", (artifact_id, thread_id)
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise WorkspaceError("ARTIFACT_NOT_FOUND", "Artifact not found", 404)
            return ArtifactRecord(**dict(row))

    async def discard_upload(self, file: FileRecord) -> None:
        """只补偿本次已知UUID/内部键上传，不删除产物或其它资源。"""
        async with self.database.transaction() as conn:
            await conn.execute(
                "DELETE FROM files WHERE id=? AND storage_key=? AND thread_id=? AND kind='UPLOAD' AND run_id IS NULL",
                (file.id, file.storage_key, file.thread_id),
            )
