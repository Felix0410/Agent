"""P04完整HTTP/Fake链路与跨生命周期权威历史。"""

import hashlib

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.main import create_app
from minideerflow.runtime import runner
from minideerflow.runtime.checkpoints import thread_config


def plan(status):
    return [
        {"todo_id": str(n), "title": title, "status": status}
        for n, title in enumerate(["分析核心观点", "分析潜在问题", "生成摘要"])
    ]


def parent_model():
    def call(name, args, id):
        return {"name": name, "args": args, "id": id}

    return ScriptedModel(
        responses=[
            AIMessage(
                content="", tool_calls=[call("write_todos", {"items": plan("in_progress")}, "plan")]
            ),
            AIMessage(
                content="",
                tool_calls=[
                    call(
                        "task",
                        {
                            "agent_type": "general",
                            "description": "Analyze core ideas in notes.md",
                            "todo_id": "0",
                        },
                        "one",
                    ),
                    call(
                        "task",
                        {
                            "agent_type": "research",
                            "description": "Analyze issues in notes.md",
                            "todo_id": "1",
                        },
                        "two",
                    ),
                ],
            ),
            AIMessage(
                content="", tool_calls=[call("write_todos", {"items": plan("completed")}, "finish")]
            ),
            AIMessage(
                content="",
                tool_calls=[
                    call(
                        "write_text",
                        {"filename": "summary.md", "content": "P04 synthetic findings and issues"},
                        "write",
                    )
                ],
            ),
            AIMessage(content="Created summary from two real delegated results."),
        ]
    )


def test_complete_demo_refresh_reopen_and_run_isolation(monkeypatch):
    file_id = None
    calls = 0
    children = []
    parent = parent_model()

    def factory(settings):
        nonlocal calls
        calls += 1
        if calls <= 2:
            return parent
        child = ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "child-read", "name": "read_text", "args": {"file_id": file_id}}
                    ],
                ),
                AIMessage(content="P04 synthetic child analysis"),
            ]
        )
        children.append(child)
        return child

    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        file_id = client.post(
            f"/api/threads/{thread}/files",
            files={
                "file": ("notes.md", b"P04 synthetic project: ideas and risks", "text/markdown")
            },
        ).json()["id"]
        run = client.post(
            f"/api/threads/{thread}/runs",
            json={"message": "PARENT_HISTORY: analyze notes and create summary"},
        ).json()["run_id"]
        drain(client, app)
        result = client.get("/api/runs/" + run).json()
        assert result["status"] == "SUCCEEDED", result
        todos = client.get(f"/api/runs/{run}/todos").json()
        tasks = client.get(f"/api/runs/{run}/subtasks").json()
        assert len(todos) == 3 and all(t["status"] == "completed" for t in todos)
        assert len(tasks) == 2 and all(
            t["status"] == "COMPLETED" and t["source_file_ids"] == [file_id] for t in tasks
        )
        assert all("PARENT_HISTORY" not in str(c.seen) for c in children)
        artifact = client.get(f"/api/threads/{thread}/artifacts").json()[0]
        url = f"/api/artifacts/{artifact['artifact_id']}?thread_id={thread}"
        data = client.get(url).content
        assert data == b"P04 synthetic findings and issues"
        files = client.get(f"/api/threads/{thread}/files").json()
        assert (
            next(f for f in files if f["id"] == artifact["file_id"])["sha256"]
            == hashlib.sha256(data).hexdigest()
        )
        with client.stream("GET", f"/api/runs/{run}/events") as response:
            sse = "".join(response.iter_text())
        for kind in [
            "todo_updated",
            "subtask_created",
            "subtask_started",
            "subtask_completed",
            "tool_start",
            "tool_end",
            "run_end",
        ]:
            assert f"event: {kind}" in sse
        assert "child-read" not in sse
        # 1. 下一Run只做普通答复，Graph.todos清空而历史SQL不丢。
        app.state.runner.model_factory = lambda settings: ScriptedModel(
            responses=[AIMessage(content="simple")]
        )
        next_run = client.post(f"/api/threads/{thread}/runs", json={"message": "hello"}).json()[
            "run_id"
        ]
        drain(client, app)
        assert client.get(f"/api/runs/{next_run}/todos").json() == []
        state = client.portal.call(app.state.checkpointer.aget_tuple, thread_config(thread))
        assert state.checkpoint["channel_values"]["todos"] == []
        assert client.get(f"/api/runs/{run}/todos").json() == todos
        other = client.post("/api/threads", json={}).json()["id"]
        other_run = client.post(f"/api/threads/{other}/runs", json={"message": "hello"}).json()[
            "run_id"
        ]
        drain(client, app)
        assert client.get(f"/api/runs/{other_run}/subtasks").json() == []
        # 3. 模拟进程中断留下的父/子SQL记录，重开只标失败不重放。
        from minideerflow.runtime.models import RunStatus

        async def leave_orphans():
            orphan = await app.state.repository.create_run(other, "interrupted")
            await app.state.repository.transition_run(
                orphan.id, RunStatus.CREATED, RunStatus.RUNNING
            )
            await app.state.plans.create_subtask(orphan.id, other, "general", "pending")
            running = await app.state.plans.create_subtask(orphan.id, other, "research", "running")
            from minideerflow.agents.subagents.models import TaskStatus

            await app.state.plans.transition_subtask(
                running.id, orphan.id, other, TaskStatus.RUNNING
            )
            return orphan.id

        orphan_id = client.portal.call(leave_orphans)
    # 2. 应用完整关闭/重开，历史来自同一临时SQL，无SSE仍能恢复并下载。
    with TestClient(create_app()) as client:
        assert client.get(f"/api/runs/{run}/todos").json() == todos
        assert client.get(f"/api/runs/{run}/subtasks").json() == tasks
        assert client.get(url).content == data
        assert client.get(f"/api/threads/{other}/artifacts").json() == []
        assert client.get("/api/runs/" + orphan_id).json()["status"] == "FAILED"
        orphan_tasks = client.get(f"/api/runs/{orphan_id}/subtasks").json()
        assert len(orphan_tasks) == 2 and all(
            t["status"] == "FAILED" and t["error_code"] == "SUBTASK_INTERRUPTED"
            for t in orphan_tasks
        )
