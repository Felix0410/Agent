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
