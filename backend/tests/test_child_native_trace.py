"""Child已完成工具被原生摘要后，来源与错误仍从真实回执观察恢复。"""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_file_tools import active_run
from test_lead import ScriptedModel
from test_workspace import Upload, workspace

from minideerflow.agents.context import ChildContext
from minideerflow.agents.subagents.config import SPECS
from minideerflow.agents.subagents.executor import execute_child
from minideerflow.config import Settings
from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository
from minideerflow.tools.calculator import calculate
from minideerflow.tools.file_tools import read_text


@pytest.mark.parametrize("failed_read", [False, True])
def test_child_summary_keeps_real_source_and_failure(tmp_path, failed_read):
    class ChildModel(ScriptedModel):
        async def _agenerate(self, messages, **kwargs):
            if not any(m.type == "system" for m in messages):
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=AIMessage(content="Synthetic data, no new permissions.")
                        )
                    ]
                )
            return await super()._agenerate(messages, **kwargs)

    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            file = await ws.upload(thread.id, Upload(b"x" * 5000, "synthetic.md"))
            model = ChildModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "read_text",
                                "id": "read",
                                "args": {"file_id": "missing" if failed_read else file.id},
                            }
                        ],
                    ),
                    *[
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "calculate",
                                    "id": f"calc{n}",
                                    "args": {"expression": "1+2"},
                                }
                            ],
                        )
                        for n in range(2)
                    ],
                    AIMessage(content="synthetic result"),
                ]
            )
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            context = ChildContext(thread.id, run.id, ws, budget_tracker=tracker)
            settings = Settings(
                summarization_trigger_tokens=128,
                summarization_trigger_messages=3,
                summarization_keep_messages=2,
            )
            result = await execute_child(
                SPECS["general"],
                "read synthetic file",
                context,
                lambda: model,
                [read_text, calculate],
                "synthetic-task",
                settings=settings,
            )
            value = await usage.get(run.id)
            assert value.compaction_count >= 1 and value.summary_calls >= 1
            if failed_read:
                assert result.status == "FAILED" and result.error_code == "SUBTASK_TOOL_ERROR"
            else:
                assert result.status == "COMPLETED" and result.source_file_ids == [file.id]
            assert value.tool_calls == 3

    asyncio.run(scenario())
