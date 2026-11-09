"""计划任务工具"""

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
        # 1. 检查上下文是否有效
        context = runtime.context
        if not isinstance(context, AgentRunContext) or not isinstance(
            context.todo_service, PlanService
        ):
            raise PlanError("TODO_CONTEXT_INVALID")
        # 2. 调用计划服务更新计划
        todos = await context.todo_service.write_todos(context, items, runtime.state)
        # 3. 更新计划任务以及追加一条工具回执消息
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
    except Exception as exc:
        code = exc.code if isinstance(exc, PlanError) else "TODO_UNAVAILABLE"
        # 4. 失败时添加一条错误消息
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
