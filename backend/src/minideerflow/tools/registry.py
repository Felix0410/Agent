"""启动期注册、Run 内固定授权；模型不能修改注册表或权限。"""

import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool


class ToolPolicyError(Exception):
    """对外只传稳定错误码。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ToolPolicy:
    run_id: str
    thread_id: str
    allowed_names: frozenset[str] = frozenset()
    allowed_permissions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    tool: BaseTool
    source: Literal["builtin", "mcp", "skill"]
    permission: Literal["read", "write", "orchestrate"]
    timeout_seconds: float
    origin: str
    description: str


class ToolRegistry:
    """全局唯一工具名；freeze后拒绝注册，不持有任何Run可变状态。"""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._frozen = False
        self._offline: set[str] = set()
        self._unavailable: list[dict] = []

    def register(self, definition: ToolDefinition):
        """工具对象及其公开schema为唯一事实源，不复制schema定义。"""
        if self._frozen:
            raise ToolPolicyError("TOOL_REGISTRY_FROZEN")
        if definition.name in self._tools:
            raise ToolPolicyError("TOOL_DUPLICATE")
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", definition.name)
            or definition.name != definition.tool.name
            or not 0 < definition.timeout_seconds <= 150
            or definition.source not in ("builtin", "mcp", "skill")
            or definition.permission not in ("read", "write", "orchestrate")
        ):
            raise ToolPolicyError("TOOL_INVALID_DEFINITION")
        self._tools[definition.name] = definition

    def freeze(self):
        """lifespan完成装配后关闭注册入口。"""
        self._frozen = True
        return self

    def get(self, name: str) -> ToolDefinition:
        if name in self._offline:
            raise ToolPolicyError("MCP_UNAVAILABLE")
        if name not in self._tools:
            raise ToolPolicyError("TOOL_NOT_ALLOWED")
        return self._tools[name]

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._tools.keys() - self._offline)

    def list_allowed(self, policy: ToolPolicy) -> list[BaseTool]:
        """默认DENY；名字与能力级别必须同时获准。"""
        return [
            d.tool
            for n, d in sorted(self._tools.items())
            if n not in self._offline
            and n in policy.allowed_names
            and d.permission in policy.allowed_permissions
        ]

    def mark_unavailable(self, name: str, origin: str, code: str, source="mcp"):
        """故障条目只展示脱敏状态，永不进入可执行集合。"""
        if self._frozen:
            raise ToolPolicyError("TOOL_REGISTRY_FROZEN")
        self._unavailable.append(
            {
                "name": name,
                "source": source,
                "permission": "read",
                "origin": origin,
                "availability": code,
            }
        )

    def mark_origin_offline(self, origin: str):
        """断连只收回调用能力，不可在运行时恢复/新增工具；恢复需重启。"""
        self._offline.update(
            n for n, d in self._tools.items() if d.source == "mcp" and d.origin == origin
        )

    def list_catalog(self) -> list[dict]:
        """不向页面返回schema长文本、地址、文件路径或认证信息。"""
        return sorted(
            [
                {
                    "name": d.name,
                    "source": d.source,
                    "permission": d.permission,
                    "origin": d.origin,
                    "availability": "MCP_UNAVAILABLE" if d.name in self._offline else "available",
                }
                for d in self._tools.values()
            ]
            + self._unavailable,
            key=lambda d: d["name"],
        )


def register_builtin_tools(registry: ToolRegistry) -> None:
    """保持既有六个工具对象和协议，只附加执行策略。"""
    from minideerflow.tools.calculator import calculate
    from minideerflow.tools.file_tools import list_files, read_text, write_text
    from minideerflow.tools.task_tool import task
    from minideerflow.tools.todo_tool import write_todos

    for tool, permission, timeout in [
        (calculate, "read", 5),
        (list_files, "read", 10),
        (read_text, "read", 10),
        (write_text, "write", 30),
        (write_todos, "orchestrate", 30),
        (task, "orchestrate", 145),
    ]:
        registry.register(
            ToolDefinition(
                tool.name, tool, "builtin", permission, timeout, "builtin", tool.description
            )
        )
