"""只转换 Graph 的实际本轮消息；不负责调度或业务数据库写入。"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from minideerflow.agents.service import (
    AgentResponse,
    extract_final_answer,
    extract_run_tool_traces,
)
from minideerflow.runtime.checkpoints import thread_config

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


async def stream_agent(
    agent: Any, thread_id: str, message: str, event_sink: EventSink | None = None
) -> AgentResponse:
    """以框架流执行一次 Run，只验收当前新增消息，排除 Checkpoint 的旧历史。"""
    config = thread_config(thread_id)
    # 1. 用运行前已保存的消息 ID 划出本轮边界，不从 Run 表拼接模型上下文。
    previous = await agent.aget_state(config)
    old_ids = {m.id for m in previous.values.get("messages", []) if m.id}
    current: list[BaseMessage] = []
    indexed: dict[str, BaseMessage] = {}
    # 2. updates 包含完成的模型/工具消息；messages 增量将在 C 映射为 SSE。
    async for mode, data in agent.astream(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
        stream_mode=["messages", "updates"],
    ):
        if mode != "updates":
            continue
        for update in data.values():
            if not isinstance(update, dict):
                continue
            for item in update.get("messages", []):
                if not isinstance(item, (AIMessage, ToolMessage)) or item.id in old_ids:
                    continue
                if not item.id:
                    raise ValueError("missing graph message id")
                if item.id in indexed:
                    if indexed[item.id] != item:
                        raise ValueError("inconsistent repeated message")
                    continue
                indexed[item.id] = item
                current.append(item)
    # 3. 以最终已保存状态复核本轮最后消息，不能把历史 AIMessage 当成新答案。
    state = await agent.aget_state(config)
    saved = state.values.get("messages", [])
    if not saved or not current or saved[-1].id != current[-1].id or saved[-1] != current[-1]:
        raise ValueError("no current final state")
    traces = extract_run_tool_traces(current)
    return AgentResponse(answer=extract_final_answer(current), tool_calls=traces)
