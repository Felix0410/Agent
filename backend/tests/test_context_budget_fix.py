"""专项预算修复：真实SQL/Graph，模型和外部来源只用合成Fake。"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.context_manager import ContextManager
from minideerflow.agents.middleware import UsageBudgetMiddleware
from minideerflow.config import Settings
from minideerflow.runtime.budget import BudgetError, RunBudget, RunBudgetTracker, budget_breakdown
from minideerflow.runtime.usage import UsageRepository


def test_budget_configuration_bounds():
    settings = Settings()
    assert (settings.context_soft_limit_estimate, settings.context_hard_limit_estimate) == (
        24000,
        48000,
    )
    assert settings.run_max_input_tokens_estimate == 480000
    Settings(
        context_soft_limit_estimate=96000,
        context_hard_limit_estimate=128000,
        run_max_input_tokens_estimate=1000000,
    )
    for override in (
        {"context_soft_limit_estimate": 96001},
        {"context_hard_limit_estimate": 128001},
        {"run_max_input_tokens_estimate": 1000001},
        {"context_soft_limit_estimate": 48000},
    ):
        with pytest.raises(ValidationError):
            Settings(**override)


def test_initial_overhead_fails_without_summary_and_persists_numbers(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            manager = ContextManager(100, 500, tools=[{"description": "s" * 600}])
            manager.system_message = SystemMessage(content="private-system")
            ctx = AgentRunContext(thread.id, run.id, ws, None, budget_tracker=tracker)
            with pytest.raises(BudgetError) as error:
                await manager.prepare(
                    [HumanMessage(content="private-user")],
                    ctx,
                    lambda: pytest.fail("must not summarize"),
                )
            assert error.value.reason == "BASE_OVERHEAD_EXCEEDS_HARD_LIMIT"
            result = await usage.get(run.id)
            assert result.model_calls == 0
            assert result.context_breakdown["total_bytes"] > 500
            assert "private" not in str(result.model_dump())
            assert result.estimate_unit == "utf8_json_bytes_v1"

    asyncio.run(scenario())


@pytest.mark.parametrize("source", ["parent", "child"])
def test_parent_and_child_follow_shared_hard_limit(tmp_path, source):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            usage = UsageRepository(repo.database)
            tracker = RunBudgetTracker(run.id, RunBudget(), usage)
            await tracker.initialize()
            calls = []

            async def handler(request):
                calls.append(request)
                return SimpleNamespace(result=[])

            request = SimpleNamespace(
                runtime=SimpleNamespace(context=SimpleNamespace(budget_tracker=tracker)),
                messages=[HumanMessage(content="x" * 20000)],
                tools=[],
                system_message=SystemMessage(content="system"),
            )
            await UsageBudgetMiddleware(source).awrap_model_call(request, handler)
            tracker.context_hard_limit = 19000
            with pytest.raises(BudgetError):
                await UsageBudgetMiddleware(source).awrap_model_call(request, handler)
            result = await usage.get(run.id)
            assert len(calls) == 1 and result.model_calls == 1
            assert result.provider_input_tokens is None
            assert result.context_breakdown["reason"] == "ACTIVE_MESSAGES"

    asyncio.run(scenario())


def test_breakdown_includes_each_component_once():
    value = budget_breakdown(
        [HumanMessage(content="中文 hello")], [{"name": "tool"}], SystemMessage(content="system")
    )
    assert value.total_bytes == value.system_bytes + value.message_bytes + value.tool_schema_bytes
    assert value.estimator == "utf8_json_bytes_v1"
