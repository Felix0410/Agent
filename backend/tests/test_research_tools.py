"""Fake只替代Provider/模型，实际HTTP/ToolNode/SQLite/Checkpoint仍执行。"""

import json

import pytest
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
from minideerflow.tools.research_tools import fetch_webpage, list_evidence, search_web


@pytest.mark.parametrize("long_urls", [False, True])
def test_parallel_search_previews_fit_default_context(monkeypatch, long_urls):
    """真实Runner串起并行搜索/取文；仅Provider和模型替换为可观测Fake。"""
    monkeypatch.setenv("TAVILY_API_KEY", "test-only")
    get_settings.cache_clear()

    async def search(self, query, max_results=5):
        return [
            SearchHit(
                title="合成来源标题" * 30,
                url=f"https://example.com/{query}/{n}" + ("x" * 1900 if long_urls else ""),
                snippet="合成中文搜索摘要" * 60,
                searched_at="now",
            )
            for n in range(5)
        ]

    async def extract(self, url):
        return "合成正文" * 1000

    monkeypatch.setattr(TavilyProvider, "search", search)
    monkeypatch.setattr(TavilyProvider, "extract", extract)
    observed = []

    class Model(ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            results = [m for m in messages if isinstance(m, ToolMessage)]
            observed.append(results)
            if not results:
                calls = [
                    {"name": "search_web", "id": f"search-{q}", "args": {"query": q}}
                    for q in ("a", "b")
                ]
                reply = AIMessage(content="", tool_calls=calls)
            elif results[-1].name == "search_web":
                evidence_id = json.loads(results[0].content)[0]["id"]
                reply = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "fetch_webpage",
                            "id": "fetch",
                            "args": {"evidence_id": evidence_id},
                        }
                    ],
                )
            else:
                reply = AIMessage(content="Synthetic preview only")
            return ChatResult(generations=[ChatGeneration(message=reply)])

    monkeypatch.setattr(
        runner, "build_chat_model", lambda s: Model(responses=[AIMessage(content="unused")])
    )
    app = create_app()
    with TestClient(app) as client:
        # 1. 默认上下文预算下，两个满额中文搜索结果后仍可取文、完成回答。
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(f"/api/threads/{tid}/runs", json={"message": "查询合成资料"}).json()[
            "run_id"
        ]
        drain(client, app)
        run = client.get(f"/api/runs/{rid}").json()
        assert run["status"] == "SUCCEEDED", run["error_code"]
        usage = client.get(f"/api/runs/{rid}/usage").json()
        assert usage["model_calls"] == 3 and usage["tool_calls"] == 3
        # 2. 所有ID和配对关系进入下一次模型请求，正文只缩短模型预览。
        results = observed[-1]
        assert [m.tool_call_id for m in results] == ["search-a", "search-b", "fetch"]
        assert all(len(m.content.encode()) <= 3072 for m in results)
        ids = {item["id"] for m in results[:2] for item in json.loads(m.content)}
        records = client.get(f"/api/runs/{rid}/research/evidence").json()
        assert len(records) == 10 and ids == {item["id"] for item in records}
        assert all(item["snippet"] == "合成中文搜索摘要" * 60 for item in records)
        if long_urls:
            assert all(len(item["url"]) > 1900 for item in records)
        extracted = next(item for item in records if item["source_status"] == "EXTRACTED")
        assert len(extracted["excerpt"]) == 1500
        assert "Preview only" in results[-1].content


def test_full_evidence_list_keeps_all_references_in_bounded_preview():
    from minideerflow.research.models import EvidenceRecord, SourceStatus
    from minideerflow.tools.research_tools import _evidence_previews

    records = [
        EvidenceRecord(
            id=f"00000000-0000-0000-0000-{n:012d}",
            title="合成标题" * 50,
            url="https://example.com/" + "x" * 1900,
            snippet="合成摘要" * 100,
            searched_at="now",
            source_status=SourceStatus.SNIPPET_ONLY,
            excerpt="",
        )
        for n in range(30)
    ]
    payload = _evidence_previews(records)
    assert len(json.dumps(payload, ensure_ascii=False).encode()) <= 3072
    assert [item["id"] for item in payload] == [item.id for item in records]
    assert all(item["source_status"] == "SNIPPET_ONLY" for item in payload)


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


def test_parallel_chinese_search_previews_fit_default_context(monkeypatch):
    """两次各五条中文摘要不应挤爆普通Run；SQL原证据必须保持完整。"""
    monkeypatch.setenv("TAVILY_API_KEY", "test-only")
    get_settings.cache_clear()
    snippet = "合成搜索摘要，用于验证中文UTF8预览预算。" * 30
    snippet = snippet[:500]

    async def search(self, query, max_results=5):
        return [
            SearchHit(
                title=("合成来源标题" * 15)[:100],
                url=f"https://example.com/{query}/{index}",
                snippet=snippet,
                searched_at="2026-11-17T00:00:00+00:00",
            )
            for index in range(5)
        ]

    models = []

    def factory(settings):
        model = ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "search_web", "id": query, "args": {"query": query}}
                        for query in ("alpha", "beta")
                    ],
                ),
                AIMessage(content="Synthetic preview comparison; full evidence remains recorded."),
            ]
        )
        models.append(model)
        return model

    monkeypatch.setattr(TavilyProvider, "search", search)
    monkeypatch.setattr(runner, "build_chat_model", factory)
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(
            f"/api/threads/{tid}/runs", json={"message": "合成问题：比较两个方向"}
        ).json()["run_id"]
        drain(client, app)
        run = client.get(f"/api/runs/{rid}").json()
        assert run["status"] == "SUCCEEDED", run["error_code"]
        evidence = client.get(f"/api/runs/{rid}/research/evidence").json()
        assert len(evidence) == 10 and all(row["snippet"] == snippet for row in evidence)
        for trace in run["tool_calls"]:
            previews = json.loads(trace["result"])
            assert len(previews) == 5
            assert all(item["id"] in {row["id"] for row in evidence} for item in previews)
            assert all(len(item["snippet"].encode("utf-8")) <= 120 for item in previews)
            assert all(item["preview_only"] is True for item in previews)
        assert len(models[-1].seen) == 2
        usage = client.get(f"/api/runs/{rid}/usage").json()
        assert usage["model_calls"] == 2 and usage["tool_calls"] == 2
        assert usage["compaction_count"] == 0
