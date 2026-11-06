"""业务 SQLite 的单连接与事务边界，不涉及 Graph 内部表。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL DEFAULT '新会话' CHECK(length(trim(title)) BETWEEN 1 AND 100),
    needs_recovery INTEGER NOT NULL DEFAULT 0 CHECK(needs_recovery IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY NOT NULL,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    input_message TEXT NOT NULL CHECK(length(trim(input_message)) BETWEEN 1 AND 2000),
    status TEXT NOT NULL CHECK(status IN ('CREATED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    answer TEXT,
    tool_trace_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_runs_thread_history ON runs(thread_id, created_at, id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_one_active_per_thread
    ON runs(thread_id) WHERE status IN ('CREATED', 'RUNNING');
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY NOT NULL,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    run_id TEXT REFERENCES runs(id),
    display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 120),
    storage_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN ('UPLOAD','ARTIFACT')),
    mime TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    created_at TEXT NOT NULL,
    CHECK((kind='UPLOAD' AND run_id IS NULL) OR (kind='ARTIFACT' AND run_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_files_thread ON files(thread_id,created_at,id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_artifact_display_name
    ON files(thread_id,display_name) WHERE kind='ARTIFACT';
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY NOT NULL,
    file_id TEXT UNIQUE NOT NULL REFERENCES files(id),
    thread_id TEXT NOT NULL REFERENCES threads(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_artifacts_thread ON artifacts(thread_id,created_at,id);

CREATE TABLE IF NOT EXISTS run_todos (
    run_id TEXT NOT NULL REFERENCES runs(id), todo_id TEXT NOT NULL,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
    status TEXT NOT NULL CHECK(status IN ('pending','in_progress','completed')),
    position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 7), updated_at TEXT NOT NULL,
    PRIMARY KEY(run_id,todo_id), UNIQUE(run_id,position)
);
CREATE TABLE IF NOT EXISTS subtasks (
    id TEXT PRIMARY KEY NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id),
    thread_id TEXT NOT NULL REFERENCES threads(id),
    agent_type TEXT NOT NULL CHECK(agent_type IN ('general','research')),
    description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 1000),
    todo_id TEXT, status TEXT NOT NULL CHECK(status IN ('PENDING','RUNNING','COMPLETED','FAILED','CANCELLED','TIMED_OUT')),
    result_summary TEXT, error_code TEXT, source_file_ids_json TEXT NOT NULL DEFAULT '[]',
    truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0,1)),
    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_subtasks_run ON subtasks(run_id,created_at,id);
"""


class RuntimeDatabase:
    """用进程内锁串行化共享连接，关键写操作再由 SQLite 事务保护。"""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection
        self._lock = asyncio.Lock()
        self._closed = False

    @classmethod
    async def open(cls, path: Path) -> "RuntimeDatabase":
        """创建父目录并开启业务库；打开失败时不遗留工作线程。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(path, isolation_level=None)
        try:
            connection.row_factory = aiosqlite.Row
            for pragma in (
                "PRAGMA foreign_keys=ON",
                "PRAGMA journal_mode=WAL",
                "PRAGMA busy_timeout=5000",
            ):
                async with connection.execute(pragma):
                    pass
            return cls(connection)
        except BaseException:
            await connection.close()
            raise

    async def init_schema(self) -> None:
        """仅初始化本项目业务表，不修改 Saver 的数据库结构。"""
        async with self._lock:
            try:
                await self.connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            except BaseException:
                await self.connection.rollback()
                raise

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """将检查和写入放在同一事务，异常或取消时显式回滚。"""
        async with self._lock:
            # 1. 锁保护同一连接；BEGIN IMMEDIATE 同时保护其它连接的竞争写入。
            await self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                # 2. 只有所有检查和 SQL 都成功才提交。
                await self.connection.commit()
            except BaseException:
                # 3. 包括协程取消，均不留下半个事务。
                await self.connection.rollback()
                raise

    async def close(self) -> None:
        """在生命周期退出时释放连接；允许异常清理重复调用。"""
        async with self._lock:
            if not self._closed:
                await self.connection.close()
                self._closed = True
