"""Run HTTP 的局部验证：后台 Fake 模型与真实临时数据库。"""

import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from test_runner import fake_factory

from minideerflow.main import create_app
from minideerflow.runtime import runner


def drain(client, app):
    async def wait():
        await asyncio.wait_for(app.state.runner.queue.join(), 3)

    client.portal.call(wait)


def test_202_does_not_wait_for_model_and_busy(monkeypatch):
    monkeypatch.setattr(runner, "build_chat_model", fake_factory)
    original = runner.stream_agent
    gate = threading.Event()

    async def slow(*args, **kwargs):
        while not gate.is_set():
            await asyncio.sleep(0.005)
        return await original(*args, **kwargs)

    monkeypatch.setattr(runner, "stream_agent", slow)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        response = client.post(f"/api/threads/{thread}/runs", json={"message": "hello"})
        assert response.status_code == 202
        accepted = response.json()
        assert accepted["status"] == "CREATED"
        run = client.get("/api/runs/" + accepted["run_id"]).json()
        assert run["status"] in ["CREATED", "RUNNING"] and not gate.is_set()
        duplicate = client.post(f"/api/threads/{thread}/runs", json={"message": "duplicate"})
        assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "THREAD_BUSY"
        gate.set()
        drain(client, app)
        final = client.get("/api/runs/" + accepted["run_id"]).json()
        assert final["status"] == "SUCCEEDED" and final["answer"] == "answer"
        assert client.get(f"/api/threads/{thread}/runs").json()[0]["id"] == accepted["run_id"]


def test_missing_config_and_unknown_ids():
    with TestClient(create_app()) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        response = client.post(f"/api/threads/{thread}/runs", json={"message": "hello"})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "MODEL_NOT_CONFIGURED"
        assert client.get(f"/api/threads/{thread}/runs").json() == []
        response = client.post("/api/threads/missing/runs", json={"message": "hello"})
        assert (
            response.status_code == 404 and response.json()["detail"]["code"] == "THREAD_NOT_FOUND"
        )
        assert client.get("/api/runs/missing").status_code == 404


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001, None, 42])
def test_invalid_message(message):
    with TestClient(create_app()) as client:
        assert (
            client.post("/api/threads/missing/runs", json={"message": message}).status_code == 422
        )


def test_queue_full_api_does_not_create_ghost(monkeypatch):
    monkeypatch.setattr(runner, "build_chat_model", fake_factory)

    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "stream_agent", blocked)
    app = create_app()
    with TestClient(app) as client:
        threads = [client.post("/api/threads", json={}).json()["id"] for _ in range(11)]
        for thread in threads[:10]:
            assert (
                client.post(f"/api/threads/{thread}/runs", json={"message": "queued"}).status_code
                == 202
            )
        response = client.post(f"/api/threads/{threads[-1]}/runs", json={"message": "overflow"})
        assert response.status_code == 429
        assert client.get(f"/api/threads/{threads[-1]}/runs").json() == []
        client.portal.call(app.state.runner.shutdown, 0.01)
