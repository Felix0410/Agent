"""真实Checkpoint摘要后仍保留当前目标、Todo和完整工具组合。"""

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.context_manager import ContextManager
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.middleware import ContextCompactionMiddleware, UsageBudgetMiddleware
from minideerflow.agents.state import P04AgentState
from minideerflow.runtime.budget import BudgetError, RunBudget, RunBudgetTracker
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.usage import UsageRepository


def test_summary_real_state_preserves_current_goal_and_todos(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            context = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            messages = []
            for n in range(9):
                messages.extend(
                    [
                        HumanMessage(content=f"old question {n} " + "x" * 300),
                        AIMessage(content="old answer " + "y" * 300),
                    ]
                )
            messages.append(HumanMessage(content="CURRENT_GOAL_DO_NOT_DELETE"))
            summary = ScriptedModel(
                responses=[
                    AIMessage(content="Old facts retained; missing evidence remains uncertain.")
                ]
            )
            model = ScriptedModel(responses=[AIMessage(content="new answer")])
            async with open_checkpointer(tmp_path / "saver") as saver:
                graph = build_lead_agent(
                    model,
                    [],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                    middleware=[
                        ContextCompactionMiddleware(ContextManager(2000, 18000), lambda: summary),
                        UsageBudgetMiddleware(),
                    ],
                )
                await graph.ainvoke(
                    {
                        "messages": messages,
                        "todos": [
                            {
                                "todo_id": "one",
                                "title": "unfinished",
                                "status": "in_progress",
                                "position": 0,
                            }
                        ],
                    },
                    config=thread_config(thread.id),
                    context=context,
                )
                state = (await graph.aget_state(thread_config(thread.id))).values
                assert len(state["messages"]) < len(
                    messages
                ) and "CURRENT_GOAL_DO_NOT_DELETE" in str(state["messages"])
                assert (
                    state["context_summary"].startswith("Old facts")
                    and state["todos"][0]["status"] == "in_progress"
                )
                assert len(model.seen[0]) < len(messages)
            result = await usage.get(run.id)
            assert result.compaction_count == 1 and result.model_calls == 2

    asyncio.run(scenario())


def test_partition_keeps_incomplete_tools_and_recent_messages():
    manager = ContextManager()
    messages = [
        HumanMessage(content="old"),
        AIMessage(content="done"),
        HumanMessage(content="current"),
        AIMessage(content="", tool_calls=[{"id": "call", "name": "read_text", "args": {}}]),
        ToolMessage(content="text", tool_call_id="call"),
    ]
    old, keep = manager.partition(messages)
    assert old == [] and keep == messages
    assert not manager.complete(messages[2:])


def test_hard_limit_does_not_send_unbounded_summary(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            tracker = RunBudgetTracker(run.id, RunBudget(), UsageRepository(repo.database))
            await tracker.initialize()
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            model = ScriptedModel(responses=[AIMessage(content="summary")])
            with pytest.raises(BudgetError):
                await ContextManager(100, 500).prepare(
                    [HumanMessage(content="x" * 1000)], ctx, lambda: model
                )
            assert model.seen == []

    asyncio.run(scenario())
