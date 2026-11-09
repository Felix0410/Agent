"""Run 层构造的冻结依赖；不进入模型参数或持久 State。"""

from dataclasses import dataclass
from typing import Any

from minideerflow.workspace.models import WorkspaceContext


@dataclass(frozen=True)
class AgentRunContext(WorkspaceContext):
    """智能运行上下文，包含工作空间上下文和智能体服务。"""

    todo_service: Any
    event_sink: Any = None
    task_dispatcher: Any = None
    allowed_tools: tuple[str, ...] = ("calculate", "list_files", "read_text", "write_text")
    tool_policy: Any = None
    skill_service: Any = None
    research_service: Any = None
    budget_tracker: Any = None
    usage_recorder: Any = None


@dataclass(frozen=True)
class ChildContext(WorkspaceContext):
    """子agent运行上下文，包含工作空间上下文和子运行服务。"""

    research_service: Any = None
    tool_policy: Any = None
    tool_registry: Any = None
    event_sink: Any = None
    budget_tracker: Any = None
    usage_recorder: Any = None
