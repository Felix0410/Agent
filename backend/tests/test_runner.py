"""有界后台执行的局部测试：临时库、Fake 模型，不消费额度。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from test_lead import ScriptedModel

from minideerflow.config import Settings
from minideerflow.runtime.checkpoints import open_checkpointer
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import RunStatus
from minideerflow.runtime.repository import RepositoryError, RuntimeRepository
from minideerflow.runtime.runner import RunService, RunServiceError


def fake_factory(settings):
    return ScriptedModel(responses=[AIMessage(content="answer")])


@asynccontextmanager
async def running_service(tmp_path: Path, factory=fake_factory, **settings):
    db = await RuntimeDatabase.open(tmp_path / "runtime.db")
    await db.init_schema()
    repo = RuntimeRepository(db)
    async with open_checkpointer(tmp_path / "checkpoints.db") as saver:
        service = RunService(repo, saver, Settings(**settings), model_factory=factory)
        service.start()
        try:
            yield service, repo
        finally:
            await service.shutdown(grace_seconds=0.05)
    await db.close()


async def finished(service):
    await asyncio.wait_for(service.queue.join(), 3)


def test_success_and_real_checkpoint_multi_turn(tmp_path: Path) -> None:
    async def scenario():
        models = []

        def factory(settings):
            model = fake_factory(settings)
            models.append(model)
            return model

        async with running_service(tmp_path, factory) as (service, repo):
            first = await repo.create_thread()
            accepted = await service.start_run(first.id, "remember")
            assert accepted.status == "CREATED"
            await finished(service)
            run = await repo.get_run(accepted.run_id)
            assert run.status == RunStatus.SUCCEEDED and run.answer == "answer"
            await service.start_run(first.id, "continue")
            await finished(service)
            # 第二轮模型实际看见第一轮的 Human/AI，而不是仅检查 Run 表记录。
            assert [m.content for m in models[-1].seen[0]][1:] == ["remember", "answer", "continue"]
            other = await repo.create_thread()
            await service.start_run(other.id, "independent")
            await finished(service)
            assert [m.content for m in models[-1].seen[0]][1:] == ["independent"]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("expression", "result", "ok"),
    [
        ("(12+8)*3", "60", True),
        ("1/0", "ERROR[CALC_DIV_ZERO]: division by zero", False),
    ],
)
def test_tool_trace_current_run_only(tmp_path, expression, result, ok):
    def factory(settings):
        return ScriptedModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-" + expression,
                            "name": "calculate",
                            "args": {"expression": expression},
                        }
                    ],
                ),
                AIMessage(content="done"),
            ]
        )

    async def scenario():
        async with running_service(tmp_path, factory) as (service, repo):
            thread = await repo.create_thread()
            accepted = await service.start_run(thread.id, "calculate")
            await finished(service)
            run = await repo.get_run(accepted.run_id)
            assert run.status == RunStatus.SUCCEEDED
            assert run.tool_calls[0].result == result and run.tool_calls[0].ok is ok
            service.model_factory = fake_factory
            second = await service.start_run(thread.id, "ordinary question")
            await finished(service)
            assert (await repo.get_run(second.run_id)).tool_calls == []

    asyncio.run(scenario())


def test_queue_capacity_and_busy_priority(tmp_path, monkeypatch):
    from minideerflow.runtime import runner

    original = runner.stream_agent

    async def scenario():
        gate = asyncio.Event()
        started = 0

        async def blocked(*args, **kwargs):
            nonlocal started
            started += 1
            await gate.wait()
            return await original(*args, **kwargs)

        monkeypatch.setattr(runner, "stream_agent", blocked)
        async with running_service(tmp_path) as (service, repo):
            threads = [await repo.create_thread() for _ in range(11)]
            for thread in threads[:2]:
                await service.start_run(thread.id, "blocked")
            async with asyncio.timeout(2):
                while started < 2:
                    await asyncio.sleep(0.001)
            for thread in threads[2:10]:
                await service.start_run(thread.id, "queued")
            assert service.queue.qsize() == 8
            with pytest.raises(RepositoryError) as error:
                await service.start_run(threads[0].id, "duplicate")
            assert error.value.code == "THREAD_BUSY"
            with pytest.raises(RunServiceError) as error:
                await service.start_run(threads[10].id, "overflow")
            assert error.value.code == "RUN_QUEUE_FULL"
            assert await repo.list_runs(threads[10].id) == []
            gate.set()
            await finished(service)

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["timeout", "invalid_final", "upstream"])
def test_failure_and_recovery(tmp_path, monkeypatch, mode):
    import httpx2
    from openai import APIConnectionError

    from minideerflow.runtime import runner

    async def broken(*args, **kwargs):
        if mode == "timeout":
            await asyncio.sleep(1)
        if mode == "upstream":
            raise APIConnectionError(
                message="private-secret", request=httpx2.Request("POST", "http://localhost")
            )
        raise ValueError("private-secret")

    monkeypatch.setattr(runner, "stream_agent", broken)

    async def scenario():
        async with running_service(tmp_path, model_timeout_seconds=0.02) as (service, repo):
            thread = await repo.create_thread()
            accepted = await service.start_run(thread.id, "fail")
            await finished(service)
            run = await repo.get_run(accepted.run_id)
            assert run.status == RunStatus.FAILED and run.answer is None
            assert (
                run.error_code
                == {
                    "timeout": "MODEL_TIMEOUT",
                    "invalid_final": "AGENT_EXECUTION_FAILED",
                    "upstream": "MODEL_UPSTREAM_ERROR",
                }[mode]
            )
            assert (await repo.get_thread(thread.id)).needs_recovery

    asyncio.run(scenario())


def test_no_final_ai_message_cannot_succeed(tmp_path):
    async def scenario():
        async with running_service(
            tmp_path, lambda s: ScriptedModel(responses=[AIMessage(content="")])
        ) as (service, repo):
            thread = await repo.create_thread()
            accepted = await service.start_run(thread.id, "empty reply")
            await finished(service)
            assert (await repo.get_run(accepted.run_id)).status == RunStatus.FAILED

    asyncio.run(scenario())


def test_shutdown_cleans_workers_and_queued_runs(tmp_path, monkeypatch):
    from minideerflow.runtime import runner

    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(runner, "stream_agent", blocked)

    async def scenario():
        async with running_service(tmp_path, run_max_concurrency=1) as (service, repo):
            first, second = await repo.create_thread(), await repo.create_thread()
            active = await service.start_run(first.id, "active")
            async with asyncio.timeout(2):
                while (await repo.get_run(active.run_id)).status != RunStatus.RUNNING:
                    await asyncio.sleep(0.001)
            queued = await service.start_run(second.id, "queued")
            workers = list(service._workers)
            await service.shutdown(grace_seconds=0.01)
            assert all(task.done() for task in workers)
            for accepted in [active, queued]:
                assert (await repo.get_run(accepted.run_id)).error_code == "RUN_INTERRUPTED"
            assert (await repo.get_thread(first.id)).needs_recovery
            assert not (await repo.get_thread(second.id)).needs_recovery
            with pytest.raises(RunServiceError):
                await service.start_run(second.id, "after shutdown")

    asyncio.run(scenario())


def test_model_factory_failure_before_graph_preserves_thread(tmp_path):
    calls = 0

    def factory(settings):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ValueError("private-secret")
        return fake_factory(settings)

    async def scenario():
        async with running_service(tmp_path, factory) as (service, repo):
            thread = await repo.create_thread()
            accepted = await service.start_run(thread.id, "fail factory")
            await finished(service)
            assert (await repo.get_run(accepted.run_id)).status == RunStatus.FAILED
            assert not (await repo.get_thread(thread.id)).needs_recovery

    asyncio.run(scenario())


def test_enqueue_failure_has_no_live_created_row(tmp_path, monkeypatch):
    async def scenario():
        async with running_service(tmp_path) as (service, repo):
            thread = await repo.create_thread()

            def broken_put(run_id):
                raise asyncio.QueueFull

            monkeypatch.setattr(service.queue, "put_nowait", broken_put)
            with pytest.raises(asyncio.QueueFull):
                await service.start_run(thread.id, "cannot enqueue")
            runs = await repo.list_runs(thread.id)
            assert len(runs) == 1 and runs[0].status == RunStatus.FAILED
            assert runs[0].error_code == "RUN_INTERRUPTED"

    asyncio.run(scenario())
