"""取消的SQL/CAS/队列/worker/旧库迁移真实验证。"""

import asyncio
import threading

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.main import create_app
from minideerflow.runtime import runner
from minideerflow.runtime.models import RunStatus
from minideerflow.runtime.repository import RepositoryError


def test_queued_cancel_never_enters_graph_and_worker_survives(monkeypatch):
    gate = threading.Event()
    original = runner.stream_agent
    seen = []

    async def controlled(agent, thread_id, *args, **kwargs):
        seen.append(thread_id)
        while not gate.is_set():
            await asyncio.sleep(0.002)
        return await original(agent, thread_id, *args, **kwargs)

    monkeypatch.setattr(runner, "stream_agent", controlled)
    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ScriptedModel(responses=[AIMessage(content="done")]),
    )
    app = create_app()
    with TestClient(app) as client:
        threads = [client.post("/api/threads", json={}).json()["id"] for _ in range(3)]
        ids = [
            client.post(f"/api/threads/{t}/runs", json={"message": "hello"}).json()["run_id"]
            for t in threads
        ]
        response = client.post("/api/runs/" + ids[2] + "/cancel")
        assert response.status_code == 202 and response.json()["status"] == "CANCELLED"
        stamp = response.json()["cancel_requested_at"]
        assert client.post("/api/runs/" + ids[2] + "/cancel").status_code == 200
        assert client.get("/api/runs/" + ids[2]).json()["cancel_requested_at"] == stamp
        gate.set()
        drain(client, app)
        assert threads[2] not in seen
        assert client.get("/api/runs/" + ids[0]).json()["status"] == "SUCCEEDED"
        assert not next(t for t in client.get("/api/threads").json() if t["id"] == threads[2])[
            "needs_recovery"
        ]
        assert client.post("/api/runs/missing/cancel").status_code == 404


def test_running_cancel_only_one_run_and_usage_persists(monkeypatch):
    entered = threading.Event()
    released = threading.Event()
    original = runner.stream_agent

    async def controlled(agent, thread_id, message, *args, **kwargs):
        if message == "slow":
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()
        return await original(agent, thread_id, message, *args, **kwargs)

    monkeypatch.setattr(runner, "stream_agent", controlled)
    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ScriptedModel(responses=[AIMessage(content="done")]),
    )
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "slow"}).json()["run_id"]
        assert entered.wait(1)
        response = client.post("/api/runs/" + rid + "/cancel")
        assert response.status_code == 202 and response.json()["status"] == "RUNNING"
        drain(client, app)
        assert released.is_set() and client.get("/api/runs/" + rid).json()["status"] == "CANCELLED"
        assert (
            not app.state.cancellation.active
            if hasattr(app.state, "cancellation")
            else not app.state.runner.cancellation.active
        )
        fresh = client.post("/api/threads", json={}).json()["id"]
        nextid = client.post(f"/api/threads/{fresh}/runs", json={"message": "fast"}).json()[
            "run_id"
        ]
        drain(client, app)
        assert client.get("/api/runs/" + nextid).json()["status"] == "SUCCEEDED"


def test_cancel_first_prevents_success_cas_and_register_gap(monkeypatch):
    app = create_app()
    with TestClient(app) as client:

        async def scenario():
            repo = app.state.repository
            thread = await repo.create_thread()
            run = await repo.create_run(thread.id, "race")
            await repo.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            await repo.request_cancel(run.id)
            try:
                await repo.complete_run(run.id, status=RunStatus.SUCCEEDED, answer="late")
            except RepositoryError as exc:
                assert exc.code == "RUN_CANCEL_REQUESTED"
            else:
                raise AssertionError("cancelled run succeeded")
            from minideerflow.runtime.budget import RunBudget, RunBudgetTracker

            tracker = RunBudgetTracker(run.id, RunBudget(), app.state.runner.usage)
            await tracker.initialize()
            try:
                await app.state.runner.cancellation.register(
                    run.id, asyncio.current_task(), tracker
                )
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("early cancel lost")
            app.state.runner.cancellation.unregister(run.id)
            await repo.complete_cancel(run.id, True)
            assert (await repo.get_thread(thread.id)).needs_recovery

        client.portal.call(scenario)


def test_old_database_migration_is_idempotent(tmp_path):
    import sqlite3

    from minideerflow.runtime.db import SCHEMA, RuntimeDatabase

    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.close()

    async def scenario():
        db = await RuntimeDatabase.open(path)
        try:
            await db.init_schema()
            await db.init_schema()
            async with db.connection.execute("PRAGMA table_info(runs)") as cur:
                assert [r["name"] for r in await cur.fetchall()].count("cancel_requested_at") == 1
        finally:
            await db.close()

    asyncio.run(scenario())


def test_cancel_waits_real_child_graph_and_stops_future_models(monkeypatch):
    entered = threading.Event()
    exited = threading.Event()
    count = 0

    class Slow(ScriptedModel):
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            self.seen.append(list(messages))
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()

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
                                "id": "task",
                                "name": "task",
                                "args": {"agent_type": "general", "description": "wait"},
                            }
                        ],
                    ),
                    AIMessage(content="must not run"),
                ]
            )
        return Slow(responses=[AIMessage(content="never")])

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "delegate"}).json()["run_id"]
        assert entered.wait(2)
        assert client.post("/api/runs/" + rid + "/cancel").status_code == 202
        drain(client, app)
        assert exited.is_set() and client.get("/api/runs/" + rid).json()["status"] == "CANCELLED"
        assert client.get(f"/api/runs/{rid}/subtasks").json()[0]["status"] == "CANCELLED"
        assert client.get(f"/api/runs/{rid}/usage").json()["model_calls"] == 2
        assert not app.state.runner.cancellation.active and not app.state.task_registry._runs
        assert client.get("/api/threads").json()[0]["needs_recovery"]


def test_cancel_after_write_started_marks_unknown_preserves_artifact(monkeypatch):
    entered = threading.Event()
    models = []

    def factory(settings):
        model = ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "write",
                            "name": "write_text",
                            "args": {
                                "filename": "summary.md",
                                "content": "committed synthetic evidence",
                            },
                        }
                    ],
                ),
                AIMessage(content="must not retry"),
            ]
        )
        models.append(model)
        return model

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        original = app.state.workspace.write_text

        async def uncertain(*args, **kwargs):
            await original(*args, **kwargs)
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(app.state.workspace, "write_text", uncertain)
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "write"}).json()["run_id"]
        assert entered.wait(2)
        client.post("/api/runs/" + rid + "/cancel")
        drain(client, app)
        result = client.get("/api/runs/" + rid).json()
        assert result["status"] == "FAILED" and result["error_code"] == "OUTCOME_UNKNOWN"
        assert len(models[-1].seen) == 1
        artifact = client.get(f"/api/threads/{tid}/artifacts").json()[0]
        assert (
            client.get(
                "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": tid}
            ).content
            == b"committed synthetic evidence"
        )
