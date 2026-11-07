"""父 Agent 委派入口：公开 Schema 没有身份/路径/权限字段。"""

from langchain.tools import ToolRuntime, tool

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.subagents.dispatcher import TaskDispatcher
from minideerflow.runtime.budget import BudgetError
from minideerflow.runtime.plan_repository import PlanError


@tool
async def task(
    agent_type: str,
    description: str,
    runtime: ToolRuntime[AgentRunContext],
    todo_id: str | None = None,
) -> str:
    """Delegate a focused goal (1-1000 chars) to general or research. Both are read-only; research uses existing material, not the internet. Optional todo_id must belong to this run. No more than four tasks per run."""
    try:
        context = runtime.context
        if not isinstance(context, AgentRunContext) or not isinstance(
            context.task_dispatcher, TaskDispatcher
        ):
            raise PlanError("SUBTASK_CONTEXT_INVALID")
        result = await context.task_dispatcher.dispatch(context, agent_type, description, todo_id)
        if result.error_code:
            return f"ERROR[{result.error_code}]: " + result.model_dump_json()
        return result.model_dump_json()
    except BudgetError:
        raise
    except Exception as exc:  # noqa: BLE001 - 模型边界只输出稳定错误码
        code = exc.code if isinstance(exc, PlanError) else "SUBTASK_UNAVAILABLE"
        return f"ERROR[{code}]: Delegation failed"


task.args_schema.model_config["extra"] = "forbid"
task.args_schema.model_rebuild(force=True)
