"""真实 ToolRuntime/Command/双库测试，不以自然语言模拟计划。"""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.state import P04AgentState, TodoInput
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.plan_repository import PlanError, PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.streaming import stream_agent
from minideerflow.tools.todo_tool import write_todos


def item(status="pending", **kwargs):
    return {"todo_id": "one", "title": "计划", "status": status, **kwargs}


def test_real_command_checkpoint_history_and_reset(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            service = PlanService(plans)
            events = []

            async def emit(k, p):
                events.append((k, p))

            ctx = AgentRunContext(thread.id, run.id, ws, service, emit)
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": str(n), "name": "write_todos", "args": {"items": [item(status)]}}
                        ],
                    )
                    for n, status in enumerate(["pending", "completed"])
                ]
                + [AIMessage(content="done"), AIMessage(content="simple")]
            )
            async with open_checkpointer(tmp_path / "saver.db") as saver:
                agent = build_lead_agent(
                    model,
                    [write_todos],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                )
                result = await stream_agent(
                    agent, thread.id, "plan", context=ctx, initial_state_extra={"todos": []}
                )
                assert len(result.tool_calls) == 2 and all(t.ok for t in result.tool_calls)
                state = (await agent.aget_state(thread_config(thread.id))).values
                assert state["todos"] == [item("completed", position=0)]
                assert [t.model_dump() for t in await plans.list_todos(run.id)] == state["todos"]
                await stream_agent(
                    agent, thread.id, "simple", context=ctx, initial_state_extra={"todos": []}
                )
                assert (await agent.aget_state(thread_config(thread.id))).values["todos"] == []
                assert len(await plans.list_todos(run.id)) == 1
            assert len(events) == 2 and events[0][0] == "todo_updated"

    asyncio.run(scenario())


@pytest.mark.parametrize("bad", ["delete", "revert", "duplicate", "oversize", "wrong_thread"])
def test_atomic_invalid_update(tmp_path, bad):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            initial = [TodoInput(**item("completed"))]
            await plans.replace_todos(run.id, thread.id, initial)
            values = (
                []
                if bad == "delete"
                else [TodoInput(**item())]
                if bad == "revert"
                else initial * 2
                if bad == "duplicate"
                else [TodoInput(**item(todo_id=f"i{n}")) for n in range(9)]
                if bad == "oversize"
                else initial
            )
            with pytest.raises(PlanError):
                await plans.replace_todos(
                    run.id, "wrong" if bad == "wrong_thread" else thread.id, values
                )
            assert (await plans.list_todos(run.id))[0].status == "completed"

    asyncio.run(scenario())


def test_parallel_commands_all_rejected(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            ctx = AgentRunContext(thread.id, run.id, ws, PlanService(plans))
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": str(n), "name": "write_todos", "args": {"items": [item()]}}
                            for n in range(2)
                        ],
                    ),
                    AIMessage(content="conflict"),
                ]
            )
            async with open_checkpointer(tmp_path / "saver.db") as saver:
                agent = build_lead_agent(
                    model,
                    [write_todos],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                )
                result = await stream_agent(
                    agent, thread.id, "plan", context=ctx, initial_state_extra={"todos": []}
                )
                assert all("TODO_CONFLICT" in t.result and not t.ok for t in result.tool_calls)
                assert await plans.list_todos(run.id) == []

    asyncio.run(scenario())


def test_schema():
    assert set(write_todos.tool_call_schema.model_json_schema()["properties"]) == {"items"}
