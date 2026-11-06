"""用官方 SQLite Saver 与假模型证明记忆持久化和跨 Thread 隔离。"""

import asyncio
from pathlib import Path

from langchain_core.messages import AIMessage
from test_lead import ScriptedModel

from minideerflow.agents.lead import build_lead_agent
from minideerflow.runtime.checkpoints import open_checkpointer, thread_config


def test_checkpoint_reopen_and_thread_isolation(tmp_path: Path) -> None:
    async def scenario():
        path = tmp_path / "nested/checkpoints.db"
        config = thread_config("thread-one")
        assert config == {"configurable": {"thread_id": "thread-one"}, "recursion_limit": 12}
        # 1. 同一 Thread 连续调用由 Graph 自己合并消息，不从 Run 表拼接历史。
        async with open_checkpointer(path) as saver:
            assert saver.serde.pickle_fallback is False
            assert saver.serde._allowed_msgpack_modules is not True
            model = ScriptedModel(
                responses=[AIMessage(content="first"), AIMessage(content="second")]
            )
            agent = build_lead_agent(model, [], checkpointer=saver)
            await agent.ainvoke(
                {"messages": [{"role": "user", "content": "remember this"}]}, config
            )
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "continue"}]}, config
            )
            assert [m.content for m in result["messages"]] == [
                "remember this",
                "first",
                "continue",
                "second",
            ]
            assert [m.content for m in model.seen[1]][1:] == ["remember this", "first", "continue"]
        # 2. 原连接已退出；重新打开文件仍能读取已保存的同一 Thread。
        async with open_checkpointer(path) as reopened:
            model = ScriptedModel(responses=[AIMessage(content="third")])
            agent = build_lead_agent(model, [], reopened)
            state = await agent.aget_state(config)
            assert len(state.values["messages"]) == 4
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "after restart"}]}, config
            )
            assert len(result["messages"]) == 6
            assert [m.content for m in model.seen[0]][1:] == [
                "remember this",
                "first",
                "continue",
                "second",
                "after restart",
            ]
            # 3. 另一 Thread 只有自己的消息，不能继承上个会话上下文。
            other = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "separate"}]}, thread_config("thread-two")
            )
            assert [m.content for m in other["messages"]] == ["separate", "third"]
            assert len((await agent.aget_state(config)).values["messages"]) == 6

    asyncio.run(scenario())


def test_checkpoint_preserves_actual_tool_messages(tmp_path: Path) -> None:
    from langchain_core.messages import ToolMessage

    from minideerflow.tools.calculator import calculate

    async def scenario():
        path = tmp_path / "tool-checkpoints.db"
        config = thread_config("tool-thread")
        async with open_checkpointer(path) as saver:
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "saved-call",
                                "name": "calculate",
                                "args": {"expression": "(12+8)*3"},
                            }
                        ],
                    ),
                    AIMessage(content="60"),
                ]
            )
            agent = build_lead_agent(model, [calculate], saver)
            await agent.ainvoke({"messages": [{"role": "user", "content": "calculate"}]}, config)
        async with open_checkpointer(path) as saver:
            agent = build_lead_agent(
                ScriptedModel(responses=[AIMessage(content="ok")]), [calculate], saver
            )
            messages = (await agent.aget_state(config)).values["messages"]
            tools = [m for m in messages if isinstance(m, ToolMessage)]
            assert len(tools) == 1
            assert tools[0].tool_call_id == "saved-call"
            assert tools[0].content == "60"
            assert messages[-1].content == "60"

    asyncio.run(scenario())
