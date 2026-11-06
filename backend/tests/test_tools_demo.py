"""P05主Run内MCP+Skill+文件，真实临时HTTP/Checkpoint链路。"""

import asyncio
import hashlib

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from test_lead import ScriptedModel
from test_mcp import approved_config, mcp_server
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.runtime import runner


def test_mcp_skill_file_demo_and_history_reopen(tmp_path, monkeypatch):
    with mcp_server() as (_, port):
        path, _ = asyncio.run(approved_config(tmp_path, port))
        monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
        get_settings.cache_clear()
        file_id = None

        def factory(settings):
            def call(name, args, id):
                return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])

            return ScriptedModel(
                responses=[
                    call("mcp_demo_lookup_fact", {"topic": "langgraph"}, "fact"),
                    call("list_skills", {}, "skills"),
                    call("read_skill", {"name": "file-analysis"}, "skill"),
                    call("list_files", {}, "list"),
                    call("read_text", {"file_id": file_id}, "read"),
                    call(
                        "write_text",
                        {"filename": "summary.md", "content": "P05 synthetic facts and evidence"},
                        "write",
                    ),
                    AIMessage(content="summary ready"),
                ]
            )

        monkeypatch.setattr(runner, "build_chat_model", factory)
        app = create_app()
        with TestClient(app) as client:
            tid = client.post("/api/threads", json={}).json()["id"]
            file_id = client.post(
                f"/api/threads/{tid}/files",
                files={"file": ("notes.md", b"P05 synthetic evidence", "text/markdown")},
            ).json()["id"]
            rid = client.post(
                f"/api/threads/{tid}/runs",
                json={"message": "read workflow and facts, create summary"},
            ).json()["run_id"]
            drain(client, app)
            result = client.get("/api/runs/" + rid).json()
            assert result["status"] == "SUCCEEDED" and all(t["ok"] for t in result["tool_calls"])
            assert [t["name"] for t in result["tool_calls"]] == [
                "mcp_demo_lookup_fact",
                "list_skills",
                "read_skill",
                "list_files",
                "read_text",
                "write_text",
            ]
            assert "LangGraph" in result["tool_calls"][0]["result"]
            assert result["tool_calls"][4]["result"] == "P05 synthetic evidence"
            a = client.get(f"/api/threads/{tid}/artifacts").json()[0]
            url = f"/api/artifacts/{a['artifact_id']}?thread_id={tid}"
            data = client.get(url).content
            assert data == b"P05 synthetic facts and evidence"
            file = next(
                f for f in client.get(f"/api/threads/{tid}/files").json() if f["id"] == a["file_id"]
            )
            assert hashlib.sha256(data).hexdigest() == file["sha256"]
            text = client.get(f"/api/runs/{rid}/events").text
            assert (
                "mcp_demo_lookup_fact" in text and "read_skill" in text and "event: run_end" in text
            )
            assert "127.0.0.1" not in str(client.get("/api/tools").json())
        # 全生命周期重开只读SQL/Artifact；不会靠事件窗口伪造历史。
        with TestClient(create_app()) as client:
            assert client.get("/api/runs/" + rid).json()["tool_calls"] == result["tool_calls"]
            assert client.get(url).content == data
            assert client.get("/api/skills").json()[0]["name"] == "file-analysis"


def test_child_allowlist_remains_small_with_parent_external_tools(tmp_path, monkeypatch):
    from minideerflow.agents.subagents import executor

    original = executor.create_agent
    observed = []

    def capture(model, tools, **kwargs):
        names = {t.name for t in tools}
        observed.append(names)
        assert not names & {
            "mcp_demo_lookup_fact",
            "list_skills",
            "read_skill",
            "write_text",
            "task",
            "write_todos",
        }
        return original(model, tools, **kwargs)

    monkeypatch.setattr(executor, "create_agent", capture)
    # P04完整Demo真实经过现有Runner/Guard，父registry现在额外有Skill元工具。
    from test_planning_demo import test_complete_demo_refresh_reopen_and_run_isolation

    with mcp_server() as (_, port):
        path, _ = asyncio.run(approved_config(tmp_path, port))
        monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
        get_settings.cache_clear()
        test_complete_demo_refresh_reopen_and_run_isolation(monkeypatch)
    assert len(observed) == 2
