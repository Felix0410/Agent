"""Thread/Run 业务持久化；所有状态写入集中在事务内。"""

import json
from uuid import uuid4

import aiosqlite

from minideerflow.agents.service import ToolTrace, validate_message
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import RunDto, RunStatus, ThreadDto, utc_now_iso


class RepositoryError(Exception):
    """只携带稳定业务错误，不向路由暴露 SQL 异常文本。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _thread(connection: aiosqlite.Connection, thread_id: str) -> ThreadDto:
    async with connection.execute("SELECT * FROM threads WHERE id=?", (thread_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise RepositoryError("THREAD_NOT_FOUND", "Thread not found")
    return ThreadDto(**dict(row))


async def _run(connection: aiosqlite.Connection, run_id: str) -> RunDto:
    async with connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise RepositoryError("RUN_NOT_FOUND", "Run not found")
    return _run_dto(row)


def _run_dto(row: aiosqlite.Row) -> RunDto:
    data = dict(row)
    data["tool_calls"] = json.loads(data.pop("tool_trace_json"))
    return RunDto(**data)


class RuntimeRepository:
    """单 Worker 内复用同一个业务连接，数据库索引作为并发约束兜底。"""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def create_thread(self, title: str = "新会话") -> ThreadDto:
        """创建会话身份，不创建 Graph 消息或 Run。"""
        now = utc_now_iso()
        thread = ThreadDto(id=str(uuid4()), title=title, created_at=now, updated_at=now)
        async with self.database.transaction() as conn:
            await conn.execute(
                "INSERT INTO threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (thread.id, thread.title, now, now),
            )
        return thread

    async def list_threads(self) -> list[ThreadDto]:
        """按更新时间倒序列出真实会话，相同时间以 ID 稳定排序。"""
        async with (
            self.database.transaction() as conn,
            conn.execute("SELECT * FROM threads ORDER BY updated_at DESC, id DESC") as cursor,
        ):
            return [ThreadDto(**dict(row)) for row in await cursor.fetchall()]

    async def get_thread(self, thread_id: str) -> ThreadDto:
        """读取会话；不存在时抛出稳定的 404 业务错误。"""
        async with self.database.transaction() as conn:
            return await _thread(conn, thread_id)

    async def list_runs(self, thread_id: str, limit: int = 50) -> list[RunDto]:
        """先截取最近 N 条，再按正序返回；空历史与不存在的会话不同。"""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        async with self.database.transaction() as conn:
            await _thread(conn, thread_id)
            async with conn.execute(
                "SELECT * FROM runs WHERE thread_id=? ORDER BY created_at DESC, id DESC LIMIT ?",
                (thread_id, limit),
            ) as cursor:
                return [_run_dto(row) for row in reversed(await cursor.fetchall())]

    async def create_run(self, thread_id: str, message: str) -> RunDto:
        """在同一事务内检查恢复标志、创建 Run 并更新会话时间。"""
        validate_message(message)
        run = RunDto(
            id=str(uuid4()),
            thread_id=thread_id,
            input_message=message,
            status=RunStatus.CREATED,
            created_at=utc_now_iso(),
        )
        async with self.database.transaction() as conn:
            # 1. 恢复状态优先拒绝，不能给部分 Checkpoint 自动接续新消息。
            thread = await _thread(conn, thread_id)
            if thread.needs_recovery:
                raise RepositoryError("THREAD_REQUIRES_RECOVERY", "Create a new thread to continue")
            # 2. 部分唯一索引是最终约束；即使其它连接绕过本地锁也不能重复活动 Run。
            try:
                await conn.execute(
                    "INSERT INTO runs(id,thread_id,input_message,status,created_at) VALUES(?,?,?,?,?)",
                    (run.id, thread_id, message, run.status.value, run.created_at),
                )
            except aiosqlite.IntegrityError as exc:
                if "runs.thread_id" in str(exc):
                    raise RepositoryError(
                        "THREAD_BUSY", "Thread already has an active run"
                    ) from None
                raise
            # 3. 只有插入成功才更新会话，事务失败时两者一起回滚。
            await conn.execute(
                "UPDATE threads SET updated_at=? WHERE id=?", (run.created_at, thread_id)
            )
        return run

    async def get_run(self, run_id: str) -> RunDto:
        """读取权威 Run 状态，而非从 Graph 文本推测是否完成。"""
        async with self.database.transaction() as conn:
            return await _run(conn, run_id)

    async def transition_run(
        self,
        run_id: str,
        expected: RunStatus,
        target: RunStatus,
        *,
        answer: str | None = None,
        tool_calls: list[ToolTrace] | None = None,
        error_code: str | None = None,
        needs_recovery: bool = False,
    ) -> RunDto:
        """执行带 expected 条件的原子状态迁移，终态字段与状态同时落库。"""
        return await self._update_run(
            run_id, {expected}, target, answer, tool_calls, error_code, needs_recovery
        )

    async def complete_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        answer: str | None = None,
        tool_calls: list[ToolTrace] | None = None,
        error_code: str | None = None,
        needs_recovery: bool = False,
    ) -> RunDto:
        """一次性终结活动 Run；进入 Graph 后失败时由调用方明确标记需恢复。"""
        if status not in (RunStatus.SUCCEEDED, RunStatus.FAILED):
            raise RepositoryError("INVALID_RUN_TRANSITION", "Unsupported terminal status")
        return await self._update_run(
            run_id,
            {RunStatus.CREATED, RunStatus.RUNNING},
            status,
            answer,
            tool_calls,
            error_code,
            needs_recovery,
        )

    async def _update_run(
        self,
        run_id: str,
        expected: set[RunStatus],
        target: RunStatus,
        answer: str | None,
        tool_calls: list[ToolTrace] | None,
        error_code: str | None,
        needs_recovery: bool,
    ) -> RunDto:
        """所有状态写入共用的事务，防止多次终结或撤销已提交终态。"""
        async with self.database.transaction() as conn:
            # 1. 在写事务里读取当前状态；仅允许规格列出的单向边。
            current = await _run(conn, run_id)
            allowed = {
                (RunStatus.CREATED, RunStatus.RUNNING),
                (RunStatus.CREATED, RunStatus.FAILED),
                (RunStatus.RUNNING, RunStatus.SUCCEEDED),
                (RunStatus.RUNNING, RunStatus.FAILED),
            }
            if current.status not in expected or (current.status, target) not in allowed:
                raise RepositoryError("INVALID_RUN_TRANSITION", "Run transition rejected")
            terminal = target in (RunStatus.SUCCEEDED, RunStatus.FAILED)
            if target == RunStatus.SUCCEEDED and (not answer or not answer.strip()):
                raise ValueError("successful run requires a final answer")
            if target == RunStatus.FAILED and not error_code:
                raise ValueError("failed run requires an error code")
            now = utc_now_iso()
            # 2. 结果、时间戳和状态作为一次写入，不能先宣称成功再补保存结果。
            await conn.execute(
                """UPDATE runs SET status=?, answer=?, tool_trace_json=?, error_code=?,
                   started_at=?, finished_at=? WHERE id=? AND status=?""",
                (
                    target.value,
                    answer if target == RunStatus.SUCCEEDED else None,
                    json.dumps([t.model_dump() for t in (tool_calls or [])], ensure_ascii=False),
                    error_code if target == RunStatus.FAILED else None,
                    now if target == RunStatus.RUNNING else current.started_at,
                    now if terminal else None,
                    run_id,
                    current.status.value,
                ),
            )
            # 3. 同库事务记录恢复状态；两份 SQLite 之间没有跨库原子提交保证。
            await conn.execute(
                "UPDATE threads SET updated_at=?, needs_recovery=MAX(needs_recovery,?) WHERE id=?",
                (now, int(needs_recovery and target == RunStatus.FAILED), current.thread_id),
            )
            result = await _run(conn, run_id)
        return result

    async def reconcile_orphans(self) -> int:
        """保守标记遗留活动 Run 与所属会话；不声称能无损续跑 Graph。"""
        async with self.database.transaction() as conn:
            # 1. 必须先标记 Thread，再改 Run 状态，防止失去关联查询条件。
            now = utc_now_iso()
            await conn.execute(
                """UPDATE threads SET needs_recovery=1, updated_at=? WHERE id IN
                   (SELECT thread_id FROM runs WHERE status IN ('CREATED','RUNNING'))""",
                (now,),
            )
            # 2. 成功和失败的既有终态不变；所有遗留活动记录统一中断失败。
            async with conn.execute(
                """UPDATE runs SET status='FAILED', error_code='RUN_INTERRUPTED', answer=NULL,
                   finished_at=? WHERE status IN ('CREATED','RUNNING')""",
                (now,),
            ) as cursor:
                return cursor.rowcount
