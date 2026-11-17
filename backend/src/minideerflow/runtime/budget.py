"""每Run共享的用量观察与取消上下文；历史字节字段不再构成执行许可。"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from uuid import uuid4

from minideerflow.runtime.usage import UsageCall


class BudgetError(Exception):
    def __init__(self, code="BUDGET_EXCEEDED", reason="UNCOMPRESSIBLE"):
        super().__init__(code)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class RunBudget:
    """兼容旧构造接口；只有max_seconds仍用于运行资源时限。"""

    max_model_calls: int = 40
    max_tool_calls: int = 30
    max_seconds: float = 600
    max_input_tokens_estimate: int = 480000


@dataclass(frozen=True)
class BudgetBreakdown:
    """只含数字及版本，不保留消息、参数、URL或任何认证信息。"""

    system_bytes: int
    tool_schema_bytes: int
    message_bytes: int
    total_bytes: int
    soft_bytes: int
    hard_bytes: int
    cumulative_bytes: int
    estimator: str = "utf8_json_bytes_v1"


def budget_breakdown(
    messages, tools=(), system_message=None, *, soft=24000, hard=48000, cumulative=0
):
    """父/子/摘要共用同一字节口径；System和工具Schema各计一次。"""
    system = estimate_messages([system_message]) if system_message is not None else 0
    schema = estimate_tools(tools)
    body = estimate_messages(messages)
    return BudgetBreakdown(system, schema, body, system + schema + body, soft, hard, cumulative)


def estimate_messages(messages):
    """计算UTF-8 JSON字节近似值；历史字段名含tokens，不代表真实Token。"""
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


def estimate_tools(tools):
    """估算工具列表的token数"""
    total = 0
    for tool in tools:
        if isinstance(tool, dict):
            schema = tool
        else:
            public = tool.tool_call_schema
            schema = {
                "name": tool.name,
                "description": tool.description,
                "parameters": public if isinstance(public, dict) else public.model_json_schema(),
            }
        total += len(json.dumps(schema, ensure_ascii=False, default=str).encode("utf-8")) + 64
    return total


class RunBudgetTracker:
    """保留历史类名的观察上下文；计数和估算只记录，不授予执行许可。"""

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
        self.outcome_unknown = False
        self.cancel_check = None
        self.summary_config = {}

    async def initialize(self):
        await self.repository.start(
            self.run_id,
            {
                "mode": "observe_only",
                "execution_limits": False,
                "max_seconds": self.budget.max_seconds,
                "estimate_unit": "utf8_json_bytes_v1",
                "summarization": self.summary_config,
            },
        )

    async def record_context(self, breakdown, reason="WITHIN_LIMIT"):
        """SQL保存最后一次分项，日志只记录数值和固定原因枚举。"""
        data = {**asdict(breakdown), "phase": "before_model", "reason": reason}
        await self.repository.context_diagnostic(self.run_id, data)
        logging.getLogger("minideerflow.budget").info("context_budget %s", json.dumps(data))

    async def check(self):
        """检查状态"""
        if self.cancel_check is not None and await self.cancel_check():
            self.cancelled.set()
        if self.cancelled.is_set():
            raise asyncio.CancelledError
        if time.monotonic() - self.started >= self.budget.max_seconds:
            raise TimeoutError("run deadline exceeded")

    async def reserve(self, kind, estimate=0, source="parent", *, estimate_v2=None):
        """唯一invocation先登记再执行；并发安全计数，不限制40/30或输入字节。"""
        async with self.lock:
            await self.check()
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
                estimated_input_tokens_v2=estimate_v2,
                estimator_version="utf8_conservative_v2" if estimate_v2 is not None else None,
            )
            await self.repository.begin(self.run_id, call)
            return call, time.monotonic()

    async def finish(self, reservation, status, usage=None):
        """完成预扣"""
        task = asyncio.create_task(self._finish(reservation, status, usage))
        interrupted = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                interrupted = True
        task.result()
        if interrupted:
            raise asyncio.CancelledError

    async def _finish(self, reservation, status, usage=None):
        """只有明确完整Provider数字才入真实账；异常/取消仍保留次数。"""
        call, started = reservation
        call.status = status
        call.elapsed_ms = int((time.monotonic() - started) * 1000)
        if usage and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")
        ):
            call.provider_input_tokens = usage["input_tokens"]
            call.provider_output_tokens = usage["output_tokens"]
        call.usage_source = (
            "provider"
            if call.provider_input_tokens is not None
            else "estimate"
            if call.estimated_input_tokens > 0
            else "unknown"
        )
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
        await self.emit("budget_updated", (await self.repository.get(self.run_id)).model_dump())

    async def emit(self, kind, payload):
        """观察事件失败不撤销真实业务提交，也不阻止取消。"""
        if self.event_sink:
            from types import SimpleNamespace

            from minideerflow.runtime.plan_service import safe_emit

            await safe_emit(SimpleNamespace(event_sink=self.event_sink), kind, payload)
