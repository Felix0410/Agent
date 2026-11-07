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
