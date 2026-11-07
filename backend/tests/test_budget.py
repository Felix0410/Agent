"""原子共享预算的真实SQL/Fake验证。"""

import asyncio

import pytest
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.runtime.budget import BudgetError, RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_concurrent_reservation_never_exceeds(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(max_model_calls=3), usage)
            await tracker.initialize()
            results = await asyncio.gather(
                *(tracker.reserve("model", 10, "child") for _ in range(8)), return_exceptions=True
            )
            assert sum(not isinstance(r, Exception) for r in results) == 3
            assert (await usage.get(run.id)).model_calls == 3
            with pytest.raises(BudgetError):
                await tracker.reserve("tool")

    asyncio.run(scenario())
