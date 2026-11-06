"""注册表快照和默认拒绝策略。"""

import pytest

from minideerflow.tools.calculator import calculate
from minideerflow.tools.registry import (
    ToolDefinition,
    ToolPolicy,
    ToolPolicyError,
    ToolRegistry,
    register_builtin_tools,
)


def test_registry_unique_and_default_deny():
    registry = ToolRegistry()
    register_builtin_tools(registry)
    assert registry.names == {
        "calculate",
        "list_files",
        "read_text",
        "write_text",
        "write_todos",
        "task",
    }
    assert registry.list_allowed(ToolPolicy("run", "thread")) == []
    policy = ToolPolicy("run", "thread", registry.names, frozenset({"read"}))
    assert {t.name for t in registry.list_allowed(policy)} == {
        "calculate",
        "list_files",
        "read_text",
    }
    with pytest.raises(ToolPolicyError, match="TOOL_DUPLICATE"):
        register_builtin_tools(registry)
    registry.freeze()
    with pytest.raises(ToolPolicyError, match="TOOL_REGISTRY_FROZEN"):
        registry.register(
            ToolDefinition("calculate", calculate, "builtin", "read", 5, "builtin", "calc")
        )
    assert all(
        set(t) == {"name", "source", "permission", "origin", "availability"}
        for t in registry.list_catalog()
    )
