"""Fake模型经真实ToolNode/Checkpoint/Artifact/HTTP走通研究报告。"""

import hashlib
import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.research.models import SearchHit
from minideerflow.research.provider import TavilyProvider
from minideerflow.runtime import runner


def test_real_graph_report_and_reopen(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-only")
    get_settings.cache_clear()

    async def search(self, query, max_results=5):
        return [
            SearchHit(
                title="Real Fake source",
                url="https://example.com/",
                snippet="snippet",
                searched_at="now",
            )
        ]

    async def extract(self, url):
        return "bounded body evidence"

    monkeypatch.setattr(TavilyProvider, "search", search)
    monkeypatch.setattr(TavilyProvider, "extract", extract)

    class Model(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            last = messages[-1]
            if not isinstance(last, ToolMessage):
                name, args = "list_skills", {}
            elif last.name == "list_skills":
                name, args = "read_skill", {"name": "deep-research"}
            elif last.name == "read_skill":
                name, args = "search_web", {"query": "public documentation"}
            elif last.name == "search_web":
                name, args = "fetch_webpage", {"evidence_id": json.loads(last.content)[0]["id"]}
            elif last.name == "fetch_webpage":
                name, args = (
                    "save_research_report",
                    {
                        "title": "Research test",
                        "findings": [
                            {
                                "claim": "An extracted source is available; not independently verified",
                                "evidence_ids": [json.loads(last.content)["id"]],
                            }
                        ],
                        "limitations": ["Synthetic test source only"],
                    },
                )
            else:
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content="Report saved"))]
                )
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content="", tool_calls=[{"name": name, "id": name, "args": args}]
                        )
                    )
                ]
            )

    monkeypatch.setattr(
        runner, "build_chat_model", lambda s: Model(responses=[AIMessage(content="unused")])
    )
    app = create_app()
    with TestClient(app) as c:
        tid = c.post("/api/threads", json={}).json()["id"]
        rid = c.post(f"/api/threads/{tid}/runs", json={"message": "Create research report"}).json()[
            "run_id"
        ]
        drain(c, app)
        result = c.get(f"/api/runs/{rid}").json()
        assert result["status"] == "SUCCEEDED", result
        assert all(t["ok"] for t in result["tool_calls"]), result
        report = c.get(f"/api/runs/{rid}/research/report").json()
        assert report and report["citations"][0]["source_status"] == "EXTRACTED"
        aid = report["artifact_id"]
        content = c.get(f"/api/artifacts/{aid}", params={"thread_id": tid}).content
        files = c.get(f"/api/threads/{tid}/files").json()
        assert len(files) == 1 and hashlib.sha256(content).hexdigest() == files[0]["sha256"]
        assert report["citations"][0]["id"].encode() in content
        assert c.get(f"/api/runs/{rid}/usage").json()["tool_calls"] == 5
    with TestClient(create_app()) as c:
        assert c.get(f"/api/runs/{rid}/research/report").json() == report
        assert c.get(f"/api/artifacts/{aid}", params={"thread_id": tid}).content == content
