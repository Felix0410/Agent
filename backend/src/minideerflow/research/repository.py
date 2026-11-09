"""研究尝试/证据复用业务SQLite，配额和归属在同一事务检查。"""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from minideerflow.research.models import EvidenceRecord, ResearchError, SourceStatus
from minideerflow.runtime.repository import _run


def now():
    return datetime.now(UTC).isoformat()


class ResearchRepository:
    def __init__(self, database):
        self.database = database

    async def _identity(self, conn, run_id, thread_id, *, active=False):
        run = await _run(conn, run_id)
        if run.thread_id != thread_id or (
            active and (run.status != "RUNNING" or run.cancel_requested_at)
        ):
            raise ResearchError("RESEARCH_NOT_ALLOWED")
        return run

    async def reserve(self, run_id, thread_id, kind, query):
        """1. 核对运行身份；2. 原子占额；3. 记录真实尝试而非成功数。"""
        if kind not in ("SEARCH", "EXTRACT"):
            raise ResearchError("RESEARCH_INVALID_REQUEST")
        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id, active=True)
            async with conn.execute(
                "SELECT COUNT(*) FROM research_requests WHERE run_id=? AND kind=?", (run_id, kind)
            ) as cur:
                count = (await cur.fetchone())[0]
            if count >= (6 if kind == "SEARCH" else 8):
                raise ResearchError("RESEARCH_QUOTA_EXCEEDED")
            request_id = str(uuid4())
            await conn.execute(
                "INSERT INTO research_requests VALUES(?,?,?,?,'PENDING',NULL,?,NULL)",
                (request_id, run_id, kind, query, now()),
            )
            return request_id

    async def _pending(self, conn, request_id, run_id, kind):
        async with conn.execute(
            "SELECT * FROM research_requests WHERE id=? AND run_id=? AND kind=? AND status='PENDING'",
            (request_id, run_id, kind),
        ) as cur:
            if await cur.fetchone() is None:
                raise ResearchError("RESEARCH_REQUEST_UNKNOWN")

    async def finish_request(self, request_id, status, code=None):
        async with self.database.transaction() as conn:
            await conn.execute(
                "UPDATE research_requests SET status=?,error_code=?,finished_at=? WHERE id=? AND status='PENDING'",
                (status, code, now(), request_id),
            )

    async def add_search(self, run_id, thread_id, request_id, hits):
        """只提交真实Provider结果；并发去重与30条上限都在SQL事务内。"""
        from minideerflow.research.urls import canonical_url

        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id, active=True)
            await self._pending(conn, request_id, run_id, "SEARCH")
            for hit in hits[:5]:
                url = canonical_url(hit.url)
                async with conn.execute(
                    "SELECT COUNT(*) FROM research_evidence WHERE run_id=?", (run_id,)
                ) as cur:
                    count = (await cur.fetchone())[0]
                if count >= 30:
                    break
                await conn.execute(
                    "INSERT OR IGNORE INTO research_evidence VALUES(?,?,?,?,?,?,NULL,'SNIPPET_ONLY',?,NULL,NULL)",
                    (str(uuid4()), run_id, thread_id, url, hit.title, hit.snippet, hit.searched_at),
                )
            await conn.execute(
                "UPDATE research_requests SET status='SUCCEEDED',finished_at=? WHERE id=?",
                (now(), request_id),
            )
        urls = {canonical_url(h.url) for h in hits[:5]}
        return [item for item in await self.list(run_id, thread_id) if item.url in urls]

    @staticmethod
    def _record(row):
        return EvidenceRecord(
            id=row["id"],
            title=row["title"],
            url=row["canonical_url"],
            snippet=row["snippet"],
            searched_at=row["searched_at"],
            source_status=SourceStatus(row["status"]),
            excerpt=(row["extract_text"] or row["snippet"])[:1500],
            extracted_at=row["extracted_at"],
            content_sha256=row["content_sha256"],
        )

    async def list(self, run_id, thread_id):
        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id)
            async with conn.execute(
                "SELECT * FROM research_evidence WHERE run_id=? AND thread_id=? ORDER BY searched_at,id",
                (run_id, thread_id),
            ) as cur:
                return [self._record(row) for row in await cur.fetchall()]

    async def get(self, run_id, thread_id, evidence_id):
        for item in await self.list(run_id, thread_id):
            if item.id == evidence_id:
                return item
        raise ResearchError("RESEARCH_EVIDENCE_NOT_FOUND")

    async def update_extract(self, run_id, thread_id, request_id, evidence_id, text):
        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id, active=True)
            await self._pending(conn, request_id, run_id, "EXTRACT")
            # 失败不能擦除以前真实取得的正文；无正文的失败保持摘要可追溯。
            status = "EXTRACTED" if text else "EXTRACTION_FAILED"
            cur = await conn.execute(
                "UPDATE research_evidence SET status=CASE WHEN status='EXTRACTED' AND ? IS NULL THEN status ELSE ? END,extract_text=COALESCE(?,extract_text),extracted_at=?,content_sha256=COALESCE(?,content_sha256) WHERE id=? AND run_id=? AND thread_id=?",
                (
                    text,
                    status,
                    text,
                    now(),
                    hashlib.sha256(text.encode()).hexdigest() if text else None,
                    evidence_id,
                    run_id,
                    thread_id,
                ),
            )
            if cur.rowcount != 1:
                raise ResearchError("RESEARCH_EVIDENCE_NOT_FOUND")
            await conn.execute(
                "UPDATE research_requests SET status=?,error_code=?,finished_at=? WHERE id=?",
                (
                    "SUCCEEDED" if text else "FAILED",
                    None if text else "RESEARCH_EXTRACTION_FAILED",
                    now(),
                    request_id,
                ),
            )
        return await self.get(run_id, thread_id, evidence_id)

    async def reconcile_orphans(self):
        """进程重启不能重发可能已计费的外部调用。"""
        async with self.database.transaction() as conn:
            await conn.execute(
                "UPDATE research_requests SET status='UNKNOWN',finished_at=?,error_code='RESEARCH_INTERRUPTED' WHERE status='PENDING'",
                (now(),),
            )

    async def check_report_absent(self, run_id, thread_id):
        """已有关联或遗留报告Artifact时拒绝重写；不自动重放未知写操作。"""
        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id, active=True)
            async with conn.execute(
                "SELECT 1 FROM research_reports WHERE run_id=? UNION ALL SELECT 1 FROM files WHERE run_id=? AND kind='ARTIFACT' AND display_name GLOB 'research-report-*.md' LIMIT 1",
                (run_id, run_id),
            ) as cur:
                if await cur.fetchone():
                    raise ResearchError("RESEARCH_REPORT_EXISTS_OR_UNKNOWN")

    async def link_report(self, run_id, thread_id, artifact_id, data, citations):
        """关联只能指向已经登记且同Run/Thread的Artifact，不假设跨文件/SQL事务。"""
        import json

        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id, active=True)
            async with conn.execute(
                "SELECT 1 FROM artifacts WHERE id=? AND run_id=? AND thread_id=?",
                (artifact_id, run_id, thread_id),
            ) as cur:
                if await cur.fetchone() is None:
                    raise ResearchError("RESEARCH_ARTIFACT_NOT_FOUND")
            await conn.execute(
                "INSERT INTO research_reports VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    run_id,
                    thread_id,
                    artifact_id,
                    data.title,
                    json.dumps(data.limitations, ensure_ascii=False),
                    json.dumps([item.id for item in citations]),
                    now(),
                ),
            )

    async def get_report(self, run_id, thread_id):
        import json

        from minideerflow.research.models import ResearchReport

        async with self.database.transaction() as conn:
            await self._identity(conn, run_id, thread_id)
            async with conn.execute(
                "SELECT r.* FROM research_reports r JOIN artifacts a ON a.id=r.artifact_id AND a.run_id=r.run_id AND a.thread_id=r.thread_id WHERE r.run_id=? AND r.thread_id=?",
                (run_id, thread_id),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            return None
        ids = set(json.loads(row["evidence_ids_json"]))
        citations = [item for item in await self.list(run_id, thread_id) if item.id in ids]
        return ResearchReport(
            artifact_id=row["artifact_id"],
            title=row["title"],
            citations=citations,
            limitations=json.loads(row["limitations_json"]),
        )
