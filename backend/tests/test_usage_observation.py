"""移除旧门禁后，大请求仍记录；取消和真实Deadline继续生效。"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.agents.middleware import ModelUsageMiddleware
from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_large_request_is_observed_not_blocked(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(max_input_tokens_estimate=1), usage)
            await tracker.initialize()
            called = []

            async def handler(request):
                called.append(request)
                return SimpleNamespace(result=[])

            request = SimpleNamespace(
                runtime=SimpleNamespace(context=SimpleNamespace(budget_tracker=tracker)),
                messages=[HumanMessage(content="中文" * 15000)],
                tools=[{"description": "x" * 60000}],
                system_message=SystemMessage(content="synthetic system"),
            )
            await ModelUsageMiddleware().awrap_model_call(request, handler)
            result = await usage.get(run.id)
            assert len(called) == 1 and result.estimated_input_tokens > 48000
            assert result.provider_input_tokens is None
            assert result.estimated_input_tokens_v2 is None
            assert result.context_breakdown["reason"] == "OBSERVATION_ONLY"
            tracker.cancelled.set()
            with pytest.raises(asyncio.CancelledError):
                await tracker.reserve("tool")
            tracker.cancelled.clear()
            tracker.started -= 601
            with pytest.raises(TimeoutError):
                await tracker.check()

    asyncio.run(scenario())
