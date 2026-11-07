"""同一invocation不能重复入账；缺少usage为NULL。"""

import asyncio

from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_provider_null_estimate_and_unique_final(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            assert (await usage.get(run.id)).provider_input_tokens is None
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            first = await tracker.reserve("model", 40)
            await tracker.finish(first, "ok", {"input_tokens": 7, "output_tokens": 3})
            await tracker.finish(first, "ok", {"input_tokens": 7, "output_tokens": 3})
            second = await tracker.reserve("model", 20, "child")
            await tracker.finish(second, "error")
            result = await usage.get(run.id)
            assert (
                result.model_calls == 2
                and result.provider_input_tokens == 7
                and result.provider_output_tokens == 3
            )
            assert result.estimated_input_tokens == 60 and result.usage_unknown_calls == 1

    asyncio.run(scenario())
