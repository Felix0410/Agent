"""目录仅公开安全元信息，无工具执行/授权入口。"""

from fastapi.testclient import TestClient

from minideerflow.main import create_app


def test_builtin_catalog_readonly():
    with TestClient(create_app()) as client:
        tools = client.get("/api/tools").json()
        assert len(tools) == 6 and all(t["availability"] == "available" for t in tools)
        assert [t["name"] for t in tools] == sorted(t["name"] for t in tools)
        assert client.get("/api/skills").json() == []
        assert client.post("/api/tools", json={}).status_code == 405


def test_real_mcp_http_run_and_builtin_survives_disconnect(tmp_path, monkeypatch):
    """两真实进程HTTP协议，经现有Run路由得到真实ToolTrace。"""
    import asyncio

    from langchain_core.messages import AIMessage
    from test_lead import ScriptedModel
    from test_mcp import approved_config, mcp_server
    from test_runs_api import drain

    from minideerflow.config import get_settings
    from minideerflow.runtime import runner

    with mcp_server() as (process, port):
        path, _ = asyncio.run(approved_config(tmp_path, port))
        monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
        get_settings.cache_clear()

        def factory(settings):
            return ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "fact",
                                "name": "mcp_demo_lookup_fact",
                                "args": {"topic": "langgraph"},
                            }
                        ],
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": "calc", "name": "calculate", "args": {"expression": "1+2"}}
                        ],
                    ),
                    AIMessage(content="done"),
                ]
            )

        monkeypatch.setattr(runner, "build_chat_model", factory)
        app = create_app()
        with TestClient(app) as client:
            assert any(
                t["name"] == "mcp_demo_lookup_fact" and t["availability"] == "available"
                for t in client.get("/api/tools").json()
            )
            for connected in [True, False]:
                if not connected:
                    process.terminate()
                    process.wait(timeout=5)
                tid = client.post("/api/threads", json={}).json()["id"]
                rid = client.post(
                    f"/api/threads/{tid}/runs", json={"message": "fact and calculate"}
                ).json()["run_id"]
                drain(client, app)
                run = client.get("/api/runs/" + rid).json()
                assert run["status"] == "SUCCEEDED"
                assert run["tool_calls"][0]["ok"] is connected
                assert run["tool_calls"][1]["ok"] and run["tool_calls"][1]["result"] == "3"
            assert (
                next(t for t in client.get("/api/tools").json() if t["source"] == "mcp")[
                    "availability"
                ]
                == "MCP_UNAVAILABLE"
            )
