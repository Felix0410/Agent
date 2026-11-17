"""v2是明确版本化的保守预估；旧字节记录不重新解释成Token。"""

import asyncio

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.runtime.budget import (
    BudgetError,
    ConservativeContextEstimator,
    RunBudget,
    RunBudgetTracker,
    estimate_messages,
    estimate_tools,
)
from minideerflow.runtime.usage import UsageRepository


@pytest.mark.parametrize("text", ["中文合成资料" * 50, "Synthetic English material " * 50])
def test_versioned_estimate_is_deterministic_and_schema_counted_once(text):
    messages = [HumanMessage(content=text)]
    tools = [{"name": "synthetic", "parameters": {"description": "长JSON" * 300}}]
    system = SystemMessage(content="system")
    estimator = ConservativeContextEstimator()
    first = estimator.estimate(messages, tools, system)
    assert first == estimator.estimate(messages, tools, system)
    assert first.breakdown.total_bytes == estimate_messages(messages) + estimate_messages(
        [system]
    ) + estimate_tools(tools)
    assert first.estimator_version == "utf8_conservative_v2" and first.unit == "estimated_tokens_v2"
    assert (
        estimator.estimate([HumanMessage(content="short summary")], tools, system).estimated_tokens
        < first.estimated_tokens
    )


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
            estimate = tracker.estimator.estimate([HumanMessage(content="new")])
            reservation = await tracker.reserve_context(estimate)
            await tracker.finish(reservation, "ok", {"input_tokens": 7, "output_tokens": 2})
            await tracker.finish(reservation, "ok", {"input_tokens": 7, "output_tokens": 2})
            value = await usage.get(run.id)
            assert value.estimated_input_tokens_v2 == estimate.estimated_tokens
            assert value.estimated_input_tokens == 1234 + estimate.breakdown.total_bytes
            assert value.provider_input_tokens == 7 and value.estimated_v2_calls == 1

    asyncio.run(scenario())


def test_window_and_unknown_window_and_atomic_cumulative_budget(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(max_input_tokens_estimate=1500), usage)
            await tracker.initialize()
            estimate = tracker.estimator.estimate([HumanMessage(content="中" * 300)])
            tracker.model_context_window_tokens = 2200
            with pytest.raises(BudgetError) as error:
                await tracker.reserve_context(estimate)
            assert error.value.reason == "MODEL_CONTEXT_WINDOW_EXCEEDED"
            assert (await usage.get(run.id)).model_calls == 0
            tracker.model_context_window_tokens = None
            results = await asyncio.gather(
                tracker.reserve_context(estimate, "parent"),
                tracker.reserve_context(estimate, "child"),
                return_exceptions=True,
            )
            assert sum(isinstance(r, BudgetError) for r in results) == 1
            value = await usage.get(run.id)
            assert value.model_calls == 1 and value.estimated_v2_calls == 1
            assert value.estimated_input_tokens_v2 == estimate.estimated_tokens

    asyncio.run(scenario())
