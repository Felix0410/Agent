"""只读历史接口未知 Run 与空计划明确区分。"""

from fastapi.testclient import TestClient
from test_runner import fake_factory
from test_runs_api import drain

from minideerflow.main import create_app
from minideerflow.runtime import runner


def test_history_empty_and_unknown(monkeypatch):
    monkeypatch.setattr(runner, "build_chat_model", fake_factory)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        run = client.post(f"/api/threads/{thread}/runs", json={"message": "hello"}).json()["run_id"]
        drain(client, app)
        for suffix in ["todos", "subtasks"]:
            assert client.get(f"/api/runs/{run}/{suffix}").json() == []
            assert client.get(f"/api/runs/missing/{suffix}").status_code == 404
            assert client.post(f"/api/runs/{run}/{suffix}", json={}).status_code == 405
