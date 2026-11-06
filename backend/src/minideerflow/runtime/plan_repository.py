"""计划/委派使用既有业务库，归属与状态检查和写入共用事务。"""

from minideerflow.agents.state import TodoInput, TodoItem
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import utc_now_iso
from minideerflow.runtime.repository import _run


class PlanError(Exception):
    """模型只接收稳定错误码，绝不接收底层 SQL/路径。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def active_run(conn, run_id: str, thread_id: str):
    """事务内确认真实 Run 的 Thread 和运行状态。"""
    run = await _run(conn, run_id)
    if run.thread_id != thread_id or run.status != "RUNNING":
        raise PlanError("CONTEXT_INVALID")
    return run


class PlanRepository:
    """单库快照是历史页面权威数据；Checkpoint 负责父图当前状态。"""

    def __init__(self, database: RuntimeDatabase):
        self.database = database

    async def list_todos(self, run_id: str) -> list[TodoItem]:
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            async with conn.execute(
                "SELECT todo_id,title,status,position FROM run_todos WHERE run_id=? ORDER BY position",
                (run_id,),
            ) as cur:
                return [TodoItem(**dict(row)) for row in await cur.fetchall()]

    async def replace_todos(
        self, run_id: str, thread_id: str, items: list[TodoInput]
    ) -> list[TodoItem]:
        """完整列表原子替换：拒绝删 ID、重复 ID 和 completed 回退。"""
        if not 1 <= len(items) <= 8 or len({i.todo_id for i in items}) != len(items):
            raise PlanError("TODO_INVALID")
        async with self.database.transaction() as conn:
            # 1. 在写锁内读取旧计划，不能由并行调用覆盖约束检查。
            await active_run(conn, run_id, thread_id)
            async with conn.execute(
                "SELECT todo_id,status FROM run_todos WHERE run_id=?", (run_id,)
            ) as cur:
                old = {row["todo_id"]: row["status"] for row in await cur.fetchall()}
            new = {i.todo_id: i.status for i in items}
            if not old.keys() <= new.keys() or any(
                s == "completed" and new[k] != s for k, s in old.items()
            ):
                raise PlanError("TODO_INVALID_TRANSITION")
            # 2. 同一事务删除/重插，避免 position 唯一键交换时中间冲突。
            result = [TodoItem(**item.model_dump(), position=n) for n, item in enumerate(items)]
            await conn.execute("DELETE FROM run_todos WHERE run_id=?", (run_id,))
            await conn.executemany(
                "INSERT INTO run_todos VALUES(?,?,?,?,?,?)",
                [(run_id, i.todo_id, i.title, i.status, i.position, utc_now_iso()) for i in result],
            )
            return result

    async def list_subtasks(self, run_id: str) -> list:
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            return []
