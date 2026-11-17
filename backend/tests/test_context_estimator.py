"""旧v1/v2历史列真实迁移，历史预估不覆盖Provider Token。"""

import asyncio

from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_old_sql_migration_retains_byte_totals_and_null_v2(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            old = await tracker.reserve("model", 1234)
            await tracker.finish(old, "ok")
            # 真正删除新列构造P06旧表，再运行同一幂等迁移，不伪造默认Token。
            async with repo.database.transaction() as conn:
                for table in ("run_usage", "usage_calls"):
                    for column in ("estimated_input_tokens_v2", "estimator_version"):
                        await conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
                await conn.execute("ALTER TABLE run_usage DROP COLUMN estimated_v2_calls")
                await conn.execute("UPDATE run_usage SET budget_json='{}'")
            await repo.database.init_schema()
            await repo.database.init_schema()
            migrated = await usage.get(run.id)
            assert migrated.estimated_input_tokens == 1234
            assert migrated.estimated_input_tokens_v2 is None and migrated.estimated_v2_calls == 0
            assert migrated.provider_input_tokens is None
            reservation = await tracker.reserve("model", 100, estimate_v2=100)
            await tracker.finish(reservation, "ok", {"input_tokens": 7, "output_tokens": 2})
            await tracker.finish(reservation, "ok", {"input_tokens": 7, "output_tokens": 2})
            value = await usage.get(run.id)
            assert value.estimated_input_tokens_v2 == 100
            assert value.estimated_input_tokens == 1234 + 100
            assert value.provider_input_tokens == 7 and value.estimated_v2_calls == 1

    asyncio.run(scenario())
