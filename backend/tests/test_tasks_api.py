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


def test_parent_timeout_and_shutdown_wait_for_child(monkeypatch):
    """父终态之前 child 真正退出，遗留状态不能误写完成。"""
    import asyncio

    from langchain_core.messages import AIMessage
    from test_lead import ScriptedModel

    from minideerflow.agents.subagents import executor

    class Slow:
        async def ainvoke(self, *args, **kwargs):
            await asyncio.Event().wait()

    monkeypatch.setattr(executor, "create_agent", lambda *a, **k: Slow())

    def factory(settings):
        return ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "delegate",
                            "name": "task",
                            "args": {"agent_type": "general", "description": "wait"},
                        }
                    ],
                ),
                AIMessage(content="done"),
            ]
        )

    monkeypatch.setattr(runner, "build_chat_model", factory)
    for mode in ["timeout", "shutdown"]:
        monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "0.15" if mode == "timeout" else "150")
        from minideerflow.config import get_settings

        get_settings.cache_clear()
        app = create_app()
        with TestClient(app) as client:
            thread = client.post("/api/threads", json={}).json()["id"]
            run = client.post(f"/api/threads/{thread}/runs", json={"message": "delegate"}).json()[
                "run_id"
            ]

            async def wait_started(app=app, run=run):
                async with asyncio.timeout(2):
                    while not any(
                        t.status == "RUNNING" for t in await app.state.plans.list_subtasks(run)
                    ):
                        await asyncio.sleep(0.001)

            client.portal.call(wait_started)
            if mode == "shutdown":
                client.portal.call(app.state.runner.shutdown, 0)
            else:
                drain(client, app)
            result = client.get("/api/runs/" + run).json()
            tasks = client.get(f"/api/runs/{run}/subtasks").json()
            assert result["status"] == "FAILED"
            assert result["error_code"] == (
                "MODEL_TIMEOUT" if mode == "timeout" else "RUN_INTERRUPTED"
            )
            assert tasks[0]["status"] == "CANCELLED"
            assert not app.state.task_registry._runs
            with client.stream("GET", f"/api/runs/{run}/events") as response:
                text = "".join(response.iter_text())
            assert "subtask_started" in text and "subtask_failed" in text
            assert text.index("subtask_failed") < text.index("run_end")
