"""计划任务服务"""

import logging

from langchain_core.messages import AIMessage

from minideerflow.agents.context import AgentRunContext
from minideerflow.runtime.plan_repository import PlanError, PlanRepository


async def safe_emit(context, kind: str, payload: dict) -> None:
    """安全发布计划任务事件"""
    if context.event_sink is not None:
        try:
            await context.event_sink(kind, payload)
        except Exception:  # noqa: BLE001 - 边界统一脱敏，保持取消和既有失败语义
            logging.getLogger("minideerflow").warning("Plan event unavailable")


class PlanService:
    """计划任务服务"""

    def __init__(self, repository: PlanRepository):
        """初始化计划任务仓库"""
        self.repository = repository

    async def write_todos(self, context, items, runtime_state):
        """更新计划任务"""
        # 1. 检查上下文是否有效
        if not isinstance(context, AgentRunContext) or context.todo_service is not self:
            raise PlanError("TODO_CONTEXT_INVALID")
        # 2. 检查是否有冲突
        messages = runtime_state.get("messages", [])
        last = messages[-1] if messages else None
        if (
            not isinstance(last, AIMessage)
            or sum(c["name"] == "write_todos" for c in last.tool_calls) != 1
        ):
            raise PlanError("TODO_CONFLICT")
        # 3. 更新数据库的计划任务
        saved = await self.repository.replace_todos(context.run_id, context.thread_id, items)
        todos = [i.model_dump() for i in saved]
        await safe_emit(
            context, "todo_updated", {"run_id": context.run_id, "todos": todos, "revision": last.id}
        )
        return todos
