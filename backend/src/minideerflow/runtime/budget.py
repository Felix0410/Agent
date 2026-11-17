"""每Run共享、先预扣的预算，不把token估算当Provider实际用量。"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import uuid4

from minideerflow.runtime.usage import UsageCall


class BudgetError(Exception):
    def __init__(self, code="BUDGET_EXCEEDED", reason="UNCOMPRESSIBLE"):
        super().__init__(code)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class RunBudget:
    """单次Run的预算"""

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


@dataclass(frozen=True)
class ContextEstimate:
    """一次请求的统一结果；预估与真实Provider Token没有互相覆盖关系。"""

    breakdown: BudgetBreakdown
    estimated_tokens: int
    unit: str = "estimated_tokens_v2"
    estimator_version: str = "utf8_conservative_v2"


class ContextEstimator(Protocol):
    """计数策略只接收本次实际消息和公开Schema，不依赖模型名称猜窗口。"""

    def estimate(self, messages, tools=(), system_message=None, **limits) -> ContextEstimate: ...


class ConservativeContextEstimator:
    """未知兼容模型使用每UTF-8代理字节一Token的保守预估，不宣称精确计数。"""

    def estimate(self, messages, tools=(), system_message=None, **limits):
        breakdown = budget_breakdown(messages, tools, system_message, **limits)
        # 继续保留字节硬保护；不采用英文常见的4字节/Token换算去放行中文或长JSON。
        return ContextEstimate(breakdown, breakdown.total_bytes)


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
    """单次Run的预算跟踪器"""

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
        self.context_soft_limit = 24000
        self.context_hard_limit = 48000
        self.estimator: ContextEstimator = ConservativeContextEstimator()
        self.model_context_window_tokens = None
        self.model_output_reserve_tokens = 2048

    async def initialize(self):
        await self.repository.start(
            self.run_id,
            {
                **asdict(self.budget),
                "estimate_unit": "utf8_json_bytes_v1",
                "estimator_version": "utf8_conservative_v2",
                "v2_unit": "estimated_tokens_v2",
                "model_context_window_tokens": self.model_context_window_tokens,
                "model_output_reserve_tokens": self.model_output_reserve_tokens,
            },
        )

    async def reserve_context(self, estimate, source="parent"):
        """窗口只在用户确认后启用；与字节上限同时检查，不猜模型实际窗口。"""
        breakdown = estimate.breakdown
        window = self.model_context_window_tokens
        if (
            window is not None
            and estimate.estimated_tokens + self.model_output_reserve_tokens > window
        ):
            await self.record_context(breakdown, "MODEL_CONTEXT_WINDOW_EXCEEDED")
            raise BudgetError("CONTEXT_BUDGET_EXCEEDED", "MODEL_CONTEXT_WINDOW_EXCEEDED")
        if breakdown.total_bytes > min(self.context_hard_limit, breakdown.hard_bytes):
            await self.record_context(breakdown, "ACTIVE_MESSAGES")
            raise BudgetError("CONTEXT_BUDGET_EXCEEDED", "ACTIVE_MESSAGES")
        return await self.reserve(
            "model", breakdown.total_bytes, source, estimate_v2=estimate.estimated_tokens
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
        if self.exceeded or time.monotonic() - self.started >= self.budget.max_seconds:
            self.exceeded = True
            raise BudgetError()

    async def reserve(self, kind, estimate=0, source="parent", *, estimate_v2=None):
        """预扣预算"""
        # 1. 父子共享同一锁，同一预算
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
            # 2. 预扣同时覆盖次数与累计输入；失败也不会返还。
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
            # 3. 唯一ID持久化完成后才返回给真正执行者。
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
