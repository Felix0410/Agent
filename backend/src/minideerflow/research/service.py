"""可信Context协调联网与持久化，外部页面只作为不可信证据数据。"""

import asyncio

from minideerflow.research.models import ResearchError
from minideerflow.runtime.plan_service import safe_emit


class ResearchService:
    def __init__(self, repository, provider, workspace=None):
        self.repository = repository
        self.provider = provider
        self.workspace = workspace
        self._report_locks = {}

    async def _check(self, context):
        if context.research_service is not self or self.provider is None:
            raise ResearchError("RESEARCH_UNAVAILABLE")
        if context.budget_tracker:
            await context.budget_tracker.check()
        async with self.repository.database.transaction() as conn:
            await self.repository._identity(conn, context.run_id, context.thread_id, active=True)

    async def _cleanup(self, request_id, status, code):
        """反复取消也先落下未知状态；调用方随后继续传播原异常。"""
        task = asyncio.create_task(self.repository.finish_request(request_id, status, code))
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        await task

    async def search(self, context, query):
        """1. 可信身份与SQL占额；2. 一次Provider请求；3. 提交后发轻量事件。"""
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 400:
            raise ResearchError("RESEARCH_INVALID_REQUEST")
        await self._check(context)
        request_id = await self.repository.reserve(
            context.run_id, context.thread_id, "SEARCH", query.strip()
        )
        try:
            await self._check(context)
            hits = await self.provider.search(query.strip())
            await self._check(context)
            result = await self.repository.add_search(
                context.run_id, context.thread_id, request_id, hits
            )
        except BaseException as exc:
            await self._cleanup(
                request_id,
                "UNKNOWN" if isinstance(exc, asyncio.CancelledError) else "FAILED",
                exc.code if isinstance(exc, ResearchError) else "RESEARCH_REQUEST_UNKNOWN",
            )
            raise
        await safe_emit(
            context, "research_search_completed", {"evidence_ids": [item.id for item in result]}
        )
        return result

    async def fetch(self, context, evidence_id):
        """URL只能来自同Run真实证据；失败保留原摘要，不改为任意直连。"""
        await self._check(context)
        item = await self.repository.get(context.run_id, context.thread_id, evidence_id)
        request_id = await self.repository.reserve(
            context.run_id, context.thread_id, "EXTRACT", item.url
        )
        try:
            await self._check(context)
            try:
                text = await self.provider.extract(item.url)
            except ResearchError as exc:
                # Provider错误仍写真实证据等级，最终错误类别保存在请求表。
                await self.repository.update_extract(
                    context.run_id, context.thread_id, request_id, item.id, None, exc.code
                )
                raise
            await self._check(context)
            result = await self.repository.update_extract(
                context.run_id, context.thread_id, request_id, item.id, text
            )
        except BaseException as exc:
            await self._cleanup(
                request_id,
                "UNKNOWN" if isinstance(exc, asyncio.CancelledError) else "FAILED",
                exc.code if isinstance(exc, ResearchError) else "RESEARCH_REQUEST_UNKNOWN",
            )
            if isinstance(exc, ResearchError):
                current = await self.repository.get(context.run_id, context.thread_id, item.id)
                await safe_emit(
                    context,
                    "research_evidence_updated",
                    {"evidence_id": item.id, "status": current.source_status.value},
                )
            raise
        await safe_emit(
            context,
            "research_evidence_updated",
            {"evidence_id": result.id, "status": result.source_status.value},
        )
        return result

    async def save_report(self, context, data):
        """1. 验证引用和单份约束；2. P03原子写；3. 同Run SQL关联后才报成功。"""
        from uuid import uuid4

        from minideerflow.agents.context import AgentRunContext
        from minideerflow.research.report import render_markdown_report

        if not isinstance(context, AgentRunContext) or self.workspace is None:
            raise ResearchError("RESEARCH_NOT_ALLOWED")
        # 服务生命周期内按Run串行写；SQL唯一约束及遗留Artifact检查保护重启。
        lock = self._report_locks.setdefault(context.run_id, asyncio.Lock())
        async with lock:
            await self._check(context)
            await self.repository.check_report_absent(context.run_id, context.thread_id)
            evidence = await self.repository.list(context.run_id, context.thread_id)
            markdown, citations = render_markdown_report(data, evidence)
            await self._check(context)
            try:
                artifact = await self.workspace.write_text(
                    context.thread_id, context.run_id, f"research-report-{uuid4().hex}.md", markdown
                )
                await self._check(context)
                await self.repository.link_report(
                    context.run_id, context.thread_id, artifact.artifact_id, data, citations
                )
            except BaseException as exc:
                # 写入已开始：不能把未知回执当成可重试，原Artifact保留供人工复核。
                if context.budget_tracker:
                    context.budget_tracker.outcome_unknown = True
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise ResearchError("RESEARCH_REPORT_OUTCOME_UNKNOWN") from None
            await safe_emit(
                context, "research_report_created", {"artifact_id": artifact.artifact_id}
            )
            return await self.repository.get_report(context.run_id, context.thread_id)
