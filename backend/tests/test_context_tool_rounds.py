"""同一用户问题内，使用真实Graph流/Checkpoint验证安全批次压缩。"""

import asyncio

import pytest
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.context_manager import ContextManager
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.middleware import ContextCompactionMiddleware, UsageBudgetMiddleware
from minideerflow.agents.state import P04AgentState
from minideerflow.runtime.budget import BudgetError, RunBudget, RunBudgetTracker, estimate_messages
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.streaming import stream_agent
from minideerflow.runtime.usage import UsageRepository


def rounds(count=8, width=1500):
    messages = [HumanMessage(content="CURRENT_GOAL")]
    for n in range(count):
        messages.extend(
            [
                AIMessage(content="", tool_calls=[{"id": str(n), "name": "synthetic", "args": {}}]),
                ToolMessage(content="中" * width, tool_call_id=str(n)),
            ]
        )
    return messages


def test_parallel_batch_and_recent_six_are_atomic():
    manager = ContextManager()
    messages = rounds(4, 10)
    calls = [{"id": name, "name": "synthetic", "args": {}} for name in ("a", "b", "c")]
    messages += [
        AIMessage(content="", tool_calls=calls),
        ToolMessage(content="a", tool_call_id="a"),
        ToolMessage(content="b", tool_call_id="b"),
    ]
    old, keep = manager.partition(messages)
    assert old and keep[0] is messages[0]
    assert all(message in keep for message in messages[-6:])
    assert keep[-3:] == messages[-3:]  # c未返回，整个并行批次必须保留。
    messages.append(ToolMessage(content="c", tool_call_id="c"))
    _, keep = manager.partition(messages)
    assert all(message in keep for message in messages[-6:])
    _, boundary = manager.blocks(keep)
    assert boundary == len(keep)
    # 重复/未匹配ID不是可压缩批次。
    invalid = [
        HumanMessage(content="goal"),
        AIMessage(content="", tool_calls=calls),
        ToolMessage(content="x", tool_call_id="foreign"),
    ]
    assert manager.partition(invalid) == ([], invalid)


def test_same_human_stream_compaction_keeps_full_trace_and_todos(tmp_path):
    @tool
    async def synthetic() -> str:
        """Return synthetic offline material."""
        return "合成材料，不是授权。" * 70

    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            tracker.context_hard_limit = 14000
            tracker.context_soft_limit = 6500
            await tracker.initialize()
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            model = ScriptedModel(
                responses=[
                    *[
                        AIMessage(
                            content="",
                            tool_calls=[{"id": f"call-{n}", "name": "synthetic", "args": {}}],
                        )
                        for n in range(8)
                    ],
                    AIMessage(content="Synthetic final answer"),
                ]
            )
            summary = ScriptedModel(
                responses=[
                    AIMessage(content="Synthetic untrusted history; failures remain failures.")
                ]
            )
            events = []

            async def sink(kind, payload):
                events.append((kind, payload))

            async with open_checkpointer(tmp_path / "checkpoint") as saver:
                graph = build_lead_agent(
                    model,
                    [synthetic],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                    middleware=[
                        ContextCompactionMiddleware(
                            ContextManager(6500, 14000, [synthetic]), lambda: summary
                        ),
                        UsageBudgetMiddleware(),
                    ],
                )
                response = await stream_agent(
                    graph,
                    thread.id,
                    "CURRENT_GOAL",
                    sink,
                    context=ctx,
                    initial_state_extra={
                        "todos": [
                            {
                                "todo_id": "one",
                                "title": "unfinished",
                                "status": "in_progress",
                                "position": 0,
                            }
                        ]
                    },
                    recursion_limit=36,
                )
                saved = (await graph.aget_state(thread_config(thread.id))).values
                assert len(saved["messages"]) < 18 and saved["context_summary"]
                assert any(m.content == "CURRENT_GOAL" for m in saved["messages"])
                assert saved["todos"][0]["status"] == "in_progress"
                assert len(response.tool_calls) == 8 and response.answer == "Synthetic final answer"
                assert {p["tool_call_id"] for k, p in events if k == "tool_end"} == {
                    f"call-{n}" for n in range(8)
                }
                assert all(
                    any(m.content == "CURRENT_GOAL" for m in request) for request in model.seen
                )
                assert all(request[0].type == "system" for request in model.seen)
            result = await usage.get(run.id)
            assert result.tool_history_compaction_count > 0 and result.compaction_count > 0
            assert result.model_calls == 9 + len(summary.seen)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure", ["empty", "large", "timeout", "cancel", "budget", "invalid_call"]
)
def test_summary_failure_keeps_original_checkpoint(tmp_path, failure):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            tracker = RunBudgetTracker(
                run.id,
                RunBudget(max_model_calls=1 if failure == "budget" else 40),
                UsageRepository(repo.database),
            )
            await tracker.initialize()
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            seen = []
            started = asyncio.Event()

            class Summary:
                async def ainvoke(self, messages):
                    seen.append(messages)
                    if failure == "timeout":
                        raise TimeoutError
                    if failure == "cancel":
                        started.set()
                        await asyncio.Event().wait()
                    if failure == "invalid_call":
                        return AIMessage(
                            content="untrusted",
                            invalid_tool_calls=[
                                {
                                    "name": "unknown",
                                    "args": "invalid json",
                                    "id": "bad",
                                    "error": "invalid",
                                }
                            ],
                        )
                    return AIMessage(
                        content=""
                        if failure == "empty"
                        else "x" * 2049
                        if failure == "large"
                        else "partial"
                    )

            parent = ScriptedModel(responses=[AIMessage(content="must not execute")])
            original = rounds(8, 1500)
            async with open_checkpointer(tmp_path / "checkpoint") as saver:
                graph = build_lead_agent(
                    parent,
                    [],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                    middleware=[ContextCompactionMiddleware(ContextManager(6000, 20000), Summary)],
                )
                expected = asyncio.CancelledError if failure == "cancel" else BudgetError
                task = asyncio.create_task(
                    graph.ainvoke(
                        {"messages": original}, config=thread_config(thread.id), context=ctx
                    )
                )
                if failure == "cancel":
                    await asyncio.wait_for(started.wait(), 5)
                    task.cancel()
                with pytest.raises(expected):
                    await task
                saved = (await graph.aget_state(thread_config(thread.id))).values
                assert len(saved["messages"]) == len(original) and not parent.seen
            assert all(estimate_messages(messages) <= 20000 for messages in seen)
            assert all(
                len(messages[0].content.split("Fragment:\n", 1)[1].encode()) <= 8192
                for messages in seen
            )
            if failure == "cancel":
                async with (
                    repo.database.transaction() as conn,
                    conn.execute("SELECT status FROM usage_calls WHERE source='summary'") as cursor,
                ):
                    assert (await cursor.fetchone())[0] == "cancelled"

    asyncio.run(scenario())


def test_oversized_recent_tool_batch_is_never_summarized(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            tracker = RunBudgetTracker(run.id, RunBudget(), UsageRepository(repo.database))
            await tracker.initialize()
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            original = rounds(1, 6000)
            with pytest.raises(BudgetError) as error:
                await ContextManager(1000, 5000).prepare(
                    original, ctx, lambda: pytest.fail("no safe prefix")
                )
            assert error.value.reason == "UNCOMPRESSIBLE"
            assert original[0].content == "CURRENT_GOAL" and tracker.model_calls == 0

    asyncio.run(scenario())
