"""原子共享预算的真实SQL/Fake验证。"""

import asyncio

from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_concurrent_observation_never_blocks_or_loses_counts(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(max_model_calls=3), usage)
            await tracker.initialize()
            results = await asyncio.gather(
                *(tracker.reserve("model", 20000, "child") for _ in range(45)),
                return_exceptions=True,
            )
            assert sum(not isinstance(r, Exception) for r in results) == 45
            assert (await usage.get(run.id)).model_calls == 45
            await asyncio.gather(*(tracker.reserve("tool") for _ in range(35)))
            value = await usage.get(run.id)
            assert value.tool_calls == 35 and value.estimated_input_tokens == 900000
            assert value.budget["mode"] == "observe_only"

    asyncio.run(scenario())
