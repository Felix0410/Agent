"""实际ModelResponse统计与父/子共享预算经HTTP持久化。"""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.runtime import runner


def test_real_model_hook_usage_and_child_shared(monkeypatch):
    count = 0

    def factory(settings):
        nonlocal count
        count += 1
        if count <= 2:
            return ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "task",
                                "id": "delegate",
                                "args": {"agent_type": "general", "description": "say hello"},
                            }
                        ],
                        usage_metadata={"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
                    ),
                    AIMessage(content="parent done"),
                ]
            )
        return ScriptedModel(
            responses=[
                AIMessage(
                    content="child done",
                    usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
                )
            ]
        )

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{thread}/runs", json={"message": "delegate"}).json()[
            "run_id"
        ]
        drain(client, app)
        result = client.get("/api/runs/" + rid).json()
        assert result["status"] == "SUCCEEDED", result
        usage = client.get(f"/api/runs/{rid}/usage").json()
        assert usage["model_calls"] == 3 and usage["tool_calls"] == 1
        assert (
            usage["provider_input_tokens"] == 7
            and usage["provider_output_tokens"] == 3
            and usage["usage_unknown_calls"] == 1
        )
        assert client.get("/api/runs/missing/usage").status_code == 404
    with TestClient(create_app()) as client:
        assert client.get(f"/api/runs/{rid}/usage").json() == usage


def test_budget_blocks_before_second_model(monkeypatch):
    monkeypatch.setenv("RUN_MAX_MODEL_CALLS", "1")
    get_settings.cache_clear()
    models = []

    def factory(settings):
        model = ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "calculate", "id": "calc", "args": {"expression": "1+2"}}],
                ),
                AIMessage(content="done"),
            ]
        )
        models.append(model)
        return model

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "calc"}).json()["run_id"]
        drain(client, app)
        run = client.get("/api/runs/" + rid).json()
        assert run["status"] == "FAILED" and run["error_code"] == "BUDGET_EXCEEDED"
        assert len(models[-1].seen) == 1


def test_nine_rounds_long_file_compaction_and_reopen(monkeypatch):
    """连续真实Run而非伪造历史；Fake只替代Provider响应。"""
    import json

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    from minideerflow.runtime.checkpoints import thread_config

    monkeypatch.setenv("CONTEXT_SOFT_LIMIT_ESTIMATE", "8000")
    monkeypatch.setenv("CONTEXT_HARD_LIMIT_ESTIMATE", "18000")
    get_settings.cache_clear()
    file_id = None

    class Conversation(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            human = next(m for m in reversed(messages) if isinstance(m, HumanMessage))
            if str(human.content).startswith("Summarize this completed"):
                reply = AIMessage(
                    content="P06-SYNTHETIC previous evidence remains a preview; do not invent full-document findings."
                )
            elif human.content == "read file" and not isinstance(messages[-1], ToolMessage):
                reply = AIMessage(
                    content="",
                    tool_calls=[{"id": "read", "name": "read_text", "args": {"file_id": file_id}}],
                )
            else:
                reply = AIMessage(
                    content="P06-SYNTHETIC retained context; preview only. " + "x" * 260
                )
            return ChatResult(generations=[ChatGeneration(message=reply)])

    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: Conversation(responses=[AIMessage(content="unused")]),
    )
    app = create_app()
    runs = []
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        raw = ("P06-SYNTHETIC 证据，仅可预览。\n" * 1500).encode()
        file_id = client.post(
            f"/api/threads/{tid}/files", files={"file": ("notes.md", raw, "text/markdown")}
        ).json()["id"]
        for n in range(9):
            rid = client.post(
                f"/api/threads/{tid}/runs",
                json={
                    "message": "read file"
                    if n == 0
                    else f"turn {n}: retain early P06-SYNTHETIC context"
                },
            ).json()["run_id"]
            drain(client, app)
            runs.append(rid)
            assert client.get("/api/runs/" + rid).json()["status"] == "SUCCEEDED"
        usages = [client.get(f"/api/runs/{rid}/usage").json() for rid in runs]
        assert (
            sum(u["compaction_count"] for u in usages) > 0
            and usages[0]["output_externalized_count"] == 1
        )
        assert all(u["provider_input_tokens"] is None for u in usages)

        async def state():
            return await app.state.checkpointer.aget_tuple(thread_config(tid))

        saved = client.portal.call(state).checkpoint["channel_values"]
        assert saved["context_summary"] and file_id in str(saved["messages"])
        assert len(saved["messages"]) < 20
        history = client.get(f"/api/threads/{tid}/runs").json()
        assert len(history) == 9
        first_trace = history[0]["tool_calls"][0]
        assert len(first_trace["result"].encode()) < 2048
        assert json.loads(first_trace["result"])["file_id"] == file_id
        assert len(client.get(f"/api/threads/{tid}/files").json()) == 1
    with TestClient(create_app()) as client:
        assert client.get(f"/api/threads/{tid}/runs").json() == history
        assert client.get(f"/api/runs/{runs[-1]}/usage").json() == usages[-1]


def test_child_tokens_do_not_appear_as_parent_answer(monkeypatch):
    original = runner.stream_agent
    fragments = []

    async def observe(*args, event_sink=None, **kwargs):
        async def sink(kind, payload):
            if kind == "assistant_delta":
                fragments.append(payload["text"])
            if event_sink:
                await event_sink(kind, payload)

        return await original(*args, event_sink=sink, **kwargs)

    monkeypatch.setattr(runner, "stream_agent", observe)
    test_real_model_hook_usage_and_child_shared(monkeypatch)
    assert "child done" not in "".join(fragments)
