"""只转换 Graph 的实际本轮消息；不负责调度或业务数据库写入。"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage

from minideerflow.agents.service import (
    AgentResponse,
    extract_final_answer,
    extract_run_tool_traces,
)
from minideerflow.runtime.checkpoints import thread_config

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


async def stream_agent(
    agent: Any,
    thread_id: str,
    message: str,
    event_sink: EventSink | None = None,
    *,
    on_graph_start: Callable[[], None] | None = None,
    context: Any | None = None,
) -> AgentResponse:
    """以框架流执行一次 Run，只验收当前新增消息，排除 Checkpoint 的旧历史。"""
    config = thread_config(thread_id)
    # 1. 用运行前已保存的消息 ID 划出本轮边界，不从 Run 表拼接模型上下文。
    previous = await agent.aget_state(config)
    old_ids = {m.id for m in previous.values.get("messages", []) if m.id}
    current: list[BaseMessage] = []
    indexed: dict[str, BaseMessage] = {}
    calls: dict[str, dict] = {}
    completed: set[str] = set()

    async def emit(kind: str, payload: dict[str, Any]) -> None:
        if event_sink is not None:
            await event_sink(kind, payload)

    # 2. messages 只转换真实模型文本，updates 才发出完整工具调用/回执。
    # 读取历史失败还没开始写 Graph；到这个边界才通知 Runner 标记执行已进入。
    if on_graph_start is not None:
        on_graph_start()
    async for mode, data in agent.astream(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
        stream_mode=["messages", "updates"],
        context=context,
    ):
        if mode == "messages":
            chunk, metadata = data
            if (
                isinstance(chunk, (AIMessage, AIMessageChunk))
                and metadata.get("langgraph_node") == "model"
                and chunk.id
                and chunk.id not in old_ids
                and not chunk.tool_calls
                and not getattr(chunk, "tool_call_chunks", [])
                and not chunk.invalid_tool_calls
                and chunk.text
            ):
                await emit("assistant_delta", {"message_id": chunk.id, "text": chunk.text})
            continue
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
                if isinstance(item, AIMessage):
                    if item.invalid_tool_calls:
                        raise ValueError("invalid tool call")
                    for call in item.tool_calls:
                        call_id = call.get("id")
                        if not call_id or call_id in calls:
                            raise ValueError("duplicate tool call id")
                        calls[call_id] = call
                        await emit(
                            "tool_start",
                            {
                                "tool_call_id": call_id,
                                "name": call["name"],
                                "args": call["args"],
                            },
                        )
                else:
                    call = calls.get(item.tool_call_id)
                    if call is None or item.tool_call_id in completed:
                        raise ValueError("unmatched or repeated tool result")
                    completed.add(item.tool_call_id)
                    result = item.content if isinstance(item.content, str) else str(item.content)
                    await emit(
                        "tool_end",
                        {
                            "tool_call_id": item.tool_call_id,
                            "name": call["name"],
                            "result": result,
                            "ok": item.status != "error" and not result.startswith("ERROR["),
                        },
                    )
    # 3. 以最终已保存状态复核本轮最后消息，不能把历史 AIMessage 当成新答案。
    state = await agent.aget_state(config)
    saved = state.values.get("messages", [])
    if not saved or not current or saved[-1].id != current[-1].id or saved[-1] != current[-1]:
        raise ValueError("no current final state")
    traces = extract_run_tool_traces(current)
    return AgentResponse(answer=extract_final_answer(current), tool_calls=traces)
