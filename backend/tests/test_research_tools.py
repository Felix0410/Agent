"""Fake只替代Provider/模型，实际HTTP/ToolNode/SQLite/Checkpoint仍执行。"""

import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.research.models import SearchHit
from minideerflow.research.provider import TavilyProvider
from minideerflow.runtime import runner
from minideerflow.tools.research_tools import fetch_webpage, list_evidence, search_web


def test_schema_hides_context():
    for t in (search_web, fetch_webpage, list_evidence):
        assert (
            not {"runtime", "run_id", "thread_id", "provider", "key", "service"}
            & t.tool_call_schema.model_json_schema()["properties"].keys()
        )


def test_unconfigured_keeps_old_tools():
    with TestClient(create_app()) as c:
        assert c.get("/api/research/status").json()["enabled"] is False
        assert c.get("/api/runs/missing/research/evidence").status_code == 404
        assert c.get("/api/runs/missing/research/report").status_code == 404


def test_real_toolnode_search_extract(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-only")
    get_settings.cache_clear()

    async def search(self, query, max_results=5):
        return [
            SearchHit(
                title="source", url="https://example.com/", snippet="snippet", searched_at="now"
            )
        ]

    async def extract(self, url):
        return "Extracted body; data only"

    monkeypatch.setattr(TavilyProvider, "search", search)
    monkeypatch.setattr(TavilyProvider, "extract", extract)

    class Model(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            from langchain_core.outputs import ChatGeneration, ChatResult

            last = messages[-1]
            if isinstance(last, ToolMessage) and last.name == "search_web":
                evidence = json.loads(last.content)[0]
                result = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "fetch_webpage",
                            "id": "extract",
                            "args": {"evidence_id": evidence["id"]},
                        }
                    ],
                )
            elif isinstance(last, ToolMessage):
                result = AIMessage(content="done")
            else:
                result = AIMessage(
                    content="",
                    tool_calls=[{"name": "search_web", "id": "search", "args": {"query": "topic"}}],
                )
            return ChatResult(generations=[ChatGeneration(message=result)])

    monkeypatch.setattr(
        runner, "build_chat_model", lambda s: Model(responses=[AIMessage(content="unused")])
    )
    app = create_app()
    with TestClient(app) as c:
        tid = c.post("/api/threads", json={}).json()["id"]
        rid = c.post(f"/api/threads/{tid}/runs", json={"message": "research"}).json()["run_id"]
        drain(c, app)
        run = c.get(f"/api/runs/{rid}").json()
        assert run["status"] == "SUCCEEDED", run
        rows = c.get(f"/api/runs/{rid}/research/evidence").json()
        assert len(rows) == 1 and rows[0]["source_status"] == "EXTRACTED"
        assert len(rows[0]["excerpt"]) <= 1500
        assert c.get(f"/api/runs/{rid}/usage").json()["tool_calls"] == 2
        assert c.get(f"/api/runs/{rid}/research/report").json() is None
    with TestClient(create_app()) as c:
        assert c.get(f"/api/runs/{rid}/research/evidence").json() == rows


def test_configured_simple_question_never_searches(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-only")
    get_settings.cache_clear()
    calls = []

    async def unexpected(self, query, max_results=5):
        calls.append(query)
        raise AssertionError("simple question must not search")

    monkeypatch.setattr(TavilyProvider, "search", unexpected)
    monkeypatch.setattr(
        runner, "build_chat_model", lambda s: ScriptedModel(responses=[AIMessage(content="Hello")])
    )
    app = create_app()
    with TestClient(app) as c:
        tid = c.post("/api/threads", json={}).json()["id"]
        rid = c.post(f"/api/threads/{tid}/runs", json={"message": "Hello"}).json()["run_id"]
        drain(c, app)
        assert c.get(f"/api/runs/{rid}").json()["status"] == "SUCCEEDED"
        assert c.get(f"/api/runs/{rid}/usage").json()["tool_calls"] == 0
        assert c.get(f"/api/runs/{rid}/research/evidence").json() == [] and calls == []
        assert "test-only" not in c.get("/api/research/status").text
