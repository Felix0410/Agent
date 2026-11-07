"""每Run共享、先预扣的预算，不把token估算当Provider实际用量。"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from uuid import uuid4

from minideerflow.runtime.usage import UsageCall


class BudgetError(Exception):
    def __init__(self, code="BUDGET_EXCEEDED"):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RunBudget:
    max_model_calls: int = 40
    max_tool_calls: int = 30
    max_seconds: float = 600
    max_input_tokens_estimate: int = 120000


def estimate_messages(messages):
    """UTF8字节+结构开销的保守确定性估算，不宣称精确tokenizer。"""
    return sum(
        len(
            json.dumps(
                {"content": m.content, "tools": getattr(m, "tool_calls", [])},
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        )
        + 64
        for m in messages
    )


class RunBudgetTracker:
    """锁覆盖父/子/摘要预留；取消和耗尽为不可逆信号。"""

    def __init__(self, run_id, budget, repository, event_sink=None):
        self.run_id = run_id
        self.budget = budget
        self.repository = repository
        self.event_sink = event_sink
        self.started = time.monotonic()
        self.lock = asyncio.Lock()
        self.model_calls = 0
        self.tool_calls = 0
        self.estimated = 0
        self.compactions = 0
        self.externalized = 0
        self.cancelled = asyncio.Event()
        self.exceeded = False
        self.outcome_unknown = False
        self.cancel_check = None

    async def initialize(self):
        await self.repository.start(self.run_id, asdict(self.budget))

    async def check(self):
        """每次操作前确认取消；SQL检查由C接入，防止已提交取消后新增调用。"""
        if self.cancel_check is not None and await self.cancel_check():
            self.cancelled.set()
        if self.cancelled.is_set():
            raise asyncio.CancelledError
        if self.exceeded or time.monotonic() - self.started >= self.budget.max_seconds:
            self.exceeded = True
            raise BudgetError()

    async def reserve(self, kind, estimate=0, source="parent"):
        """1. 共享锁核验；2. 原子预扣；3. 保存唯一调用尝试。"""
        async with self.lock:
            await self.check()
            if (
                kind == "model"
                and (
                    self.model_calls >= self.budget.max_model_calls
                    or self.estimated + estimate > self.budget.max_input_tokens_estimate
                )
            ) or (kind == "tool" and self.tool_calls >= self.budget.max_tool_calls):
                self.exceeded = True
                raise BudgetError()
            if kind == "model":
                self.model_calls += 1
                self.estimated += estimate
            else:
                self.tool_calls += 1
            call = UsageCall(
                invocation_id=str(uuid4()),
                kind=kind,
                source=source,
                estimated_input_tokens=estimate,
            )
            await self.repository.begin(self.run_id, call)
            return call, time.monotonic()

    async def finish(self, reservation, status, usage=None):
        """只有明确完整Provider数字才入真实账；异常/取消仍保留次数。"""
        call, started = reservation
        call.status = status
        call.elapsed_ms = int((time.monotonic() - started) * 1000)
        if usage and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")
        ):
            call.provider_input_tokens = usage["input_tokens"]
            call.provider_output_tokens = usage["output_tokens"]
        await self.repository.finish(self.run_id, call)
        await self.flush()

    async def flush(self):
        """只发布数值统计，任何正文/Key都不进入预算事件。"""
        await self.repository.metrics(
            self.run_id,
            int((time.monotonic() - self.started) * 1000),
            self.compactions,
            self.externalized,
        )
        if self.event_sink:
            from types import SimpleNamespace

            from minideerflow.runtime.plan_service import safe_emit

            await safe_emit(
                SimpleNamespace(event_sink=self.event_sink),
                "budget_updated",
                (await self.repository.get(self.run_id)).model_dump(),
            )
