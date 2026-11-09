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
    """文件元数据仓库"""

    def __init__(self, database: RuntimeDatabase) -> None:
        """初始化文件元数据仓库"""
        self.database = database

    async def _thread(self, conn: aiosqlite.Connection, thread_id: str) -> None:
        """验证线程是否存在"""
        async with conn.execute("SELECT 1 FROM threads WHERE id=?", (thread_id,)) as cursor:
            if await cursor.fetchone() is None:
                raise WorkspaceError("THREAD_NOT_FOUND", "Thread not found", 404)
        validate_uuid(thread_id)

    async def check_thread(self, thread_id: str) -> None:
        """验证线程是否存在"""
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)

    async def _quota(self, conn: aiosqlite.Connection, file: FileRecord) -> None:
        """验证线程配额是否足够"""
        async with conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes),0) FROM files WHERE thread_id=?",
            (file.thread_id,),
        ) as cursor:
            count, size = await cursor.fetchone()
        if count >= THREAD_FILE_LIMIT or size + file.size_bytes > THREAD_BYTES_LIMIT:
            raise WorkspaceError("WORKSPACE_QUOTA_EXCEEDED", "Thread file quota exceeded", 409)

    async def _insert_file(self, conn: aiosqlite.Connection, file: FileRecord) -> None:
        """插入文件元数据"""
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
        """登记上传文件"""
        # 1. 验证文件类型
        if file.kind != FileKind.UPLOAD or file.run_id is not None:
            raise WorkspaceError("INVALID_FILE_PATH", "Invalid upload metadata", 422)
        # 2. 验证线程、配额、文件大小是否满足要求
        async with self.database.transaction() as conn:
            await self._thread(conn, file.thread_id)
            await self._quota(conn, file)
            await self._insert_file(conn, file)
        return file

    async def list_files(self, thread_id: str) -> list[FileRecord]:
        """列出线程下所有文件"""
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                "SELECT * FROM files WHERE thread_id=? ORDER BY created_at,id",
                (thread_id,),
            ) as cursor:
                return [FileRecord(**dict(row)) for row in await cursor.fetchall()]

    async def get_file(self, file_id: str) -> FileRecord:
        """获取文件元数据"""
        async with self.database.transaction() as conn:
            async with conn.execute("SELECT * FROM files WHERE id=?", (file_id,)) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise WorkspaceError("FILE_NOT_FOUND", "File not found", 404)
            return FileRecord(**dict(row))

    async def _run(self, conn: aiosqlite.Connection, thread_id: str, run_id: str) -> None:
        """验证线程下是否存在当前运行的 Run"""
        validate_uuid(run_id)
        await self._thread(conn, thread_id)
        async with conn.execute(
            "SELECT 1 FROM runs WHERE id=? AND thread_id=? AND status='RUNNING'",
            (run_id, thread_id),
        ) as cursor:
            if await cursor.fetchone() is None:
                raise WorkspaceError("INVALID_FILE_PATH", "Run is not active in this thread", 422)

    async def check_run(self, thread_id: str, run_id: str) -> None:
        """验证线程下是否存在当前运行的 Run"""
        async with self.database.transaction() as conn:
            await self._run(conn, thread_id, run_id)

    async def get_file_for_thread(self, thread_id: str, file_id: str) -> FileRecord:
        """获取线程下文件元数据"""
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
        """登记Agent生成文件的元数据"""
        from uuid import uuid4

        # 1. 验证文件类型
        if file.kind != FileKind.ARTIFACT or file.run_id is None:
            raise WorkspaceError("INVALID_FILE_PATH", "Invalid artifact metadata", 422)
        # 2. 创建Artifact元数据
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
            # 3. 验证线程下是否存在当前运行的 Run以及配额是否满足要求
            await self._run(conn, file.thread_id, file.run_id)
            await self._quota(conn, file)
            try:
                # 4. 插入文件元数据
                await self._insert_file(conn, file)
                # 5. 插入Artifact元数据
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

    # 查询Artifact元数据的sql
    _ARTIFACT_QUERY = """SELECT a.id AS artifact_id, a.file_id, a.thread_id, a.run_id, a.created_at,
        f.display_name, f.size_bytes, f.mime FROM artifacts a
        JOIN files f ON f.id=a.file_id AND f.thread_id=a.thread_id AND f.run_id=a.run_id
        JOIN runs r ON r.id=a.run_id AND r.thread_id=a.thread_id
        WHERE f.kind='ARTIFACT' """

    async def list_artifacts(self, thread_id: str) -> list[ArtifactRecord]:
        """列出线程下所有Artifact元数据"""
        async with self.database.transaction() as conn:
            await self._thread(conn, thread_id)
            async with conn.execute(
                self._ARTIFACT_QUERY + "AND a.thread_id=? ORDER BY a.created_at,a.id",
                (thread_id,),
            ) as cursor:
                return [ArtifactRecord(**dict(row)) for row in await cursor.fetchall()]

    async def get_artifact(self, thread_id: str, artifact_id: str) -> ArtifactRecord:
        """获取线程下指定Artifact元数据"""
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
        """删除线程下指定上传文件的元数据"""
        async with self.database.transaction() as conn:
            await conn.execute(
                "DELETE FROM files WHERE id=? AND storage_key=? AND thread_id=? AND kind='UPLOAD' AND run_id IS NULL",
                (file.id, file.storage_key, file.thread_id),
            )
