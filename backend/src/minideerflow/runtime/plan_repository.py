"""计划/委派使用既有业务库，归属与状态检查和写入共用事务。"""

import json
from uuid import uuid4

from minideerflow.agents.state import TodoInput, TodoItem
from minideerflow.agents.subagents.models import TaskRecord, TaskResult, TaskStatus
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

    async def list_subtasks(self, run_id: str) -> list[TaskRecord]:
        """历史任务由 SQL 恢复，不依赖活动 Task 对象。"""
        async with self.database.transaction() as conn:
            await _run(conn, run_id)
            async with conn.execute(
                "SELECT * FROM subtasks WHERE run_id=? ORDER BY created_at,id", (run_id,)
            ) as cur:
                return [self._task(row) for row in await cur.fetchall()]

    @staticmethod
    def _task(row) -> TaskRecord:
        data = dict(row)
        data["source_file_ids"] = json.loads(data.pop("source_file_ids_json"))
        return TaskRecord(**data)

    async def create_subtask(
        self,
        run_id: str,
        thread_id: str,
        agent_type: str,
        description: str,
        todo_id: str | None = None,
    ) -> TaskRecord:
        """只允许活动父 Run 创建，todo 关联必须属于同 Run。"""
        if agent_type not in ("general", "research") or not 1 <= len(description.strip()) <= 1000:
            raise PlanError("SUBTASK_INVALID")
        async with self.database.transaction() as conn:
            await active_run(conn, run_id, thread_id)
            if todo_id is not None:
                async with conn.execute(
                    "SELECT 1 FROM run_todos WHERE run_id=? AND todo_id=?", (run_id, todo_id)
                ) as cur:
                    if await cur.fetchone() is None:
                        raise PlanError("SUBTASK_TODO_INVALID")
            task = TaskRecord(
                id=str(uuid4()),
                run_id=run_id,
                thread_id=thread_id,
                agent_type=agent_type,
                description=description,
                todo_id=todo_id,
                status=TaskStatus.PENDING,
                created_at=utc_now_iso(),
            )
            await conn.execute(
                "INSERT INTO subtasks(id,run_id,thread_id,agent_type,description,todo_id,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    task.id,
                    run_id,
                    thread_id,
                    agent_type,
                    description,
                    todo_id,
                    task.status.value,
                    task.created_at,
                ),
            )
            return task

    async def transition_subtask(
        self,
        task_id: str,
        run_id: str,
        thread_id: str,
        status: TaskStatus,
        result: TaskResult | None = None,
    ) -> TaskRecord:
        """按固定转移更新；终态不可逆，身份条件不能由模型提供。"""
        async with self.database.transaction() as conn:
            async with conn.execute(
                "SELECT * FROM subtasks WHERE id=? AND run_id=? AND thread_id=?",
                (task_id, run_id, thread_id),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                raise PlanError("SUBTASK_NOT_FOUND")
            old = self._task(row)
            allowed = {
                TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED},
                TaskStatus.RUNNING: {
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                    TaskStatus.TIMED_OUT,
                },
            }
            if status not in allowed.get(old.status, set()):
                raise PlanError("SUBTASK_INVALID_TRANSITION")
            if result is not None and (result.task_id != task_id or result.status != status):
                raise PlanError("SUBTASK_INVALID_RESULT")
            # 1. RUNNING 单独记启动时间，终态记录短结果而不保存消息全文。
            if status == TaskStatus.RUNNING:
                await conn.execute(
                    "UPDATE subtasks SET status=?,started_at=? WHERE id=?",
                    (status.value, utc_now_iso(), task_id),
                )
            else:
                await conn.execute(
                    "UPDATE subtasks SET status=?,finished_at=?,result_summary=?,error_code=?,source_file_ids_json=?,truncated=? WHERE id=?",
                    (
                        status.value,
                        utc_now_iso(),
                        result.summary if result else None,
                        result.error_code if result else None,
                        json.dumps(result.source_file_ids if result else []),
                        int(result.truncated) if result else 0,
                        task_id,
                    ),
                )
            async with conn.execute("SELECT * FROM subtasks WHERE id=?", (task_id,)) as cur:
                return self._task(await cur.fetchone())

    async def reconcile_orphaned_subtasks(self) -> int:
        """进程重启只标失败，不重放可能已执行过的工作。"""
        async with self.database.transaction() as conn:
            cur = await conn.execute(
                "UPDATE subtasks SET status='FAILED',error_code='SUBTASK_INTERRUPTED',finished_at=? WHERE status IN ('PENDING','RUNNING')",
                (utc_now_iso(),),
            )
            return cur.rowcount
