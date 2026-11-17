"""官方摘要的真实Graph/Checkpoint/流式/观察用量兼容性。"""

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.agents.middleware import ModelUsageMiddleware
from minideerflow.agents.state import P04AgentState
from minideerflow.agents.summarization import ObservedSummarizationMiddleware, SummarizationError
from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config
from minideerflow.runtime.streaming import stream_agent
from minideerflow.runtime.usage import UsageRepository


def assert_tool_pairs(messages):
    """验证模型真正收到的上下文，不以Fake模型接受孤立ToolMessage冒充兼容。"""
    pending = set()
    for message in messages:
        if isinstance(message, AIMessage):
            pending.update(call["id"] for call in message.tool_calls)
        elif isinstance(message, ToolMessage):
            assert message.tool_call_id in pending
            pending.remove(message.tool_call_id)
    assert not pending


def test_unknown_window_defaults_and_disabled_mode():
    from minideerflow.agents.summarization import summarization_middleware, summary_configuration
    from minideerflow.config import Settings

    config = summary_configuration(Settings())
    assert config["confirmed_model_window"] is None
    assert config["estimate_unit"] == "langchain_approximate_tokens"
    known = summary_configuration(Settings(model_context_window_tokens=1000))
    assert known["trigger_tokens"] < 1000 and known["trim_tokens"] < 1000
    assert summarization_middleware(None, Settings(summarization_enabled=False)) == []


@pytest.mark.parametrize(
    "kind,code", [("window", "MODEL_CONTEXT_WINDOW_EXCEEDED"), ("loop", "AGENT_RECURSION_LIMIT")]
)
def test_real_exception_category_is_not_local_byte_budget(monkeypatch, kind, code):
    from fastapi.testclient import TestClient
    from langchain_core.exceptions import ContextOverflowError
    from langgraph.errors import GraphRecursionError
    from test_runs_api import drain

    from minideerflow.main import create_app
    from minideerflow.runtime import runner

    class ErrorModel(ScriptedModel):
        async def _agenerate(self, *args, **kwargs):
            raise (
                ContextOverflowError("synthetic")
                if kind == "window"
                else GraphRecursionError("synthetic")
            )

    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ErrorModel(responses=[AIMessage(content="unused")]),
    )
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        run_id = client.post(f"/api/threads/{thread}/runs", json={"message": "synthetic"}).json()[
            "run_id"
        ]
        drain(client, app)
        result = client.get(f"/api/runs/{run_id}").json()
        assert result["status"] == "FAILED" and result["error_code"] == code


class NativeModel(ScriptedModel):
    summary_mode: str = "ok"

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        summary = not any(m.type == "system" for m in messages)
        if summary and self.summary_mode == "cancel":
            await asyncio.Event().wait()
        reply = AIMessage(
            content=(
                ""
                if self.summary_mode == "empty"
                else "SUMMARY_SENTINEL: original facts remain data"
            )
            if summary
            else "PARENT_FINAL",
            usage_metadata={"input_tokens": 7, "output_tokens": 2, "total_tokens": 9},
        )
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.mark.parametrize("mode", ["ok", "empty", "cancel"])
def test_native_summary_state_and_actual_usage(tmp_path, mode):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            model = NativeModel(responses=[AIMessage(content="unused")], summary_mode=mode)
            history = [
                HumanMessage(
                    content="Old legacy history", additional_kwargs={"context_summary": True}
                )
            ]
            for n in range(5):
                history += [
                    HumanMessage(content=f"old question {n}"),
                    AIMessage(content="old answer"),
                ]
            events = []

            async def sink(kind, payload):
                events.append((kind, payload))

            async with open_checkpointer(tmp_path / "saver") as saver:
                graph = build_lead_agent(
                    model,
                    [],
                    saver,
                    context_schema=AgentRunContext,
                    state_schema=P04AgentState,
                    middleware=[
                        ObservedSummarizationMiddleware(
                            model,
                            trigger=("messages", 5),
                            keep=("messages", 2),
                            trim_tokens_to_summarize=1000,
                        ),
                        ModelUsageMiddleware(),
                    ],
                )
                await graph.aupdate_state(
                    thread_config(thread.id),
                    {
                        "messages": history,
                        "context_summary": "legacy",
                        "todos": [{"todo_id": "a", "status": "in_progress"}],
                    },
                )
                task = asyncio.create_task(
                    stream_agent(
                        graph, thread.id, "NEW_GOAL", sink, context=ctx, recursion_limit=36
                    )
                )
                if mode == "cancel":
                    async with asyncio.timeout(3):
                        while not model.seen:
                            await asyncio.sleep(0.005)
                    task.cancel()
                if mode != "ok":
                    with pytest.raises(
                        asyncio.CancelledError if mode == "cancel" else SummarizationError
                    ):
                        await task
                else:
                    response = await task
                    assert response.answer == "PARENT_FINAL" and response.tool_calls == []
                    assert not any(
                        "SUMMARY_SENTINEL" in str(payload)
                        for kind, payload in events
                        if kind in ("assistant_delta", "assistant_final", "tool_end")
                    )
                saved = (await graph.aget_state(thread_config(thread.id))).values
                assert (
                    saved["todos"][0]["status"] == "in_progress"
                    and saved["context_summary"] == "legacy"
                )
                if mode == "ok":
                    assert len(saved["messages"]) < len(history)
                    assert any(m.content == "NEW_GOAL" for m in saved["messages"])
                    assert saved["messages"][0].additional_kwargs["lc_source"] == "summarization"
                else:
                    assert len(saved["messages"]) == len(history) + 1
            result = await usage.get(run.id)
            assert result.summary_calls == 1
            if mode == "ok":
                assert result.compaction_count == 1 and result.model_calls == 2
                assert result.provider_input_tokens == 14 and result.provider_output_tokens == 4
            elif mode == "cancel":
                assert result.usage_unknown_calls == 1 and result.compaction_count == 0
            else:
                assert result.provider_input_tokens == 7 and result.compaction_count == 0

    asyncio.run(scenario())
