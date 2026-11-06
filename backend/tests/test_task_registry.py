"""并发/次数/取消/启动核查的真实局部验证。"""

import asyncio

import pytest
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext
from minideerflow.agents.subagents.dispatcher import TaskDispatcher
from minideerflow.agents.subagents.models import TaskStatus
from minideerflow.config import Settings
from minideerflow.runtime.plan_repository import PlanError, PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.task_registry import TaskRegistry


def test_three_running_four_total_and_per_run_isolation():
    async def scenario():
        registry = TaskRegistry()
        gate = asyncio.Event()
        running = 0
        peak = 0
        entered = asyncio.Event()

        async def work(sem):
            nonlocal running, peak
            async with sem:
                running += 1
                peak = max(peak, running)
                if running == 3:
                    entered.set()
                try:
                    await gate.wait()
                finally:
                    running -= 1
                return "done"

        calls = [asyncio.create_task(registry.run("one", work)) for _ in range(4)]
        await asyncio.wait_for(entered.wait(), 1)
        assert running == 3 and not calls[3].done()
        with pytest.raises(PlanError, match="SUBTASK_LIMIT"):
            await registry.run("one", work)

        async def independent(sem):
            return "second run"

        assert await registry.run("two", independent) == "second run"
        gate.set()
        assert await asyncio.gather(*calls) == ["done"] * 4
        assert peak == 3 and running == 0
        await registry.shutdown()
        assert registry._runs == {}

    asyncio.run(scenario())


def test_timeout_queued_cancellation_and_no_live_tasks(tmp_path, monkeypatch):
    async def scenario():
        from minideerflow.agents.subagents import executor

        entered = asyncio.Event()
        original = executor.create_agent

        class Slow:
            async def ainvoke(self, *args, **kwargs):
                entered.set()
                await asyncio.Event().wait()

        monkeypatch.setattr(executor, "create_agent", lambda *a, **k: Slow())
        async with workspace(tmp_path) as (ws, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            registry = TaskRegistry(concurrency=1)
            dispatcher = TaskDispatcher(plans, lambda: None, registry, timeout=0.02)
            ctx = AgentRunContext(
                thread.id, run.id, ws, PlanService(plans), task_dispatcher=dispatcher
            )
            first = await dispatcher.dispatch(ctx, "general", "timeout")
            assert first.status == "TIMED_OUT" and first.error_code == "SUBTASK_TIMEOUT"
            dispatcher.timeout = 10
            active = asyncio.create_task(dispatcher.dispatch(ctx, "general", "cancel active"))
            await entered.wait()
            queued = asyncio.create_task(dispatcher.dispatch(ctx, "general", "cancel queued"))
            async with asyncio.timeout(1):
                while len(await plans.list_subtasks(run.id)) < 3:
                    await asyncio.sleep(0.001)
            await registry.close_run(run.id)
            await asyncio.gather(active, queued, return_exceptions=True)
            records = await plans.list_subtasks(run.id)
            assert [r.status for r in records] == ["TIMED_OUT", "CANCELLED", "FAILED"]
            assert records[2].started_at is None
            assert registry._runs == {}
        monkeypatch.setattr(executor, "create_agent", original)

    asyncio.run(scenario())


def test_startup_orphans_and_irreversible_terminal(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (_, repo, _):
            thread = await repo.create_thread()
            run = await active_run(repo, thread)
            plans = PlanRepository(repo.database)
            a = await plans.create_subtask(run.id, thread.id, "general", "pending")
            b = await plans.create_subtask(run.id, thread.id, "research", "running")
            await plans.transition_subtask(b.id, run.id, thread.id, TaskStatus.RUNNING)
            assert await plans.reconcile_orphaned_subtasks() == 2
            records = await plans.list_subtasks(run.id)
            assert all(
                t.status == "FAILED" and t.error_code == "SUBTASK_INTERRUPTED" for t in records
            )
            with pytest.raises(PlanError):
                await plans.transition_subtask(a.id, run.id, thread.id, TaskStatus.RUNNING)
            assert await plans.reconcile_orphaned_subtasks() == 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_timeout_seconds", 151),
        ("subagent_timeout_seconds", 36),
        ("max_subagent_concurrency", 4),
        ("max_subagent_calls_per_run", 5),
        ("subagent_recursion_limit", 15),
    ],
)
def test_budget_bounds(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(**{field: value})
