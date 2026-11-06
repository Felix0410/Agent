"""真实 State 工具，ToolMessage ID 必须匹配当前框架调用。"""

import json

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.state import P04AgentState, TodoInput
from minideerflow.runtime.plan_repository import PlanError
from minideerflow.runtime.plan_service import PlanService


@tool
async def write_todos(
    items: list[TodoInput], runtime: ToolRuntime[AgentRunContext, P04AgentState]
) -> Command:
    """Replace the complete plan (1-8 items). Preserve existing todo_id values; never revert completed items. Use pending/in_progress/completed. Only one write_todos call per model step."""
    try:
        context = runtime.context
        if not isinstance(context, AgentRunContext) or not isinstance(
            context.todo_service, PlanService
        ):
            raise PlanError("TODO_CONTEXT_INVALID")
        todos = await context.todo_service.write_todos(context, items, runtime.state)
        return Command(
            update={
                "todos": todos,
                "messages": [
                    ToolMessage(
                        content=json.dumps(todos, ensure_ascii=False),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001 - 工具边界隐藏底层异常
        code = exc.code if isinstance(exc, PlanError) else "TODO_UNAVAILABLE"
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ERROR[{code}]: Plan update failed",
                        tool_call_id=runtime.tool_call_id,
                        status="error",
                    )
                ]
            }
        )


write_todos.args_schema.model_config["extra"] = "forbid"
write_todos.args_schema.model_rebuild(force=True)
