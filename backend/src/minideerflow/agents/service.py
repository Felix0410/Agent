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
    """Agent 执行异常"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolTrace(BaseModel):
    """工具调用轨迹"""

    name: str
    args: dict[str, Any]
    result: str
    ok: bool


class AgentResponse(BaseModel):
    """Agent 执行响应"""

    answer: str
    tool_calls: list[ToolTrace]


def validate_message(message: str) -> str:
    """校验消息长度"""
    if not message.strip() or len(message) > 2000:
        raise ValueError("message must contain 1 to 2000 characters")
    return message


def extract_run_tool_traces(messages: list[BaseMessage]) -> list[ToolTrace]:
    """从消息中提取工具调用轨迹"""
    pending = {}  # 暂存未匹配的调用ID
    seen = set()  # 已见的调用ID
    traces = []  # 工具调用轨迹
    for item in messages:
        # 1. 检查是否为 AIMessage
        if isinstance(item, AIMessage):
            # 2. 检查是否含有工具调用
            if item.invalid_tool_calls:
                raise ValueError("invalid tool call")
            for call in item.tool_calls:
                call_id = call.get("id")
                if not call_id or call_id in seen:
                    raise ValueError("invalid tool call id")
                # 3. 记录已见调用ID
                seen.add(call_id)
                # 4. 记录暂存未匹配的调用ID
                pending[call_id] = call
        # 5. 检查是否为 ToolMessage
        elif isinstance(item, ToolMessage):
            # 6. 检查是否匹配暂存未匹配的调用ID
            call = pending.pop(item.tool_call_id, None)
            if call is None:
                raise ValueError("unmatched tool result")
            # 7. 提取工具调用结果
            result = item.content if isinstance(item.content, str) else str(item.content)
            # 8. 记录工具调用轨迹
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
    # 9. 返回工具调用轨迹
    return traces


def extract_final_answer(messages: list[BaseMessage]) -> str:
    """从消息中提取最终答案"""
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
    """执行一次无会话持久化的 Agent 请求，并提取可信的最终答复和工具轨迹"""
    # 1. 校验用户输入
    validate_message(message)
    try:
        # 2. 创建模型和 Agent
        settings = get_settings()
        if model is None:
            model = build_chat_model(settings)
        agent = build_lead_agent(model, [calculate])
        # 3. 执行 Agent
        async with asyncio.timeout(settings.model_timeout_seconds):
            state = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config={"recursion_limit": 12},
            )
        # 4. 从状态中提取消息
        messages = state["messages"]
        # 5. 从消息中提取工具调用轨迹
        traces = extract_run_tool_traces(messages)
        # 6. 从消息中提取最终答案，并返回最终答案和工具调用轨迹
        return AgentResponse(answer=extract_final_answer(messages), tool_calls=traces)
    except ModelNotConfigured:
        raise
    except (TimeoutError, APITimeoutError):
        raise AgentExecutionError("MODEL_TIMEOUT", "Model request timed out") from None
    except APIError:
        raise AgentExecutionError("MODEL_UPSTREAM_ERROR", "Model provider request failed") from None
    except Exception:  # noqa: BLE001 - the public boundary must sanitize provider/framework errors
        raise AgentExecutionError("AGENT_EXECUTION_FAILED", "Agent execution failed") from None
