"""Tool 边界校验与 SQL 后事件通知；事件失败不反转已提交事实。"""

import logging

from langchain_core.messages import AIMessage

from minideerflow.agents.context import AgentRunContext
from minideerflow.runtime.plan_repository import PlanError, PlanRepository


async def safe_emit(context, kind: str, payload: dict) -> None:
    """只输出脱敏错误，不把已提交 SQL 误报为写入失败。"""
    if context.event_sink is not None:
        try:
            await context.event_sink(kind, payload)
        except Exception:  # noqa: BLE001 - 事件错误不反转已提交状态
            logging.getLogger("minideerflow").warning("Plan event unavailable")


class PlanService:
    """不维护第二套 Todo 内存状态。"""

    def __init__(self, repository: PlanRepository):
        self.repository = repository

    async def write_todos(self, context, items, runtime_state):
        """先拒绝同批多写，再提交快照，最后发布已提交结果。"""
        if not isinstance(context, AgentRunContext) or context.todo_service is not self:
            raise PlanError("TODO_CONTEXT_INVALID")
        # 1. 所有同批写入都看到同一 AIMessage，全部拒绝而不是锁后串写。
        messages = runtime_state.get("messages", [])
        last = messages[-1] if messages else None
        if (
            not isinstance(last, AIMessage)
            or sum(c["name"] == "write_todos" for c in last.tool_calls) != 1
        ):
            raise PlanError("TODO_CONFLICT")
        # 2. SQL 快照提交后才可返回 State Command。
        saved = await self.repository.replace_todos(context.run_id, context.thread_id, items)
        todos = [i.model_dump() for i in saved]
        await safe_emit(
            context, "todo_updated", {"run_id": context.run_id, "todos": todos, "revision": last.id}
        )
        return todos
