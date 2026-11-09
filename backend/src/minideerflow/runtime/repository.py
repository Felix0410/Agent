"""Thread/Run 业务持久化；所有状态写入集中在事务内。"""

import json
from uuid import uuid4

import aiosqlite

from minideerflow.agents.service import ToolTrace, validate_message
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import RunDto, RunStatus, ThreadDto, utc_now_iso


class RepositoryError(Exception):
    """数据库操作异常"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def _thread(connection: aiosqlite.Connection, thread_id: str) -> ThreadDto:
    """查询会话详情"""
    async with connection.execute("SELECT * FROM threads WHERE id=?", (thread_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise RepositoryError("THREAD_NOT_FOUND", "Thread not found")
    return ThreadDto(**dict(row))


async def _run(connection: aiosqlite.Connection, run_id: str) -> RunDto:
    """查询 Run 详情"""
    async with connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise RepositoryError("RUN_NOT_FOUND", "Run not found")
    return _run_dto(row)


def _run_dto(row: aiosqlite.Row) -> RunDto:
    """将数据库行转换为 Run 详情"""
    data = dict(row)
    data["tool_calls"] = json.loads(data.pop("tool_trace_json"))
    return RunDto(**data)


class RuntimeRepository:
    """运行时数据库操作"""

    # 初始化数据库连接
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    async def create_thread(self, title: str = "新会话") -> ThreadDto:
        """创建一个新会话"""
        now = utc_now_iso()
        thread = ThreadDto(id=str(uuid4()), title=title, created_at=now, updated_at=now)
        async with self.database.transaction() as conn:
            await conn.execute(
                "INSERT INTO threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (thread.id, thread.title, now, now),
            )
        return thread

    async def list_threads(self) -> list[ThreadDto]:
        """查询所有会话"""
        async with (
            self.database.transaction() as conn,
            conn.execute("SELECT * FROM threads ORDER BY updated_at DESC, id DESC") as cursor,
        ):
            return [ThreadDto(**dict(row)) for row in await cursor.fetchall()]

    async def get_thread(self, thread_id: str) -> ThreadDto:
        """读取会话详情"""
        async with self.database.transaction() as conn:
            return await _thread(conn, thread_id)

    async def list_runs(self, thread_id: str, limit: int = 50) -> list[RunDto]:
        """查询会话下的最近几条 Run"""
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
        """创建一个新 Run"""
        validate_message(message)
        run = RunDto(
            id=str(uuid4()),
            thread_id=thread_id,
            input_message=message,
            status=RunStatus.CREATED,
            created_at=utc_now_iso(),
        )
        async with self.database.transaction() as conn:
            # 检查会话是否需要恢复
            thread = await _thread(conn, thread_id)
            if thread.needs_recovery:
                raise RepositoryError("THREAD_REQUIRES_RECOVERY", "Create a new thread to continue")
            try:
                await conn.execute(
                    "INSERT INTO runs(id,thread_id,input_message,status,created_at) VALUES(?,?,?,?,?)",
                    (run.id, thread_id, message, run.status.value, run.created_at),
                )
            # 处理唯一索引冲突
            except aiosqlite.IntegrityError as exc:
                if "runs.thread_id" in str(exc):
                    raise RepositoryError(
                        "THREAD_BUSY", "Thread already has an active run"
                    ) from None
                raise
            # 更新会话时间
            await conn.execute(
                "UPDATE threads SET updated_at=? WHERE id=?", (run.created_at, thread_id)
            )
        return run

    async def check_thread_available(self, thread_id: str) -> None:
        """检查会话是否可用"""
        async with self.database.transaction() as conn:
            thread = await _thread(conn, thread_id)
            if thread.needs_recovery:
                raise RepositoryError("THREAD_REQUIRES_RECOVERY", "Create a new thread to continue")
            async with conn.execute(
                "SELECT 1 FROM runs WHERE thread_id=? AND status IN ('CREATED','RUNNING')",
                (thread_id,),
            ) as cursor:
                if await cursor.fetchone():
                    raise RepositoryError("THREAD_BUSY", "Thread already has an active run")

    async def get_run(self, run_id: str) -> RunDto:
        """读取 Run 详情"""
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
        """更新 Run 状态"""
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
        """终结 Run"""
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
        """更新 Run 状态"""
        async with self.database.transaction() as conn:
            # 1. 查询当前 Run 状态
            current = await _run(conn, run_id)
            # 2. 检查状态迁移是否符合规格
            allowed = {
                (RunStatus.CREATED, RunStatus.RUNNING),
                (RunStatus.CREATED, RunStatus.FAILED),
                (RunStatus.RUNNING, RunStatus.SUCCEEDED),
                (RunStatus.RUNNING, RunStatus.FAILED),
                (RunStatus.CREATED, RunStatus.CANCELLED),
                (RunStatus.RUNNING, RunStatus.CANCELLED),
            }
            if current.status not in expected or (current.status, target) not in allowed:
                raise RepositoryError("INVALID_RUN_TRANSITION", "Run transition rejected")
            if target == RunStatus.SUCCEEDED and current.cancel_requested_at is not None:
                raise RepositoryError("RUN_CANCEL_REQUESTED", "Cancellation already requested")
            if target == RunStatus.CANCELLED and current.cancel_requested_at is None:
                raise RepositoryError("INVALID_RUN_TRANSITION", "Cancellation was not requested")
            terminal = target in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)
            if target == RunStatus.SUCCEEDED and (not answer or not answer.strip()):
                raise ValueError("successful run requires a final answer")
            if target == RunStatus.FAILED and not error_code:
                raise ValueError("failed run requires an error code")
            now = utc_now_iso()
            # 3. 更新 Run 状态
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
            # 4. 更新会话状态
            await conn.execute(
                "UPDATE threads SET updated_at=?, needs_recovery=MAX(needs_recovery,?) WHERE id=?",
                (
                    now,
                    int(needs_recovery and target in (RunStatus.FAILED, RunStatus.CANCELLED)),
                    current.thread_id,
                ),
            )
            # 5. 返回更新后的 Run 状态
            result = await _run(conn, run_id)
        return result

    async def request_cancel(self, run_id):
        """请求取消 Run"""
        async with self.database.transaction() as conn:
            # 1. 查询当前 Run 状态
            current = await _run(conn, run_id)
            # 2. 检查状态是否符合规格
            if (
                current.status not in (RunStatus.CREATED, RunStatus.RUNNING)
                or current.cancel_requested_at
            ):
                return current, False
            now = utc_now_iso()
            # 3. 更新 Run 状态为 CANCELLED
            if current.status == RunStatus.CREATED:
                await conn.execute(
                    "UPDATE runs SET status='CANCELLED',cancel_requested_at=?,finished_at=? WHERE id=? AND status='CREATED'",
                    (now, now, run_id),
                )
            else:
                await conn.execute(
                    "UPDATE runs SET cancel_requested_at=? WHERE id=? AND status='RUNNING' AND cancel_requested_at IS NULL",
                    (now, run_id),
                )
            return await _run(conn, run_id), True

    async def complete_cancel(self, run_id, needs_recovery=False):
        """成功取消 Run记录"""
        current = await self.get_run(run_id)
        if current.status not in (RunStatus.CREATED, RunStatus.RUNNING):
            return current
        try:
            return await self._update_run(
                run_id,
                {RunStatus.CREATED, RunStatus.RUNNING},
                RunStatus.CANCELLED,
                None,
                None,
                None,
                needs_recovery,
            )
        except RepositoryError:
            current = await self.get_run(run_id)
            if current.status not in (RunStatus.CREATED, RunStatus.RUNNING):
                return current
            raise

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
