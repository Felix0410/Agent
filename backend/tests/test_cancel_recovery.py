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
    conn.executescript(SCHEMA.split("CREATE TABLE IF NOT EXISTS run_usage")[0])
    conn.execute(
        "INSERT INTO threads(id,title,created_at,updated_at) VALUES('old-thread','old','2026-01-01','2026-01-01')"
    )
    conn.execute(
        "INSERT INTO runs(id,thread_id,input_message,status,answer,created_at,finished_at) VALUES('old-run','old-thread','old input','SUCCEEDED','old answer','2026-01-01','2026-01-01')"
    )
    conn.commit()
    conn.close()

    async def scenario():
        db = await RuntimeDatabase.open(path)
        try:
            await db.init_schema()
            await db.init_schema()
            from minideerflow.runtime.repository import RuntimeRepository

            assert (await RuntimeRepository(db).get_run("old-run")).answer == "old answer"
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


def test_cancel_before_graph_registration_has_no_provider_call(monkeypatch):
    from minideerflow.runtime.cancellation import RunCancellationRegistry

    entered = threading.Event()
    release = threading.Event()
    models = []
    original = RunCancellationRegistry.register

    async def delayed(self, *args):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.001)
        return await original(self, *args)

    monkeypatch.setattr(RunCancellationRegistry, "register", delayed)

    def factory(settings):
        model = ScriptedModel(responses=[AIMessage(content="must not run")])
        models.append(model)
        return model

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "race"}).json()["run_id"]
        assert entered.wait(1)
        client.post("/api/runs/" + rid + "/cancel")
        release.set()
        drain(client, app)
        assert client.get("/api/runs/" + rid).json()["status"] == "CANCELLED"
        assert not any(model.seen for model in models)
        assert client.get(f"/api/runs/{rid}/usage").json()["model_calls"] == 0


def test_success_wins_before_cancel_is_not_retracted(monkeypatch):
    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ScriptedModel(responses=[AIMessage(content="done")]),
    )
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "hi"}).json()["run_id"]
        drain(client, app)
        for _ in range(2):
            result = client.post("/api/runs/" + rid + "/cancel")
            assert (
                result.status_code == 200
                and result.json()["status"] == "SUCCEEDED"
                and result.json()["cancel_requested_at"] is None
            )


def test_cancel_in_local_mcp_dispatch_never_retries(monkeypatch, tmp_path):
    from test_mcp import approved_config, mcp_server

    from minideerflow.config import get_settings

    script = """
import sys,asyncio
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
server=FastMCP('slow-test',host='127.0.0.1',port=int(sys.argv[1]),stateless_http=True,json_response=True,log_level='WARNING')
@server.tool(structured_output=False,annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False))
async def lookup_fact(topic:str)->str:
    await asyncio.sleep(5)
    return 'fixed synthetic fact'
server.run(transport='streamable-http')
"""
    with mcp_server(script) as (_, port):
        path, _ = asyncio.run(approved_config(tmp_path, port))
        monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
        get_settings.cache_clear()
        monkeypatch.setattr(
            runner,
            "build_chat_model",
            lambda settings: ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": "mcp", "name": "mcp_demo_lookup_fact", "args": {"topic": "test"}}
                        ],
                    ),
                    AIMessage(content="must not run"),
                ]
            ),
        )
        app = create_app()
        with TestClient(app) as client:
            tid = client.post("/api/threads", json={}).json()["id"]
            rid = client.post(f"/api/threads/{tid}/runs", json={"message": "slow MCP"}).json()[
                "run_id"
            ]

            async def in_flight():
                async with asyncio.timeout(2):
                    while (await app.state.runner.usage.get(rid)).tool_calls != 1:
                        await asyncio.sleep(0.001)
                await asyncio.sleep(0.05)

            client.portal.call(in_flight)
            client.post("/api/runs/" + rid + "/cancel")
            drain(client, app)
            assert client.get("/api/runs/" + rid).json()["status"] == "CANCELLED"
            usage = client.get(f"/api/runs/{rid}/usage").json()
            assert usage["model_calls"] == 1 and usage["tool_calls"] == 1


def test_cancel_notification_failure_does_not_lose_signal(monkeypatch):
    entered = threading.Event()

    async def slow(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "stream_agent", slow)
    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ScriptedModel(responses=[AIMessage(content="never")]),
    )
    app = create_app()
    with TestClient(app) as client:
        original_publish = app.state.events.publish

        async def publish(run_id, kind, payload):
            if kind == "run_cancel_requested":
                raise RuntimeError("synthetic transport failure")
            return await original_publish(run_id, kind, payload)

        monkeypatch.setattr(app.state.events, "publish", publish)
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "slow"}).json()["run_id"]
        assert entered.wait(1)
        assert client.post("/api/runs/" + rid + "/cancel").status_code == 202
        drain(client, app)
        assert client.get("/api/runs/" + rid).json()["status"] == "CANCELLED"


def test_cancel_marker_blocks_new_subtask_in_same_sql_transaction():
    app = create_app()
    with TestClient(app) as client:

        async def scenario():
            import pytest

            from minideerflow.runtime.plan_repository import PlanError

            repo = app.state.repository
            thread = await repo.create_thread()
            run = await repo.create_run(thread.id, "manual race")
            await repo.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            await repo.request_cancel(run.id)
            with pytest.raises(PlanError):
                await app.state.plans.create_subtask(run.id, thread.id, "general", "must not start")
            assert await app.state.plans.list_subtasks(run.id) == []
            await repo.complete_cancel(run.id)

        client.portal.call(scenario)


def test_cancel_one_child_run_keeps_parallel_run_running(monkeypatch):
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    entered = threading.Event()
    exited = threading.Event()

    class Routed(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            if "Complete only the delegated goal" in str(messages[0].content):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    exited.set()
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            user = next(m for m in reversed(messages) if isinstance(m, HumanMessage))
            if user.content == "delegate" and not isinstance(messages[-1], ToolMessage):
                answer = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "task",
                            "name": "task",
                            "args": {"agent_type": "general", "description": "wait"},
                        }
                    ],
                )
            else:
                answer = AIMessage(content="independent done")
            return ChatResult(generations=[ChatGeneration(message=answer)])

    monkeypatch.setattr(
        runner, "build_chat_model", lambda settings: Routed(responses=[AIMessage(content="unused")])
    )
    app = create_app()
    with TestClient(app) as client:
        # 1. 第一Run进入真正child图并阻塞，第二Run独立提交到另一个worker。
        first = client.post("/api/threads", json={}).json()["id"]
        a = client.post(f"/api/threads/{first}/runs", json={"message": "delegate"}).json()["run_id"]
        assert entered.wait(2)
        second = client.post("/api/threads", json={}).json()["id"]
        b = client.post(f"/api/threads/{second}/runs", json={"message": "independent"}).json()[
            "run_id"
        ]

        async def second_done():
            async with asyncio.timeout(2):
                while (await app.state.repository.get_run(b)).status != RunStatus.SUCCEEDED:
                    await asyncio.sleep(0.001)

        client.portal.call(second_done)
        assert client.get("/api/runs/" + a).json()["status"] == "RUNNING"
        # 2. 取消只影响第一Run及其child，第二Run不需等取消才完成。
        client.post("/api/runs/" + a + "/cancel")
        drain(client, app)
        assert exited.is_set() and client.get("/api/runs/" + a).json()["status"] == "CANCELLED"
        assert client.get("/api/runs/" + b).json()["status"] == "SUCCEEDED"
        # 3. 用量与任务归属各自Run，清理没有遗留活动句柄。
        assert client.get(f"/api/runs/{a}/usage").json()["model_calls"] == 2
        assert client.get(f"/api/runs/{b}/usage").json()["model_calls"] == 1
        assert not app.state.task_registry._runs and not app.state.runner.cancellation.active


def test_unconfirmed_write_exception_cannot_become_success(monkeypatch):
    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "write",
                            "name": "write_text",
                            "args": {"filename": "summary.md", "content": "known stored bytes"},
                        }
                    ],
                ),
                AIMessage(content="explain partial failure"),
            ]
        ),
    )
    app = create_app()
    with TestClient(app) as client:
        original = app.state.workspace.write_text

        async def lost_ack(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError("synthetic lost acknowledgement")

        monkeypatch.setattr(app.state.workspace, "write_text", lost_ack)
        # 文件工具自身会脱敏未知异常；这里让Guard看到真正未确认的异常边界。
        from langchain.tools import ToolRuntime, tool

        from minideerflow.agents.context import AgentRunContext

        @tool("unconfirmed_write")
        async def unconfirmed_write(runtime: ToolRuntime[AgentRunContext]) -> str:
            """Write a synthetic file and lose the acknowledgement."""
            await runtime.context.workspace_service.write_text(
                runtime.context.thread_id,
                runtime.context.run_id,
                "summary.md",
                "known stored bytes",
            )
            return "unreachable"

        from minideerflow.tools.registry import ToolDefinition, ToolRegistry, register_builtin_tools

        registry = ToolRegistry()
        register_builtin_tools(registry)
        registry.register(
            ToolDefinition(
                "unconfirmed_write", unconfirmed_write, "builtin", "write", 5, "builtin", "test"
            )
        )
        registry.freeze()
        app.state.runner.tool_registry = registry
        app.state.runner.model_factory = lambda settings: ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"id": "write", "name": "unconfirmed_write", "args": {}}],
                ),
                AIMessage(content="explain partial failure"),
            ]
        )
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "write"}).json()["run_id"]
        drain(client, app)
        result = client.get("/api/runs/" + rid).json()
        assert result["status"] == "FAILED" and result["error_code"] == "OUTCOME_UNKNOWN"
        assert len(client.get(f"/api/threads/{tid}/artifacts").json()) == 1
