"""单轮 Agent 执行服务：编排、消息校验、工具轨迹还原与错误脱敏。"""

import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from openai import APIError, APITimeoutError
from pydantic import BaseModel

from minideerflow.agents.lead import build_lead_agent
from minideerflow.config import get_settings
from minideerflow.core.model import ModelNotConfigured, build_chat_model
from minideerflow.tools.calculator import calculate


class AgentExecutionError(Exception):
    """统一的 Agent 执行错误，避免对外泄露模型供应商原始异常。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolTrace(BaseModel):
    """从真实模型/工具消息还原的调用记录，而非推测生成的轨迹。"""

    name: str
    args: dict[str, Any]
    result: str
    ok: bool


class AgentResponse(BaseModel):
    """一次独立请求的最终答复及工具调用记录。"""

    answer: str
    tool_calls: list[ToolTrace]


def validate_message(message: str) -> str:
    """限制消息非空且长度在本地 Demo 允许的范围内。"""
    if not message.strip() or len(message) > 2000:
        raise ValueError("message must contain 1 to 2000 characters")
    return message


def extract_run_tool_traces(messages: list[BaseMessage]) -> list[ToolTrace]:
    """按真实回执顺序配对调用 ID，拒绝重复 ID、未匹配及缺失回执。"""
    pending = {}
    seen = set()
    traces = []
    for item in messages:
        if isinstance(item, AIMessage):
            if item.invalid_tool_calls:
                raise ValueError("invalid tool call")
            for call in item.tool_calls:
                call_id = call.get("id")
                if not call_id or call_id in seen:
                    raise ValueError("invalid tool call id")
                seen.add(call_id)
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
    if pending:
        raise ValueError("missing tool result")
    return traces


def extract_final_answer(messages: list[BaseMessage]) -> str:
    """最终答案必须来自本轮最后一条无工具请求的有效 AIMessage。"""
    if not messages:
        raise ValueError("no final answer")
    final = messages[-1]
    if (
        not isinstance(final, AIMessage)
        or final.tool_calls
        or final.invalid_tool_calls
        or not final.text.strip()
    ):
        raise ValueError("no final answer")
    return final.text


async def run_agent_once(message: str, *, model: BaseChatModel | None = None) -> AgentResponse:
    """执行一次无会话持久化的 Agent 请求，并提取可信的最终答复和工具轨迹。"""
    # 1. 先校验用户输入；测试可注入假模型，真实请求才从配置创建模型。
    validate_message(message)
    try:
        settings = get_settings()
        if model is None:
            model = build_chat_model(settings)
        agent = build_lead_agent(model, [calculate])
        # 2. 由 LangChain 完成模型→工具→模型的实际循环，同时设置超时和递归上限。
        async with asyncio.timeout(settings.model_timeout_seconds):
            state = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config={"recursion_limit": 12},
            )
        # 3. 单轮与持久 Run 复用相同的消息验收，不能从文本猜测工具调用。
        messages = state["messages"]
        traces = extract_run_tool_traces(messages)
        return AgentResponse(answer=extract_final_answer(messages), tool_calls=traces)
    # 5. 错误统一映射为对外安全的错误码；不透传 Provider 的请求、密钥或堆栈。
    except ModelNotConfigured:
        raise
    except (TimeoutError, APITimeoutError):
        raise AgentExecutionError("MODEL_TIMEOUT", "Model request timed out") from None
    except APIError:
        raise AgentExecutionError("MODEL_UPSTREAM_ERROR", "Model provider request failed") from None
    except Exception:  # noqa: BLE001 - the public boundary must sanitize provider/framework errors
        raise AgentExecutionError("AGENT_EXECUTION_FAILED", "Agent execution failed") from None
