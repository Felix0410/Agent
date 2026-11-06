"""真正通过LangChain ToolRuntime运行文件工具，模型只提供业务参数。"""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from test_lead import ScriptedModel
from test_workspace import Upload, workspace

from minideerflow.agents.lead import build_lead_agent
from minideerflow.runtime.checkpoints import open_checkpointer
from minideerflow.runtime.models import RunStatus
from minideerflow.runtime.streaming import stream_agent
from minideerflow.tools.file_tools import list_files, read_text, write_text
from minideerflow.workspace.models import WorkspaceContext


async def active_run(runtime, thread):
    run = await runtime.create_run(thread.id, "file tools")
    await runtime.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
    return run


def test_public_tool_schemas_hide_all_identity_and_paths():
    assert list_files.tool_call_schema.model_json_schema()["properties"] == {}
    assert set(read_text.tool_call_schema.model_json_schema()["properties"]) == {"file_id"}
    assert set(write_text.tool_call_schema.model_json_schema()["properties"]) == {
        "filename",
        "content",
    }


def test_runtime_real_list_read_write_and_tool_ids(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            run = await active_run(runtime, thread)
            file = await service.upload(thread.id, Upload("临时笔记".encode(), "notes.md"))
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="", tool_calls=[{"id": "list", "name": "list_files", "args": {}}]
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"id": "read", "name": "read_text", "args": {"file_id": file.id}}
                        ],
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "write",
                                "name": "write_text",
                                "args": {"filename": "summary.md", "content": "临时摘要"},
                            }
                        ],
                    ),
                    AIMessage(content="created"),
                ]
            )
            async with open_checkpointer(tmp_path / "checkpoint.db") as saver:
                agent = build_lead_agent(
                    model,
                    [list_files, read_text, write_text],
                    saver,
                    context_schema=WorkspaceContext,
                )
                response = await stream_agent(
                    agent,
                    thread.id,
                    "summarize",
                    context=WorkspaceContext(thread.id, run.id, service),
                )
            assert [t.name for t in response.tool_calls] == [
                "list_files",
                "read_text",
                "write_text",
            ]
            assert response.tool_calls[1].result == "临时笔记"
            assert all(t.ok for t in response.tool_calls)
            tools = [m for m in model.seen[-1] if isinstance(m, ToolMessage)]
            assert [m.tool_call_id for m in tools] == ["list", "read", "write"]
            artifact = json.loads(response.tool_calls[2].result)
            data, metadata = await service.download_artifact(thread.id, artifact["artifact_id"])
            assert data == "临时摘要".encode() and metadata.display_name == "summary.md"
            assert str(storage.root) not in str(response.model_dump())

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode", ["cross_thread", "pdf", "large", "invalid_name", "forged_arg", "forged_context"]
)
def test_scoped_tool_failures_are_not_success(tmp_path, mode):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, _storage):
            thread = await runtime.create_thread()
            other = await runtime.create_thread()
            run = await active_run(runtime, thread)
            upload_thread = other if mode == "cross_thread" else thread
            payload = b"%PDF-x" if mode == "pdf" else b"x" * 65537 if mode == "large" else b"notes"
            file = await service.upload(
                upload_thread.id, Upload(payload, "notes.pdf" if mode == "pdf" else "notes.md")
            )
            name, args = "read_text", {"file_id": file.id}
            if mode == "invalid_name":
                name, args = "write_text", {"filename": "../escape.md", "content": "x"}
            if mode == "forged_arg":
                args["thread_id"] = other.id
            context = WorkspaceContext(
                other.id if mode == "forged_context" else thread.id, run.id, service
            )
            model = ScriptedModel(
                responses=[
                    AIMessage(
                        content="", tool_calls=[{"id": "unsafe", "name": name, "args": args}]
                    ),
                    AIMessage(content="cannot perform operation"),
                ]
            )
            async with open_checkpointer(tmp_path / "checkpoint.db") as saver:
                agent = build_lead_agent(
                    model,
                    [list_files, read_text, write_text],
                    saver,
                    context_schema=WorkspaceContext,
                )
                response = await stream_agent(
                    agent, thread.id, "test unsafe input", context=context
                )
            assert response.tool_calls[0].ok is False
            assert await service.list_artifacts(thread.id) == []

    asyncio.run(scenario())


def test_p01_single_round_does_not_register_file_tools():
    from pydantic import Field

    from minideerflow.agents.service import run_agent_once

    class InspectTools(ScriptedModel):
        names: list[str] = Field(default_factory=list)

        def bind_tools(self, tools, **kwargs):
            self.names = [tool.name for tool in tools]
            return self

    model = InspectTools(responses=[AIMessage(content="plain response")])
    response = asyncio.run(run_agent_once("hello", model=model))
    assert response.answer == "plain response"
    assert model.names == ["calculate"]
