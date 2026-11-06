"""真实临时 SQLite 的事务、状态与 Thread HTTP 测试；不调用 Provider。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from minideerflow.agents.service import ToolTrace
from minideerflow.main import create_app
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import RunAccepted, RunEvent, RunStatus, utc_now_iso
from minideerflow.runtime.repository import RepositoryError, RuntimeRepository


@asynccontextmanager
async def repository(path: Path):
    database = await RuntimeDatabase.open(path)
    try:
        await database.init_schema()
        yield database, RuntimeRepository(database)
    finally:
        await database.close()


def test_thread_creation_order_and_lookup(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            first = await repo.create_thread()
            second = await repo.create_thread("  自定义会话  ")
            UUID(first.id)
            assert first.title == "新会话"
            assert second.title == "自定义会话"
            assert first.needs_recovery is False
            assert [t.id for t in await repo.list_threads()] == [second.id, first.id]
            assert await repo.get_thread(first.id) == first
            assert await repo.list_runs(first.id) == []
            with pytest.raises(RepositoryError) as error:
                await repo.get_thread("missing")
            assert error.value.code == "THREAD_NOT_FOUND"

    asyncio.run(scenario())


def test_atomic_active_run_constraint(tmp_path: Path) -> None:
    async def scenario():
        # 两个连接模拟绕过同一进程锁的竞争，最终由 BEGIN IMMEDIATE/唯一索引兜底。
        async with repository(tmp_path / "runtime.db") as (_, left):
            thread = await left.create_thread()
            other = await left.create_thread()
            async with repository(tmp_path / "runtime.db") as (_, right):
                results = await asyncio.gather(
                    left.create_run(thread.id, "one"),
                    right.create_run(thread.id, "two"),
                    return_exceptions=True,
                )
                assert sum(isinstance(r, RepositoryError) for r in results) == 1
                error = next(r for r in results if isinstance(r, RepositoryError))
                assert error.code == "THREAD_BUSY"
                assert (await right.create_run(other.id, "independent")).status == RunStatus.CREATED
                assert len(await left.list_runs(thread.id)) == 1

    asyncio.run(scenario())


def test_run_lifecycle_terminal_immutable_and_trace(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            thread = await repo.create_thread()
            run = await repo.create_run(thread.id, "calculate")
            assert run.started_at is None and run.finished_at is None
            running = await repo.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            assert running.started_at is not None
            trace = ToolTrace(name="calculate", args={"expression": "1+1"}, result="2", ok=True)
            complete = await repo.complete_run(
                run.id, status=RunStatus.SUCCEEDED, answer="2", tool_calls=[trace]
            )
            assert complete.finished_at is not None
            assert complete.tool_calls == [trace]
            assert complete.answer == "2"
            assert complete.error_code is None
            with pytest.raises(RepositoryError):
                await repo.transition_run(run.id, RunStatus.SUCCEEDED, RunStatus.RUNNING)
            with pytest.raises(RepositoryError):
                await repo.complete_run(run.id, status=RunStatus.FAILED, error_code="LATE")
            assert await repo.get_run(run.id) == complete
            assert (await repo.create_run(thread.id, "next")).status == RunStatus.CREATED

    asyncio.run(scenario())


def test_illegal_transition_and_failure_before_running(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            thread = await repo.create_thread()
            run = await repo.create_run(thread.id, "hello")
            with pytest.raises(RepositoryError):
                await repo.complete_run(run.id, status=RunStatus.SUCCEEDED, answer="invented")
            with pytest.raises(RepositoryError):
                await repo.transition_run(
                    run.id, RunStatus.RUNNING, RunStatus.FAILED, error_code="X"
                )
            failed = await repo.complete_run(
                run.id, status=RunStatus.FAILED, error_code="START_FAILED"
            )
            assert failed.answer is None and failed.started_at is None
            assert failed.finished_at is not None
            assert not (await repo.get_thread(thread.id)).needs_recovery

    asyncio.run(scenario())


def test_failed_graph_blocks_future_runs(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            thread = await repo.create_thread()
            run = await repo.create_run(thread.id, "hello")
            await repo.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            await repo.complete_run(
                run.id, status=RunStatus.FAILED, error_code="MODEL_TIMEOUT", needs_recovery=True
            )
            assert (await repo.get_thread(thread.id)).needs_recovery
            with pytest.raises(RepositoryError) as error:
                await repo.create_run(thread.id, "unsafe continuation")
            assert error.value.code == "THREAD_REQUIRES_RECOVERY"

    asyncio.run(scenario())


def test_reopen_persists_and_reconciles_only_orphans(tmp_path: Path) -> None:
    async def scenario():
        path = tmp_path / "runtime.db"
        async with repository(path) as (_, repo):
            done_thread = await repo.create_thread()
            done = await repo.create_run(done_thread.id, "done")
            await repo.transition_run(done.id, RunStatus.CREATED, RunStatus.RUNNING)
            await repo.complete_run(done.id, status=RunStatus.SUCCEEDED, answer="saved")
            queued_thread = await repo.create_thread()
            queued = await repo.create_run(queued_thread.id, "queued")
            running_thread = await repo.create_thread()
            running = await repo.create_run(running_thread.id, "running")
            await repo.transition_run(running.id, RunStatus.CREATED, RunStatus.RUNNING)
        async with repository(path) as (_, repo):
            assert (await repo.get_run(done.id)).answer == "saved"
            assert await repo.reconcile_orphans() == 2
            assert await repo.reconcile_orphans() == 0
            for old in [queued, running]:
                interrupted = await repo.get_run(old.id)
                assert interrupted.status == RunStatus.FAILED
                assert interrupted.error_code == "RUN_INTERRUPTED"
                assert interrupted.finished_at is not None
                assert (await repo.get_thread(old.thread_id)).needs_recovery
            assert not (await repo.get_thread(done_thread.id)).needs_recovery
            assert (await repo.get_run(done.id)).status == RunStatus.SUCCEEDED

    asyncio.run(scenario())


def test_history_limits_and_order(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            thread = await repo.create_thread()
            ids = []
            for index in range(4):
                run = await repo.create_run(thread.id, str(index))
                await repo.complete_run(run.id, status=RunStatus.FAILED, error_code="START_FAILED")
                ids.append(run.id)
            assert [r.id for r in await repo.list_runs(thread.id, 2)] == ids[-2:]
            for limit in [0, 101]:
                with pytest.raises(ValueError):
                    await repo.list_runs(thread.id, limit)

    asyncio.run(scenario())


def test_pragmas_constraints_and_transaction_rollback(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "nested/runtime.db") as (database, repo):
            for name, expected in [
                ("foreign_keys", 1),
                ("journal_mode", "wal"),
                ("busy_timeout", 5000),
            ]:
                async with database.transaction() as conn, conn.execute(f"PRAGMA {name}") as cursor:
                    assert (await cursor.fetchone())[0] == expected
            with pytest.raises(aiosqlite.IntegrityError):
                async with database.transaction() as conn:
                    await conn.execute(
                        "INSERT INTO runs(id,thread_id,input_message,status,created_at) VALUES(?,?,?,?,?)",
                        ("orphan", "missing", "hi", "CREATED", utc_now_iso()),
                    )
            with pytest.raises(RuntimeError):
                async with database.transaction() as conn:
                    await conn.execute(
                        "INSERT INTO threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                        ("rollback", "temporary", utc_now_iso(), utc_now_iso()),
                    )
                    raise RuntimeError("rollback test")
            assert await repo.list_threads() == []
            assert (await repo.create_thread()).id

    asyncio.run(scenario())


def test_index_enforced_even_for_raw_sql(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (db, repo):
            thread = await repo.create_thread()
            await repo.create_run(thread.id, "first")
            with pytest.raises(aiosqlite.IntegrityError):
                async with db.transaction() as conn:
                    await conn.execute(
                        "INSERT INTO runs(id,thread_id,input_message,status,created_at) VALUES(?,?,?,?,?)",
                        ("second", thread.id, "second", "RUNNING", utc_now_iso()),
                    )

    asyncio.run(scenario())


def test_model_contracts() -> None:
    now = utc_now_iso()
    assert now.endswith("+00:00")
    assert RunAccepted(run_id="r", thread_id="t").model_dump() == {
        "run_id": "r",
        "thread_id": "t",
        "status": "CREATED",
    }
    event = RunEvent(
        event_id="r:1", run_id="r", thread_id="t", type="run_start", timestamp=now, payload={}
    )
    assert event.model_dump()["payload"] == {}
    assert RunStatus.CANCELLED.value == "CANCELLED"  # 只预留 DTO，不暴露取消入口。


def test_thread_api_lifespan_and_p01_preserved() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/threads").json() == []
        response = client.post("/api/threads", json={})
        assert response.status_code == 201
        thread = response.json()
        assert thread["title"] == "新会话"
        assert thread["needs_recovery"] is False
        custom = client.post("/api/threads", json={"title": "custom"}).json()
        assert [t["id"] for t in client.get("/api/threads").json()] == [custom["id"], thread["id"]]
        assert client.get(f"/api/threads/{thread['id']}/runs").json() == []
        assert client.post("/api/demo/calculate", json={"expression": "(12+8)*3"}).json() == {
            "result": "60"
        }
        assert client.post("/api/demo/agent", json={"message": "hello"}).status_code == 503
        # A 不能意外暴露尚未实现的 Run 提交入口。
        assert (
            client.post(f"/api/threads/{thread['id']}/runs", json={"message": "hello"}).status_code
            == 405
        )
    assert app.state.database._closed

    async def read_closed_saver():
        await app.state.checkpointer.conn.execute("SELECT 1")

    with pytest.raises(ValueError):
        asyncio.run(read_closed_saver())


@pytest.mark.parametrize("title", ["", "   ", "x" * 101, None])
def test_thread_api_rejects_invalid_title(title) -> None:
    with TestClient(create_app()) as client:
        assert client.post("/api/threads", json={"title": title}).status_code == 422


def test_history_api_404_and_limits() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/threads/missing/runs")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "THREAD_NOT_FOUND"
        for limit in [0, 101]:
            assert client.get(f"/api/threads/missing/runs?limit={limit}").status_code == 422


def test_validation_missing_rows_and_failed_update_rollback(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (_, repo):
            thread = await repo.create_thread()
            with pytest.raises(RepositoryError) as error:
                await repo.create_run("missing", "hello")
            assert error.value.code == "THREAD_NOT_FOUND"
            with pytest.raises(RepositoryError) as error:
                await repo.get_run("missing")
            assert error.value.code == "RUN_NOT_FOUND"
            for message in ["", "   ", "x" * 2001]:
                with pytest.raises(ValueError):
                    await repo.create_run(thread.id, message)
            run = await repo.create_run(thread.id, "x" * 2000)
            await repo.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
            for params in [
                {"status": RunStatus.SUCCEEDED, "answer": "   "},
                {"status": RunStatus.FAILED},
                {"status": RunStatus.CANCELLED},
            ]:
                with pytest.raises((ValueError, RepositoryError)):
                    await repo.complete_run(run.id, **params)
                assert (await repo.get_run(run.id)).status == RunStatus.RUNNING

    asyncio.run(scenario())


def test_transaction_cancel_rollback(tmp_path: Path) -> None:
    async def scenario():
        async with repository(tmp_path / "runtime.db") as (db, repo):
            with pytest.raises(asyncio.CancelledError):
                async with db.transaction() as conn:
                    await conn.execute(
                        "INSERT INTO threads(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                        ("cancelled", "temporary", utc_now_iso(), utc_now_iso()),
                    )
                    raise asyncio.CancelledError
            assert await repo.list_threads() == []
            assert (await repo.create_thread()).id

    asyncio.run(scenario())


def test_lifespan_startup_failure_closes_business_db(monkeypatch, tmp_path: Path) -> None:
    original_open = RuntimeDatabase.open
    opened = []

    async def tracked_open(path):
        db = await original_open(path)
        opened.append(db)
        return db

    # Saver 无法将目录作为 SQLite 文件打开，业务库仍必须被退出栈关闭。
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path))
    monkeypatch.setattr(RuntimeDatabase, "open", tracked_open)
    with pytest.raises(aiosqlite.OperationalError), TestClient(create_app()):
        pytest.fail("startup should not succeed")
    assert opened[0]._closed


def test_lifespan_reopens_history_and_reconciles_orphan() -> None:
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()
        run = client.portal.call(app.state.repository.create_run, thread["id"], "interrupted")
    with TestClient(app) as client:
        restored = client.get("/api/threads").json()
        assert restored[0]["id"] == thread["id"]
        assert restored[0]["needs_recovery"] is True
        runs = client.get(f"/api/threads/{thread['id']}/runs").json()
        assert runs[0]["id"] == run.id
        assert runs[0]["status"] == "FAILED"
        assert runs[0]["error_code"] == "RUN_INTERRUPTED"
