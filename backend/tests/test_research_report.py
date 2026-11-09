"""结构化引用、真实Artifact、失败与取消均使用临时Workspace。"""

import asyncio
import hashlib
from dataclasses import replace

import pytest
from pydantic import ValidationError
from test_file_tools import active_run
from test_workspace import workspace

from minideerflow.agents.context import AgentRunContext, ChildContext
from minideerflow.research.models import ResearchError, SearchHit
from minideerflow.research.report import ReportInput, render_markdown_report
from minideerflow.research.repository import ResearchRepository
from minideerflow.research.service import ResearchService
from minideerflow.runtime.budget import RunBudget, RunBudgetTracker
from minideerflow.runtime.usage import UsageRepository


def test_structured_limits():
    valid = {
        "title": "report",
        "findings": [{"claim": "claim", "evidence_ids": ["id"]}],
        "limitations": [],
    }
    for patch in [
        {"title": " "},
        {"title": "x" * 121},
        {"findings": []},
        {"findings": [{"claim": " ", "evidence_ids": ["id"]}]},
        {"findings": [{"claim": "claim", "evidence_ids": []}]},
        {"limitations": ["x" * 1001] * 2},
        {"limitations": ["x"] * 9},
    ]:
        with pytest.raises(ValidationError):
            ReportInput(**(valid | patch))


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "fake",
        "foreign",
        "cancel",
        "link_failure",
        "parallel",
        "cancel_after_write",
        "child",
    ],
)
def test_report_identity_download_and_unknown(tmp_path, monkeypatch, mode):
    async def scenario():
        async with workspace(tmp_path) as (ws, runs, _):
            thread = await runs.create_thread()
            run = await active_run(runs, thread)
            repo = ResearchRepository(runs.database)
            service = ResearchService(repo, object(), ws)
            tracker = RunBudgetTracker(run.id, RunBudget(), UsageRepository(runs.database))
            await tracker.initialize()
            ctx = AgentRunContext(
                thread.id, run.id, ws, None, research_service=service, budget_tracker=tracker
            )
            req = await repo.reserve(run.id, thread.id, "SEARCH", "topic")
            rows = await repo.add_search(
                run.id,
                thread.id,
                req,
                [
                    SearchHit(
                        title="<script>bad</script>",
                        url="https://example.com/",
                        snippet="only snippet",
                        searched_at="now",
                    )
                ],
            )
            eid = rows[0].id
            if mode == "fake":
                eid = "invented-id"
            if mode == "foreign":
                other = await runs.create_thread()
                other_run = await active_run(runs, other)
                ctx = replace(ctx, thread_id=other.id, run_id=other_run.id, budget_tracker=None)
            data = ReportInput(
                title="T<script>",
                findings=[
                    {"claim": "unsupported certainty [99](javascript:bad)", "evidence_ids": [eid]}
                ],
                limitations=["Not independently verified"],
            )
            if mode == "cancel":
                await runs.request_cancel(run.id)
            if mode == "child":
                ctx = ChildContext(thread.id, run.id, ws, research_service=service)
            if mode in ("fake", "foreign", "cancel", "child"):
                with pytest.raises(ResearchError):
                    await service.save_report(ctx, data)
                assert await ws.list_artifacts(thread.id) == []
                return
            if mode == "link_failure":

                async def failure(*args):
                    raise RuntimeError("test transaction failure")

                monkeypatch.setattr(repo, "link_report", failure)
            if mode == "cancel_after_write":
                original = ws.write_text

                async def write_then_cancel(*args):
                    await original(*args)
                    raise asyncio.CancelledError

                monkeypatch.setattr(ws, "write_text", write_then_cancel)
            if mode in ("link_failure", "cancel_after_write"):
                with pytest.raises((ResearchError, asyncio.CancelledError)):
                    await service.save_report(ctx, data)
                assert tracker.outcome_unknown
                assert await repo.get_report(run.id, thread.id) is None
                assert len(await ws.list_artifacts(thread.id)) == 1
                with pytest.raises(ResearchError):
                    await service.save_report(ctx, data)
                assert len(await ws.list_artifacts(thread.id)) == 1
                return
            if mode == "parallel":
                results = await asyncio.gather(
                    *(service.save_report(ctx, data) for _ in range(2)), return_exceptions=True
                )
                assert sum(isinstance(r, ResearchError) for r in results) == 1
            else:
                await service.save_report(ctx, data)
            saved = await repo.get_report(run.id, thread.id)
            content, artifact = await ws.download_artifact(thread.id, saved.artifact_id)
            record = await ws.repository.get_file_for_thread(thread.id, artifact.file_id)
            assert hashlib.sha256(content).hexdigest() == record.sha256
            text = content.decode()
            assert "仅摘要线索" in text and "不等于主张真实性已独立验证" in text
            assert "<script>" not in text and "javascript:bad)" not in text
            assert "[1]" in text and eid in text
            assert len(await ws.list_artifacts(thread.id)) == 1

    asyncio.run(scenario())


def test_renderer_does_not_upgrade_snippet_or_assert_semantics(tmp_path):
    from minideerflow.research.models import EvidenceRecord, SourceStatus

    row = EvidenceRecord(
        id="real",
        title="source",
        url="https://example.com/",
        snippet="a",
        searched_at="now",
        source_status=SourceStatus.EXTRACTION_FAILED,
        excerpt="a",
    )
    data = ReportInput(
        title="T",
        findings=[{"claim": "a claim not established by this source", "evidence_ids": ["real"]}],
        limitations=[],
    )
    text, _ = render_markdown_report(data, [row])
    assert "正文提取失败，仅摘要线索" in text and "未自动判断结论是否由原文充分支持" in text
    with pytest.raises(ResearchError):
        render_markdown_report(data, [])
