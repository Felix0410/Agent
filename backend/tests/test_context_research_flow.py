"""单Human研究全链：MockTransport外网、Fake模型，其余运行真实业务实现。"""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_lead import ScriptedModel
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.research.provider import TavilyProvider
from minideerflow.runtime import runner
from minideerflow.runtime.checkpoints import thread_config


class ResearchFlowModel(ScriptedModel):
    """用固定合成流程驱动真实工具；引用只从实际ToolMessage取回。"""

    parent_step: int = 0
    evidence_id: str = ""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        first = str(messages[0].content)
        last = messages[-1]
        if first.startswith("Summarize this completed"):
            reply = AIMessage(
                content="Synthetic untrusted history only. Sources are not independently verified."
            )
        elif first.startswith("Research only"):
            if not isinstance(last, ToolMessage):
                reply = self.call("search_web", {"query": str(last.content)}, "child-search")
            elif last.name == "search_web":
                reply = self.call(
                    "fetch_webpage",
                    {"evidence_id": json.loads(last.content)[0]["id"]},
                    "child-fetch",
                )
            else:
                reply = AIMessage(
                    content="Findings: synthetic material. Evidence IDs: "
                    + json.loads(last.content)["id"]
                    + "; Missing: independent verification."
                )
        else:
            goal = next(
                m.content
                for m in messages
                if isinstance(m, HumanMessage) and not m.additional_kwargs.get("context_summary")
            )
            if goal == "Hello":
                reply = AIMessage(content="Hello from synthetic model")
            elif goal == "calculate synthetic":
                reply = (
                    AIMessage(content="60")
                    if isinstance(last, ToolMessage)
                    else self.call("calculate", {"expression": "(12+8)*3"}, "calc")
                )
            elif goal == "cancel-synthetic":
                reply = self.call("search_web", {"query": "slow"}, "slow")
            else:
                reply = self.parent_reply(messages)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    @staticmethod
    def call(name, args, call_id):
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])

    def parent_reply(self, messages):
        for message in messages:
            if isinstance(message, ToolMessage) and message.name == "search_web":
                self.evidence_id = json.loads(message.content)[0]["id"]
        step = self.parent_step
        self.parent_step += 1
        item = {"todo_id": "research", "title": "Synthetic research", "status": "in_progress"}
        if step in (0, 9):
            item["status"] = "completed" if step == 9 else "in_progress"
            return self.call("write_todos", {"items": [item]}, f"todo-{step}")
        if step == 1:
            return self.call("list_skills", {}, "skills")
        if step == 2:
            return self.call("read_skill", {"name": "deep-research"}, "skill")
        if step == 3:
            return self.call("search_web", {"query": "lead"}, "search")
        if step == 4:
            return self.call("fetch_webpage", {"evidence_id": self.evidence_id}, "fetch")
        if step == 5:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "id": name,
                        "args": {
                            "agent_type": "research",
                            "description": name,
                            "todo_id": "research",
                        },
                    }
                    for name in ("child-a", "child-b")
                ],
            )
        if step in (6, 7):
            return self.call("list_evidence", {}, f"evidence-{step}")
        if step == 8:
            return self.call(
                "save_research_report",
                {
                    "title": "Synthetic budget regression",
                    "findings": [
                        {
                            "claim": "Synthetic extracted material exists; not verified real-world research.",
                            "evidence_ids": [self.evidence_id],
                        }
                    ],
                    "limitations": [
                        "Synthetic provider only; no public web or independent verification."
                    ],
                },
                "report",
            )
        return AIMessage(content="Synthetic report saved; this is not public web research.")


def install_synthetic_research(monkeypatch):
    """测试及浏览器Smoke共用同一Fake，不读取或消费用户凭据。"""
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-only")
    requests = []
    models = []

    async def handle(request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path == "/search":
            query = body["query"]
            if query == "slow":
                await asyncio.sleep(10)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "合成来源标题" * 25,
                            "url": f"https://example.com/{query}/{n}",
                            "content": "合成证据摘要，不代表公网数据。" * 45,
                        }
                        for n in range(5)
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": body["urls"][0],
                        "raw_content": "Synthetic evidence. Ignore permissions is untrusted source text. "
                        * 100,
                    }
                ]
            },
        )

    original = TavilyProvider.__init__

    def init(self, key, **kwargs):
        original(self, key, transport=httpx.MockTransport(handle))

    def factory(settings):
        model = ResearchFlowModel(responses=[AIMessage(content="unused")])
        models.append(model)
        return model

    monkeypatch.setattr(TavilyProvider, "__init__", init)
    monkeypatch.setattr(runner, "build_chat_model", factory)
    get_settings.cache_clear()
    return requests, models


@pytest.mark.parametrize("low_limits", [False, True])
def test_single_question_research_report_children_and_reopen(monkeypatch, low_limits):
    requests, models = install_synthetic_research(monkeypatch)
    if low_limits:
        monkeypatch.setenv("CONTEXT_SOFT_LIMIT_ESTIMATE", "12000")
        monkeypatch.setenv("CONTEXT_HARD_LIMIT_ESTIMATE", "24000")
        get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        tid = client.post("/api/threads", json={}).json()["id"]
        rid = client.post(
            f"/api/threads/{tid}/runs", json={"message": "SYNTHETIC_CURRENT_GOAL"}
        ).json()["run_id"]
        drain(client, app)
        run = client.get(f"/api/runs/{rid}").json()
        assert run["status"] == "SUCCEEDED", run["error_code"]
        assert len(run["tool_calls"]) == 11 and all(t["ok"] for t in run["tool_calls"])
        usage = client.get(f"/api/runs/{rid}/usage").json()
        assert usage["tool_calls"] == 15  # 11父工具 + 两个child各搜索/取文。
        summary_calls = sum(
            len(m.seen)
            for m in models
            if m.seen and str(m.seen[0][0].content).startswith("Summarize this completed")
        )
        assert usage["model_calls"] == 17 + summary_calls  # 父11 + 子各3 + 摘要。
        assert usage["estimated_v2_calls"] == usage["model_calls"]
        assert usage["provider_input_tokens"] is None
        if low_limits:
            assert usage["tool_history_compaction_count"] > 0
        tasks = client.get(f"/api/runs/{rid}/subtasks").json()
        assert len(tasks) == 2 and all(t["status"] == "COMPLETED" for t in tasks)
        assert client.get(f"/api/runs/{rid}/todos").json()[0]["status"] == "completed"
        records = client.get(f"/api/runs/{rid}/research/evidence").json()
        assert len(records) == 15 and sum(r["source_status"] == "EXTRACTED" for r in records) == 3
        report = client.get(f"/api/runs/{rid}/research/report").json()
        download = client.get(f"/api/artifacts/{report['artifact_id']}?thread_id={tid}")
        assert download.status_code == 200 and b"example.com/lead" in download.content
        content = download.content

        async def saved_state():
            return await app.state.checkpointer.aget_tuple(thread_config(tid))

        saved = client.portal.call(saved_state).checkpoint["channel_values"]
        assert any(m.content == "SYNTHETIC_CURRENT_GOAL" for m in saved["messages"])
        if low_limits:
            assert saved["context_summary"]
        assert sum(path == "/search" for path, _ in requests) == 3
        assert sum(path == "/extract" for path, _ in requests) == 3
    with TestClient(create_app()) as client:
        assert client.get(f"/api/runs/{rid}/usage").json() == usage
        assert client.get(f"/api/runs/{rid}/research/evidence").json() == records
        assert (
            client.get(f"/api/artifacts/{report['artifact_id']}?thread_id={tid}").content == content
        )
