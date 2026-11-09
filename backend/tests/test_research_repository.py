"""真实临时SQLite验证并发占额、同Run隔离和重启。"""

import asyncio

import pytest

from minideerflow.research.models import ResearchError, SearchHit
from minideerflow.research.repository import ResearchRepository
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.models import RunStatus
from minideerflow.runtime.repository import RuntimeRepository


async def setup(tmp_path):
    db = await RuntimeDatabase.open(tmp_path / "research.sqlite3")
    await db.init_schema()
    runs = RuntimeRepository(db)
    thread = await runs.create_thread()
    run = await runs.create_run(thread.id, "research")
    await runs.transition_run(run.id, RunStatus.CREATED, RunStatus.RUNNING)
    return db, runs, ResearchRepository(db), thread.id, run.id


@pytest.mark.anyio
async def test_atomic_quotas_dedup_and_reopen(tmp_path):
    db, _runs, repo, tid, rid = await setup(tmp_path)
    try:
        for kind, limit in [("SEARCH", 6), ("EXTRACT", 8)]:
            results = await asyncio.gather(
                *(repo.reserve(rid, tid, kind, "query") for _ in range(15)), return_exceptions=True
            )
            assert sum(isinstance(r, str) for r in results) == limit
            assert all(isinstance(r, (str, ResearchError)) for r in results)
        async with db.transaction() as conn:
            cur = await conn.execute("SELECT id FROM research_requests WHERE kind='SEARCH'")
            ids = [r[0] for r in await cur.fetchall()]
        for n, req in enumerate(ids):
            await repo.add_search(
                rid,
                tid,
                req,
                [
                    SearchHit(
                        title="T",
                        url=f"https://example.com/{n * 5 + i}",
                        snippet="snippet",
                        searched_at="now",
                    )
                    for i in range(5)
                ],
            )
        assert len(await repo.list(rid, tid)) == 30
        with pytest.raises(ResearchError):
            await repo.list(rid, "wrong-thread")
        with pytest.raises(ResearchError):
            await repo.get(rid, tid, "invented")
        await repo.reconcile_orphans()
        async with db.transaction() as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) FROM research_requests WHERE status='UNKNOWN'"
            )
            assert (await cur.fetchone())[0] == 8
        await db.init_schema()
        assert len(await repo.list(rid, tid)) == 30
    finally:
        await db.close()


@pytest.mark.anyio
async def test_dedup_and_extract_status(tmp_path):
    db, runs, repo, tid, rid = await setup(tmp_path)
    try:
        hit = SearchHit(title="T", url="https://example.com/a#x", snippet="s", searched_at="now")
        for _ in range(2):
            req = await repo.reserve(rid, tid, "SEARCH", "q")
            items = await repo.add_search(rid, tid, req, [hit, hit])
        assert len(items) == 1
        req = await repo.reserve(rid, tid, "EXTRACT", items[0].url)
        item = await repo.update_extract(rid, tid, req, items[0].id, "actual text")
        assert item.source_status == "EXTRACTED" and item.content_sha256
        req = await repo.reserve(rid, tid, "EXTRACT", item.url)
        assert (
            await repo.update_extract(rid, tid, req, item.id, None)
        ).source_status == "EXTRACTED"
        await runs.request_cancel(rid)
        with pytest.raises(ResearchError):
            await repo.reserve(rid, tid, "SEARCH", "later")
    finally:
        await db.close()


@pytest.fixture
def anyio_backend():
    return "asyncio"
