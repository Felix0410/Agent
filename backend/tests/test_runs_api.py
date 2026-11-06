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


def parse_events(text):
    import json

    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_sse_frame_replay_cursor_and_preflight(monkeypatch):
    monkeypatch.setattr(runner, "build_chat_model", fake_factory)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        accepted = client.post(f"/api/threads/{thread}/runs", json={"message": "hello"}).json()
        drain(client, app)
        run_id = accepted["run_id"]
        response = client.get(f"/api/runs/{run_id}/events")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        events = parse_events(response.text)
        assert events[0]["type"] == "run_start" and events[-1]["type"] == "run_end"
        assert all(e["run_id"] == run_id for e in events)
        assert [e["event_id"] for e in events] == [f"{run_id}:{i + 1}" for i in range(len(events))]
        cursor = events[0]["event_id"]
        replay = parse_events(
            client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": cursor}).text
        )
        assert replay == events[1:]
        assert (
            client.get(
                f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "wrong:1"}
            ).status_code
            == 422
        )
        assert client.get("/api/runs/missing/events").status_code == 404
        app.state.events._clock = lambda: float("inf")
        expired = client.get(f"/api/runs/{run_id}/events")
        assert expired.status_code == 410
        assert expired.json()["detail"]["code"] == "EVENT_STREAM_EXPIRED"
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "SUCCEEDED"


@pytest.mark.parametrize("fail", [False, True])
def test_terminal_event_only_after_database_commit(monkeypatch, fail):
    monkeypatch.setattr(runner, "build_chat_model", fake_factory)
    if fail:

        async def broken(*args, **kwargs):
            raise RuntimeError("private-secret")

        monkeypatch.setattr(runner, "stream_agent", broken)
    app = create_app()
    with TestClient(app) as client:
        original = app.state.events.publish
        observed = []

        async def checked(run_id, kind, payload):
            if kind == "run_end":
                saved = await app.state.repository.get_run(run_id)
                assert saved.status.value == payload["status"]
                observed.append(payload["status"])
            return await original(run_id, kind, payload)

        app.state.events.publish = checked
        thread = client.post("/api/threads", json={}).json()["id"]
        accepted = client.post(f"/api/threads/{thread}/runs", json={"message": "test"}).json()
        drain(client, app)
        events = parse_events(client.get("/api/runs/" + accepted["run_id"] + "/events").text)
        assert observed == ["FAILED" if fail else "SUCCEEDED"]
        assert events[-1]["payload"]["status"] == observed[0]
        assert "private-secret" not in str(events)


def test_restart_restores_history_checkpoint_and_isolation(monkeypatch):
    models = []

    def factory(settings):
        model = fake_factory(settings)
        models.append(model)
        return model

    monkeypatch.setattr(runner, "build_chat_model", factory)
    first_app = create_app()
    with TestClient(first_app) as client:
        thread = client.post("/api/threads", json={"title": "persistent"}).json()["id"]
        ids = []
        for message in ["remember", "continue"]:
            accepted = client.post(f"/api/threads/{thread}/runs", json={"message": message}).json()
            ids.append(accepted["run_id"])
            drain(client, first_app)
        assert [m.content for m in models[-1].seen[0]][1:] == ["remember", "answer", "continue"]
        workers = list(first_app.state.runner._workers)
    assert first_app.state.database._closed and all(task.done() for task in workers)
    second_app = create_app()
    with TestClient(second_app) as client:
        assert client.get("/api/threads").json()[0]["id"] == thread
        assert [r["id"] for r in client.get(f"/api/threads/{thread}/runs").json()] == ids
        assert client.get(f"/api/runs/{ids[0]}/events").status_code == 410
        accepted = client.post(
            f"/api/threads/{thread}/runs", json={"message": "after restart"}
        ).json()
        drain(client, second_app)
        assert [m.content for m in models[-1].seen[0]][1:] == [
            "remember",
            "answer",
            "continue",
            "answer",
            "after restart",
        ]
        other = client.post("/api/threads", json={}).json()["id"]
        client.post(f"/api/threads/{other}/runs", json={"message": "independent"})
        drain(client, second_app)
        assert [m.content for m in models[-1].seen[0]][1:] == ["independent"]
        assert client.get("/health").json() == {"status": "ok"}
        assert client.post("/api/demo/calculate", json={"expression": "(12+8)*3"}).json() == {
            "result": "60"
        }


def test_restart_orphans_block_only_affected_threads(monkeypatch):
    from minideerflow.runtime.models import RunStatus

    monkeypatch.setattr(runner, "build_chat_model", fake_factory)
    app = create_app()
    with TestClient(app) as client:
        ids = [client.post("/api/threads", json={}).json()["id"] for _ in range(3)]
        created = client.portal.call(app.state.repository.create_run, ids[0], "queued before crash")
        running = client.portal.call(
            app.state.repository.create_run, ids[1], "running before crash"
        )
        client.portal.call(
            app.state.repository.transition_run, running.id, RunStatus.CREATED, RunStatus.RUNNING
        )
    # 没入内存队列的遗留记录模拟崩溃；正常 shutdown 不应伪称它们执行过。
    restarted = create_app()
    with TestClient(restarted) as client:
        for thread, run in zip(ids[:2], [created, running]):
            saved = client.get("/api/runs/" + run.id).json()
            assert saved["status"] == "FAILED" and saved["error_code"] == "RUN_INTERRUPTED"
            response = client.post(f"/api/threads/{thread}/runs", json={"message": "unsafe replay"})
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "THREAD_REQUIRES_RECOVERY"
        response = client.post(f"/api/threads/{ids[2]}/runs", json={"message": "healthy"})
        assert response.status_code == 202
        drain(client, restarted)


def test_tool_checkpoint_partial_failure_requires_recovery(monkeypatch):
    from langchain_core.messages import AIMessage, ToolMessage
    from test_lead import ScriptedModel

    from minideerflow.runtime.checkpoints import thread_config

    class BrokenAfterTool(ScriptedModel):
        def _generate(self, messages, *args, **kwargs):
            if any(isinstance(m, ToolMessage) for m in messages):
                raise RuntimeError("private-secret")
            return super()._generate(messages, *args, **kwargs)

    def factory(settings):
        return BrokenAfterTool(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "partial-call",
                            "name": "calculate",
                            "args": {"expression": "1+1"},
                        }
                    ],
                )
            ]
        )

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        accepted = client.post(
            f"/api/threads/{thread}/runs", json={"message": "fail after tool"}
        ).json()
        drain(client, app)
        saved = client.get("/api/runs/" + accepted["run_id"]).json()
        assert saved["status"] == "FAILED" and saved["answer"] is None
        events = parse_events(client.get("/api/runs/" + accepted["run_id"] + "/events").text)
        assert any(e["type"] == "tool_end" and e["payload"]["result"] == "2" for e in events)
        checkpoint = client.portal.call(app.state.checkpointer.aget_tuple, thread_config(thread))
        assert any(
            isinstance(m, ToolMessage) for m in checkpoint.checkpoint["channel_values"]["messages"]
        )
        assert (
            client.post(f"/api/threads/{thread}/runs", json={"message": "do not rerun"}).status_code
            == 409
        )
