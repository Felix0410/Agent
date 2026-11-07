"""Run 层构造的冻结依赖；不进入模型参数或持久 State。"""

from dataclasses import dataclass
from typing import Any

from minideerflow.workspace.models import WorkspaceContext


@dataclass(frozen=True)
class AgentRunContext(WorkspaceContext):
    todo_service: Any
    event_sink: Any = None
    task_dispatcher: Any = None
    allowed_tools: tuple[str, ...] = ("calculate", "list_files", "read_text", "write_text")
    tool_policy: Any = None
    skill_service: Any = None
    budget_tracker: Any = None
    usage_recorder: Any = None


@dataclass(frozen=True)
class ChildContext(WorkspaceContext):
    """只携带父真实身份与共享预算，既无派发器也无写权限。"""

    budget_tracker: Any = None
    usage_recorder: Any = None
