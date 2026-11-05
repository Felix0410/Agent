import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from openai import APIError, APITimeoutError
from pydantic import BaseModel

from minideerflow.agents.lead import build_lead_agent
from minideerflow.config import get_settings
from minideerflow.core.model import ModelNotConfigured, build_chat_model
from minideerflow.tools.calculator import calculate


class AgentExecutionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolTrace(BaseModel):
    name: str
    args: dict[str, Any]
    result: str
    ok: bool


class AgentResponse(BaseModel):
    answer: str
    tool_calls: list[ToolTrace]


def validate_message(message: str) -> str:
    if not message.strip() or len(message) > 2000:
        raise ValueError("message must contain 1 to 2000 characters")
    return message


async def run_agent_once(message: str, *, model: BaseChatModel | None = None) -> AgentResponse:
    validate_message(message)
    try:
        settings = get_settings()
        if model is None:
            model = build_chat_model(settings)
        agent = build_lead_agent(model, [calculate])
        async with asyncio.timeout(settings.model_timeout_seconds):
            state = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config={"recursion_limit": 12},
            )
        messages = state["messages"]
        pending = {}
        traces = []
        for item in messages:
            if isinstance(item, AIMessage):
                for call in item.tool_calls:
                    call_id = call.get("id")
                    if not call_id or call_id in pending:
                        raise ValueError("invalid tool call id")
                    pending[call_id] = call
            elif isinstance(item, ToolMessage):
                call = pending.pop(item.tool_call_id, None)
                if call is None:
                    raise ValueError("unmatched tool result")
                result = item.content if isinstance(item.content, str) else str(item.content)
                traces.append(
                    ToolTrace(
                        name=call["name"],
                        args=call["args"],
                        result=result,
                        ok=item.status != "error" and not result.startswith("ERROR["),
                    )
                )
        final = messages[-1]
        if (
            pending
            or not isinstance(final, AIMessage)
            or final.tool_calls
            or final.invalid_tool_calls
            or not final.text.strip()
        ):
            raise ValueError("no final answer")
        return AgentResponse(answer=final.text, tool_calls=traces)
    except ModelNotConfigured:
        raise
    except (TimeoutError, APITimeoutError):
        raise AgentExecutionError("MODEL_TIMEOUT", "Model request timed out") from None
    except APIError:
        raise AgentExecutionError("MODEL_UPSTREAM_ERROR", "Model provider request failed") from None
    except Exception:  # noqa: BLE001 - the public boundary must sanitize provider/framework errors
        raise AgentExecutionError("AGENT_EXECUTION_FAILED", "Agent execution failed") from None
