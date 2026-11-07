"""长工具文本真实引用/转存，不改变Command或失败语义。"""

import asyncio
import json

from langchain_core.messages import AIMessage
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import Upload, workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.lead import build_lead_agent
from minideerflow.tools.executor import ToolGuardMiddleware
from minideerflow.tools.output_budget import ToolOutputBudgetMiddleware
from minideerflow.tools.registry import ToolPolicy, ToolRegistry, register_builtin_tools


def test_large_read_is_preview_with_original_file_and_no_duplicate(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            raw = ("中文证据" * 3000).encode()
            file = await ws.upload(thread.id, Upload(raw, "notes.md"))
            reg = ToolRegistry()
            register_builtin_tools(reg)
            reg.freeze()
            policy = ToolPolicy(
                run.id, thread.id, reg.names, frozenset({"read", "write", "orchestrate"})
            )
            ctx = AgentRunContext(thread.id, run.id, ws, None, tool_policy=policy)
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": "read", "name": "read_text", "args": {"file_id": file.id}}
                        ],
                    ),
                    AIMessage(content="preview only"),
                ]
            )
            graph = build_lead_agent(
                model,
                reg.list_allowed(policy),
                context_schema=AgentRunContext,
                middleware=[ToolOutputBudgetMiddleware(), ToolGuardMiddleware(reg)],
            )
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": "read"}]}, context=ctx
            )
            from minideerflow.agents.service import extract_run_tool_traces

            trace = extract_run_tool_traces(result["messages"])[0]
            payload = json.loads(trace.result)
            assert payload["file_id"] == file.id and payload["original_bytes"] == len(raw)
            assert len(payload["preview"].encode()) <= 1024 and len(trace.result.encode()) < 2048
            assert len(await ws.list_files(thread.id)) == 1
            assert (await ws.read_text(thread.id, file.id)).encode() == raw

    asyncio.run(scenario())


def test_other_long_output_registers_downloadable_artifact(tmp_path):
    async def scenario():
        from langchain.tools import tool

        from minideerflow.tools.registry import ToolDefinition

        @tool
        async def long_result() -> str:
            """Return synthetic evidence."""
            return "evidence" * 3000

        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            reg = ToolRegistry()
            register_builtin_tools(reg)
            reg.register(
                ToolDefinition("long_result", long_result, "builtin", "read", 5, "builtin", "test")
            )
            reg.freeze()
            policy = ToolPolicy(
                run.id, thread.id, reg.names, frozenset({"read", "write", "orchestrate"})
            )
            ctx = AgentRunContext(thread.id, run.id, ws, None, tool_policy=policy)
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="", tool_calls=[{"id": "long", "name": "long_result", "args": {}}]
                    ),
                    AIMessage(content="ready"),
                ]
            )
            graph = build_lead_agent(
                model,
                reg.list_allowed(policy),
                context_schema=AgentRunContext,
                middleware=[ToolOutputBudgetMiddleware(), ToolGuardMiddleware(reg)],
            )
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": "evidence"}]}, context=ctx
            )
            from minideerflow.agents.service import extract_run_tool_traces

            trace = extract_run_tool_traces(result["messages"])[0]
            payload = json.loads(trace.result)
            data, _ = await ws.download_artifact(thread.id, payload["artifact_id"])
            assert data == ("evidence" * 3000).encode() and trace.ok and len(trace.result) < 2000

    asyncio.run(scenario())
