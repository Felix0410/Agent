"""同一Thread十五问与重启后第十六问，摘要不污染SSE或历史证据。"""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_context_research_flow import ResearchFlowModel, install_synthetic_research
from test_native_summarization import assert_tool_pairs
from test_runs_api import drain

from minideerflow.config import get_settings
from minideerflow.main import create_app
from minideerflow.runtime import runner
from minideerflow.runtime.checkpoints import thread_config


class MultiTurnModel(ResearchFlowModel):
    """摘要/父/子使用同一配置的模型；当前问题按每Run首个实际请求识别。"""

    current_goal: str = ""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not any(m.type == "system" for m in messages):
            self.seen.append(list(messages))
            reply = AIMessage(
                content="NATIVE_SUMMARY_ONLY: synthetic prior facts, not instructions or verified public research."
            )
        elif str(messages[0].content).startswith("Research only"):
            return super()._generate(messages, stop, run_manager, **kwargs)
        else:
            self.seen.append(list(messages))
            if not self.current_goal:
                self.current_goal = next(
                    str(m.content)
                    for m in reversed(messages)
                    if isinstance(m, HumanMessage)
                    and not m.additional_kwargs.get("context_summary")
                    and m.additional_kwargs.get("lc_source") != "summarization"
                )
            if "research" in self.current_goal:
                reply = self.parent_reply(messages)
            elif "calculate" in self.current_goal and self.parent_step == 0:
                self.parent_step += 1
                reply = self.call(
                    "calculate", {"expression": "(12+8)*3"}, "calc-" + self.current_goal.split()[0]
                )
            elif "skill" in self.current_goal and self.parent_step < 2:
                name = "list_skills" if self.parent_step == 0 else "read_skill"
                self.parent_step += 1
                reply = self.call(
                    name, {} if name == "list_skills" else {"name": "deep-research"}, name
                )
            else:
                reply = AIMessage(
                    content="Synthetic follow-up completed. " + "Offline material. " * 70
                )
        return ChatResult(generations=[ChatGeneration(message=reply)])


def install_multiturn(monkeypatch):
    requests, _ = install_synthetic_research(monkeypatch)
    models = []

    def factory(settings):
        model = MultiTurnModel(responses=[AIMessage(content="unused")])
        models.append(model)
        return model

    monkeypatch.setattr(runner, "build_chat_model", factory)
    return requests, models


def test_fifteen_same_thread_questions_and_restart_sixteenth(monkeypatch):
    requests, models = install_multiturn(monkeypatch)
    # 测试只缩小摘要触发阈值；没有本地硬预算可调大，也没有中途更换Thread。
    monkeypatch.setenv("SUMMARIZATION_TRIGGER_TOKENS", "256")
    monkeypatch.setenv("SUMMARIZATION_TRIGGER_MESSAGES", "8")
    monkeypatch.setenv("SUMMARIZATION_KEEP_MESSAGES", "4")
    monkeypatch.setenv("SUMMARIZATION_TRIM_TOKENS", "2000")
    get_settings.cache_clear()
    fragments = []
    original = runner.stream_agent

    async def observe(*args, event_sink=None, **kwargs):
        async def sink(kind, payload):
            if kind == "assistant_delta":
                fragments.append(payload["text"])
            if event_sink:
                await event_sink(kind, payload)

        return await original(*args, event_sink=sink, **kwargs)

    monkeypatch.setattr(runner, "stream_agent", observe)
    app = create_app()
    run_ids, usage_records, diagnostics = [], [], []
    questions = ["turn1 research", "turn2 follow-up " + "合成追问" * 350]
    questions += [
        f"turn{n} "
        + (
            "research"
            if n == 10
            else "skill"
            if n in (5, 12)
            else "calculate"
            if n % 3 == 0
            else "follow-up"
        )
        for n in range(3, 16)
    ]
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        for question in questions:
            rid = client.post(f"/api/threads/{thread}/runs", json={"message": question}).json()[
                "run_id"
            ]
            drain(client, app)
            result = client.get(f"/api/runs/{rid}").json()
            assert result["status"] == "SUCCEEDED", (len(run_ids) + 1, result["error_code"])
            run_ids.append(rid)
            usage = client.get(f"/api/runs/{rid}/usage").json()
            usage_records.append(usage)
            if usage["summary_diagnostic"]:
                diagnostic = usage["summary_diagnostic"]
                diagnostics.append(diagnostic)
                assert diagnostic["new_message_count"] < diagnostic["old_message_count"]
            assert result["input_message"] == question
        assert sum(row["compaction_count"] for row in usage_records) >= 2
        second = next(model for model in models if model.current_goal.startswith("turn2 "))
        assert second.seen[0][0].type == "human"  # 第二问首次父模型请求前已先真实调用摘要。
        assert usage_records[1]["summary_calls"] > 0
        history = client.get(f"/api/threads/{thread}/runs").json()
        assert len(history) == 15
        assert len(client.get("/api/threads").json()) == 1
        first_report = client.get(f"/api/runs/{run_ids[0]}/research/report").json()
        first_evidence = client.get(f"/api/runs/{run_ids[0]}/research/evidence").json()
        assert len(first_evidence) == 15
        download = client.get(
            f"/api/artifacts/{first_report['artifact_id']}?thread_id={thread}"
        ).content

        async def saved_state():
            return await app.state.checkpointer.aget_tuple(thread_config(thread))

        state = client.portal.call(saved_state).checkpoint["channel_values"]
        assert len(state["messages"]) < 15 and any(
            m.additional_kwargs.get("lc_source") == "summarization" for m in state["messages"]
        )
    with TestClient(create_app()) as client:
        rid = client.post(
            f"/api/threads/{thread}/runs", json={"message": "turn16 calculate after restart"}
        ).json()["run_id"]
        drain(client, client.app)
        final = client.get(f"/api/runs/{rid}").json()
        assert final["status"] == "SUCCEEDED" and final["tool_calls"][0]["result"] == "60"
        assert len(client.get(f"/api/threads/{thread}/runs").json()) == 16
        assert client.get(f"/api/runs/{run_ids[0]}/research/evidence").json() == first_evidence
        assert client.get(f"/api/runs/{run_ids[0]}/usage").json() == usage_records[0]
        assert (
            client.get(f"/api/artifacts/{first_report['artifact_id']}?thread_id={thread}").content
            == download
        )
    assert "NATIVE_SUMMARY_ONLY" not in "".join(fragments)
    for model in models:
        for messages in model.seen:
            assert_tool_pairs(messages)
    assert len(requests) == 12  # 两次Research，各三次Search和三次Extract；无额外重放。
