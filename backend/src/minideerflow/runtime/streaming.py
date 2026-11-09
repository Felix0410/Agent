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
    initial_state_extra: dict | None = None,
    recursion_limit: int | None = None,
) -> AgentResponse:
    """以流式方式执行智能体，只验收当前新增消息，排除 Checkpoint 的旧历史。"""
    # 1. 配置 Thread RunnableConfig，确保每个 Thread 有独立的检查点，以及递归限制。
    config = thread_config(thread_id)
    if recursion_limit is not None:
        config["recursion_limit"] = recursion_limit
    # 2. 读取当前 Thread 的历史消息。
    previous = await agent.aget_state(config)
    old_ids = {m.id for m in previous.values.get("messages", []) if m.id}
    # 3. 初始化本轮消息列表，用于存储新增消息。
    current: list[BaseMessage] = []
    indexed: dict[str, BaseMessage] = {}
    calls: dict[str, dict] = {}
    completed: set[str] = set()

    # 4. 定义事件发射函数，用于向外部发送模型文本和工具调用。
    async def emit(kind: str, payload: dict[str, Any]) -> None:
        if event_sink is not None:
            await event_sink(kind, payload)

    # 5. 执行智能体，开始流式输出。
    if on_graph_start is not None:
        on_graph_start()
    async for mode, data in agent.astream(
        {**(initial_state_extra or {}), "messages": [{"role": "user", "content": message}]},
        config=config,
        stream_mode=["messages", "updates"],
        context=context,
    ):
        # 5.A 处理模型文本消息。
        if mode == "messages":
            # 拆分实际数据和元数据
            chunk, metadata = data
            if (
                isinstance(chunk, (AIMessage, AIMessageChunk))  # 确保是模型文本消息
                and metadata.get("langgraph_node") == "model"  # 确保消息来源是模型节点
                and chunk.id  # 确保消息ID有效
                and chunk.id not in old_ids
                and not chunk.tool_calls  # 确保不包含工具调用
                and not getattr(chunk, "tool_call_chunks", [])
                and not chunk.invalid_tool_calls
                and chunk.text  # 确保消息文本有效
            ):
                await emit("assistant_delta", {"message_id": chunk.id, "text": chunk.text})
            continue
        # 5.B 处理模型更新消息。
        if mode != "updates":
            continue
        # 5.B.1 遍历所有节点的状态更新
        for update in data.values():
            if not isinstance(update, dict):
                continue
            # 5.B.2 逐个处理每个节点的新增消息
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
                # 5.B.3 模型请求工具调用导致的更新
                if isinstance(item, AIMessage):
                    if item.invalid_tool_calls:
                        raise ValueError("invalid tool call")
                    # 5.B.3.1 获取每个工具调用请求
                    for call in item.tool_calls:
                        call_id = call.get("id")
                        # 5.B.3.2 防止重复工具调用
                        if not call_id or call_id in calls:
                            raise ValueError("duplicate tool call id")
                        # 5.B.3.3 存储工具调用请求
                        calls[call_id] = call
                        # 5.B.3.4 发送工具调用开始事件
                        await emit(
                            "tool_start",
                            {
                                "tool_call_id": call_id,
                                "name": call["name"],
                                "args": call["args"],
                            },
                        )
                # 5.B.4 工具调用结果导致的更新
                else:
                    # 5.B.4.1 获取工具调用
                    call = calls.get(item.tool_call_id)
                    # 5.B.4.2 检查工具调用是否异常
                    if call is None or item.tool_call_id in completed:
                        raise ValueError("unmatched or repeated tool result")
                    # 5.B.4.3 标记工具调用为已完成
                    completed.add(item.tool_call_id)
                    # 5.B.4.4 发送工具调用结束事件
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
    # 6. 获取最终状态
    state = await agent.aget_state(config)
    saved = state.values.get("messages", [])
    # 7. 检查最终状态是否与当前状态一致
    if not saved or not current or saved[-1].id != current[-1].id or saved[-1] != current[-1]:
        raise ValueError("no current final state")
    # 8. 提取工具调用轨迹
    traces = extract_run_tool_traces(current)
    # 9. 返回最终答案和工具调用轨迹
    return AgentResponse(answer=extract_final_answer(current), tool_calls=traces)
