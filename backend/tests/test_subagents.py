"""真实 child Graph 的消息隔离、权限与 SQL 状态。"""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import Upload, workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.subagents.dispatcher import TaskDispatcher
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.plan_repository import PlanError, PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.streaming import stream_agent
from minideerflow.tools.task_tool import task


@pytest.mark.parametrize("role", ["general", "research"])
def test_real_child_read_and_parent_checkpoint_isolation(tmp_path, role):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            file = await ws.upload(thread.id, Upload(b"controlled notes", "notes.md"))
            child = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": "child-read", "name": "read_text", "args": {"file_id": file.id}}
                        ],
                    ),
                    AIMessage(content="child findings"),
                ]
            )
            plans = PlanRepository(repo.database)
            dispatcher = TaskDispatcher(plans, lambda: child)
            ctx = AgentRunContext(
                thread.id, run.id, ws, PlanService(plans), task_dispatcher=dispatcher
            )
            parent = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "parent-task",
                                "name": "task",
                                "args": {
                                    "agent_type": role,
                                    "description": "Read supplied file " + file.id,
                                },
                            }
                        ],
                    ),
                    AIMessage(content="parent answer"),
                ]
            )
            async with open_checkpointer(tmp_path / "parent.db") as saver:
                graph = build_lead_agent(parent, [task], saver, context_schema=AgentRunContext)
                response = await stream_agent(
                    graph, thread.id, "PARENT_SECRET_HISTORY", context=ctx
                )
                assert response.tool_calls[0].ok
                result = json.loads(response.tool_calls[0].result)
                assert result["source_file_ids"] == [file.id]
                assert result["summary"] == "child findings"
                saved = (await graph.aget_state(thread_config(thread.id))).values["messages"]
                assert not any(getattr(m, "tool_call_id", None) == "child-read" for m in saved)
            assert "PARENT_SECRET_HISTORY" not in str(child.seen)
            records = await plans.list_subtasks(run.id)
            assert (
                len(records) == 1
                and records[0].status == "COMPLETED"
                and records[0].source_file_ids == [file.id]
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode", ["cross_thread", "tool_error", "empty", "huge", "fake_source", "permissions"]
)
def test_child_results_fail_closed(tmp_path, mode):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            other = await repo.create_thread()
            run = await active_run(repo, thread)
            file = await ws.upload(
                other.id if mode == "cross_thread" else thread.id, Upload(b"notes", "notes.md")
            )
            name = "calculate" if mode in ["tool_error", "permissions"] else "read_text"
            args = {"expression": "1/0"} if name == "calculate" else {"file_id": file.id}
            responses = (
                [AIMessage(content="x" * 1601)]
                if mode == "huge"
                else [AIMessage(content="I read " + file.id)]
                if mode == "fake_source"
                else [AIMessage(content="")]
                if mode == "empty"
                else [
                    AIMessage(content="", tool_calls=[{"id": "child", "name": name, "args": args}]),
                    AIMessage(content="claims success"),
                ]
            )
            child = ScriptedModel(responses=responses)
            plans = PlanRepository(repo.database)
            dispatcher = TaskDispatcher(plans, lambda: child)
            ctx = AgentRunContext(
                thread.id, run.id, ws, PlanService(plans), task_dispatcher=dispatcher
            )
            result = await dispatcher.dispatch(
                ctx, "research" if mode == "permissions" else "general", "goal"
            )
            if mode == "huge":
                assert (
                    result.status == "COMPLETED"
                    and result.truncated
                    and len(result.summary) == 1600
                )
            elif mode == "fake_source":
                assert result.status == "COMPLETED" and result.source_file_ids == []
            else:
                assert result.status == "FAILED" and result.summary == ""

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "role,expected",
    [
        ("general", {"calculate", "list_files", "read_text"}),
        ("research", {"list_files", "read_text"}),
    ],
)
def test_allowlist_schema(tmp_path, monkeypatch, role, expected):
    async def scenario():
        from minideerflow.agents.subagents import executor

        original = executor.create_agent

        def capture(model, tools, **kwargs):
            assert {t.name for t in tools} == expected
            assert kwargs["checkpointer"] is None
            assert kwargs["context_schema"].__name__ == "ChildContext"
            return original(model, tools, **kwargs)

        monkeypatch.setattr(executor, "create_agent", capture)
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            dispatcher = TaskDispatcher(
                plans, lambda: ScriptedModel(responses=[AIMessage(content="ok")])
            )
            ctx = AgentRunContext(
                thread.id, run.id, ws, PlanService(plans), task_dispatcher=dispatcher
            )
            assert (await dispatcher.dispatch(ctx, role, "goal")).status == "COMPLETED"

    asyncio.run(scenario())


def test_identity_and_inputs(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            dispatcher = TaskDispatcher(plans, lambda: None)
            ctx = AgentRunContext(
                thread.id, run.id, ws, PlanService(plans), task_dispatcher=dispatcher
            )
            for role, description, todo in [
                ("invalid", "goal", None),
                ("general", "x" * 1001, None),
                ("general", "goal", "missing"),
            ]:
                with pytest.raises(PlanError):
                    await dispatcher.dispatch(ctx, role, description, todo)
            with pytest.raises(PlanError):
                await dispatcher.dispatch(None, "general", "goal")
            assert await plans.list_subtasks(run.id) == []

    asyncio.run(scenario())
    assert set(task.tool_call_schema.model_json_schema()["properties"]) == {
        "agent_type",
        "description",
        "todo_id",
    }


def test_four_calls_including_failures_and_sql_survives_event_failure(tmp_path):
    """限额包含失败；SSE故障不反转已提交任务状态。"""

    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            count = 0

            def factory():
                nonlocal count
                count += 1
                return ScriptedModel(responses=[AIMessage(content="")])

            async def bad_sink(kind, payload):
                raise RuntimeError("synthetic unavailable")

            dispatcher = TaskDispatcher(plans, factory)
            ctx = AgentRunContext(thread.id, run.id, ws, PlanService(plans), bad_sink, dispatcher)
            for _ in range(4):
                assert (await dispatcher.dispatch(ctx, "general", "goal")).status == "FAILED"
            with pytest.raises(PlanError, match="SUBTASK_LIMIT"):
                await dispatcher.dispatch(ctx, "general", "fifth")
            assert count == 4 and len(await plans.list_subtasks(run.id)) == 4
            await dispatcher.registry.close_run(run.id)

    asyncio.run(scenario())


def test_parent_permission_intersection_and_forged_tool_args(tmp_path, monkeypatch):
    async def scenario():
        from minideerflow.agents.subagents import executor

        original = executor.create_agent

        def capture(model, tools, **kwargs):
            assert {t.name for t in tools} == {"list_files"}
            return original(model, tools, **kwargs)

        monkeypatch.setattr(executor, "create_agent", capture)
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            dispatcher = TaskDispatcher(
                plans, lambda: ScriptedModel(responses=[AIMessage(content="ok")])
            )
            ctx = AgentRunContext(
                thread.id,
                run.id,
                ws,
                PlanService(plans),
                task_dispatcher=dispatcher,
                allowed_tools=("list_files",),
            )
            assert (await dispatcher.dispatch(ctx, "general", "goal")).status == "COMPLETED"
            parent = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "forged",
                                "name": "task",
                                "args": {
                                    "agent_type": "general",
                                    "description": "goal",
                                    "thread_id": thread.id,
                                },
                            }
                        ],
                    ),
                    AIMessage(content="rejected"),
                ]
            )
            async with open_checkpointer(tmp_path / "parent.db") as saver:
                graph = build_lead_agent(parent, [task], saver, context_schema=AgentRunContext)
                result = await stream_agent(graph, thread.id, "test", context=ctx)
                assert not result.tool_calls[0].ok
            assert len(await plans.list_subtasks(run.id)) == 1

    asyncio.run(scenario())
