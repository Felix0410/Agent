"""真实官方Middleware+Graph：Command保持、白名单/schema/取消可观测。"""

import asyncio
from dataclasses import replace

import pytest
from langchain.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.state import P04AgentState
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.plan_repository import PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.streaming import stream_agent
from minideerflow.tools.executor import ToolGuardMiddleware
from minideerflow.tools.registry import (
    ToolDefinition,
    ToolPolicy,
    ToolRegistry,
    register_builtin_tools,
)


@pytest.mark.parametrize("mode", ["allowed", "denied", "permission", "forged", "schema", "command"])
def test_real_guard_runtime_and_command(tmp_path, mode):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            registry = ToolRegistry()
            register_builtin_tools(registry)
            registry.freeze()
            policy = ToolPolicy(
                run.id, thread.id, registry.names, frozenset({"read", "write", "orchestrate"})
            )
            if mode == "denied":
                policy = replace(policy, allowed_names=frozenset())
            if mode == "permission":
                policy = replace(policy, allowed_permissions=frozenset())
            if mode == "forged":
                policy = replace(policy, run_id="forged")
            ctx = AgentRunContext(
                thread.id,
                run.id,
                ws,
                PlanService(PlanRepository(repo.database)),
                tool_policy=policy,
            )
            args = {"expression": "(12+8)*3"}
            if mode == "schema":
                args["thread_id"] = thread.id
            name = "calculate"
            if mode == "command":
                name = "write_todos"
                args = {"items": [{"todo_id": "one", "title": "plan", "status": "in_progress"}]}
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="", tool_calls=[{"name": name, "args": args, "id": "original-id"}]
                    ),
                    AIMessage(content="done"),
                ]
            )
            async with open_checkpointer(tmp_path / "saver") as saver:
                graph = build_lead_agent(
                    model,
                    registry.list_allowed(
                        ToolPolicy(
                            run.id,
                            thread.id,
                            registry.names,
                            frozenset({"read", "write", "orchestrate"}),
                        )
                    ),
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                    middleware=[ToolGuardMiddleware(registry)],
                )
                result = await stream_agent(
                    graph, thread.id, "test", context=ctx, initial_state_extra={"todos": []}
                )
                state = (await graph.aget_state(thread_config(thread.id))).values
                returned = next(m for m in state["messages"] if isinstance(m, ToolMessage))
                assert returned.tool_call_id == "original-id"
                if mode in ["allowed", "command"]:
                    assert result.tool_calls[0].ok
                    if mode == "allowed":
                        assert result.tool_calls[0].result == "60"
                    else:
                        assert state["todos"][0]["todo_id"] == "one"
                        assert len(await ctx.todo_service.repository.list_todos(run.id)) == 1
                else:
                    assert returned.status == "error" and not result.tool_calls[0].ok

    asyncio.run(scenario())


def test_timeout_once_and_cancellation_propagates(tmp_path):
    async def scenario():
        entered = asyncio.Event()
        exited = asyncio.Event()
        calls = 0

        @tool
        async def waiting() -> str:
            """Wait for a synthetic test event."""
            nonlocal calls
            calls += 1
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()
            return "unreachable"

        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            for mode in ["timeout", "cancel"]:
                registry = ToolRegistry()
                registry.register(
                    ToolDefinition(
                        "waiting",
                        waiting,
                        "builtin",
                        "read",
                        0.01 if mode == "timeout" else 20,
                        "builtin",
                        "test",
                    )
                )
                registry.freeze()
                ctx = AgentRunContext(
                    thread.id,
                    run.id,
                    ws,
                    None,
                    tool_policy=ToolPolicy(run.id, thread.id, registry.names, frozenset({"read"})),
                )
                model = ScriptedModel(
                    responses=[
                        AIMessage(
                            content="", tool_calls=[{"name": "waiting", "id": "wait", "args": {}}]
                        ),
                        AIMessage(content="done"),
                    ]
                )
                graph = build_lead_agent(
                    model,
                    [waiting],
                    context_schema=AgentRunContext,
                    middleware=[ToolGuardMiddleware(registry)],
                )
                entered.clear()
                exited.clear()
                work = asyncio.create_task(
                    graph.ainvoke({"messages": [{"role": "user", "content": "wait"}]}, context=ctx)
                )
                await entered.wait()
                if mode == "cancel":
                    work.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await work
                else:
                    result = await work
                    returned = next(m for m in result["messages"] if isinstance(m, ToolMessage))
                    assert returned.status == "error" and "TOOL_TIMEOUT" in returned.content
                assert exited.is_set()
            assert calls == 2

    asyncio.run(scenario())
