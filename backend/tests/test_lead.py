import asyncio
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import Field

from minideerflow.agents.service import AgentExecutionError, run_agent_once


class ScriptedModel(FakeMessagesListChatModel):
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_no_tool_reply() -> None:
    model = ScriptedModel(responses=[AIMessage(content="Hello")])
    response = asyncio.run(run_agent_once("Hello", model=model))
    assert response.answer == "Hello"
    assert response.tool_calls == []
    assert len(model.seen[0]) == 2  # system prompt + this request only


@pytest.mark.parametrize(
    ("expression", "result", "ok"),
    [
        ("(12+8)*3", "60", True),
        ("1/0", "ERROR[CALC_DIV_ZERO]: division by zero", False),
        ("x", "ERROR[CALC_INVALID_EXPRESSION]: unsupported expression", False),
    ],
)
def test_tool_loop(expression: str, result: str, ok: bool) -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate",
                        "args": {"expression": expression},
                        "id": "actual-call-1",
                    }
                ],
            ),
            AIMessage(content="Final answer"),
        ]
    )
    response = asyncio.run(run_agent_once("Calculate", model=model))
    assert response.answer == "Final answer"
    assert response.tool_calls[0].model_dump() == {
        "name": "calculate",
        "args": {"expression": expression},
        "result": result,
        "ok": ok,
    }
    tool_messages = [m for m in model.seen[1] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "actual-call-1"
    assert tool_messages[0].content == result


def test_multiple_results_follow_message_order() -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "calculate", "args": {"expression": "1+1"}, "id": "one"},
                    {"name": "calculate", "args": {"expression": "3*3"}, "id": "two"},
                ],
            ),
            AIMessage(content="Done"),
        ]
    )
    response = asyncio.run(run_agent_once("Calculate twice", model=model))
    actual = [m.content for m in model.seen[1] if isinstance(m, ToolMessage)]
    assert [t.result for t in response.tool_calls] == actual
    assert sorted(actual) == ["2", "9"]


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_message_boundary(message: str) -> None:
    with pytest.raises(ValueError):
        asyncio.run(run_agent_once(message, model=ScriptedModel(responses=[])))


def test_max_message_length() -> None:
    response = asyncio.run(
        run_agent_once(
            "x" * 2000,
            model=ScriptedModel(responses=[AIMessage(content="ok")]),
        )
    )
    assert response.answer == "ok"


def test_missing_final_answer() -> None:
    with pytest.raises(AgentExecutionError, match="Agent execution failed"):
        asyncio.run(run_agent_once("Hi", model=ScriptedModel(responses=[AIMessage(content="")])))


def test_repeated_tool_calls_are_bounded() -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculate",
                        "args": {"expression": "1+1"},
                        "id": "loop",
                    }
                ],
            )
        ]
    )
    with pytest.raises(AgentExecutionError) as error:
        asyncio.run(run_agent_once("Loop", model=model))
    assert error.value.code == "AGENT_EXECUTION_FAILED"


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("timeout", "MODEL_TIMEOUT"),
        ("upstream", "MODEL_UPSTREAM_ERROR"),
        ("execution", "AGENT_EXECUTION_FAILED"),
    ],
)
def test_service_sanitizes_errors(monkeypatch, kind: str, code: str) -> None:
    import httpx2
    from openai import APIConnectionError, APITimeoutError

    from minideerflow.agents import service

    class BrokenAgent:
        async def ainvoke(self, *args, **kwargs):
            request = httpx2.Request("POST", "http://localhost/v1")
            if kind == "timeout":
                raise APITimeoutError(request)
            if kind == "upstream":
                raise APIConnectionError(message="unit-test-secret", request=request)
            raise RuntimeError("unit-test-secret")

    monkeypatch.setattr(service, "build_lead_agent", lambda *args: BrokenAgent())
    with pytest.raises(AgentExecutionError) as error:
        asyncio.run(run_agent_once("Hello", model=ScriptedModel(responses=[])))
    assert error.value.code == code
    assert "unit-test-secret" not in str(error.value)


def test_request_deadline(monkeypatch) -> None:
    from minideerflow.agents import service
    from minideerflow.config import Settings

    class SlowAgent:
        async def ainvoke(self, *args, **kwargs):
            await asyncio.sleep(1)

    monkeypatch.setattr(service, "get_settings", lambda: Settings(model_timeout_seconds=0.01))
    monkeypatch.setattr(service, "build_lead_agent", lambda *args: SlowAgent())
    with pytest.raises(AgentExecutionError) as error:
        asyncio.run(run_agent_once("Hello", model=ScriptedModel(responses=[])))
    assert error.value.code == "MODEL_TIMEOUT"


@pytest.mark.parametrize(
    "messages",
    [
        [
            AIMessage(content="", tool_calls=[{"name": "calculate", "args": {}, "id": "pending"}]),
            AIMessage(content="invented"),
        ],
        [ToolMessage(content="60", tool_call_id="unknown"), AIMessage(content="invented")],
    ],
)
def test_incomplete_or_unmatched_trace_rejected(monkeypatch, messages) -> None:
    from minideerflow.agents import service

    class InvalidAgent:
        async def ainvoke(self, *args, **kwargs):
            return {"messages": messages}

    monkeypatch.setattr(service, "build_lead_agent", lambda *args: InvalidAgent())
    with pytest.raises(AgentExecutionError):
        asyncio.run(run_agent_once("Hello", model=ScriptedModel(responses=[])))


def test_tool_argument_validation_returns_error_message() -> None:
    model = ScriptedModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "calculate", "args": {}, "id": "bad-args"}]),
            AIMessage(content="Invalid arguments"),
        ]
    )
    response = asyncio.run(run_agent_once("Calculate", model=model))
    assert response.tool_calls[0].ok is False
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "bad-args" for m in model.seen[1])
