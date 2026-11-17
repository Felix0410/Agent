"""DeerFlow式薄适配：官方分区/滚动摘要，只观察调用、状态和取消。"""

import asyncio
import time
from contextvars import ContextVar

from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.callbacks.base import BaseCallbackManager
from langchain_core.messages import RemoveMessage
from langgraph.constants import TAG_NOSTREAM

from minideerflow.runtime.budget import estimate_messages

_tracker = ContextVar("summary_usage_tracker", default=None)


class SummarizationError(Exception):
    """仅暴露稳定错误类别，Provider异常正文不进入状态或页面。"""


class SummaryUsageCallback(AsyncCallbackHandler):
    """观察官方摘要模型的每个真实尝试，重试也分别记账而不统计流片段。"""

    raise_error = True

    def __init__(self):
        self.calls = {}
        self.lock = asyncio.Lock()

    async def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        tracker = _tracker.get()
        if tracker is not None:
            reservation = await tracker.reserve(
                "model", sum(estimate_messages(batch) for batch in messages), "summary"
            )
            self.calls[run_id] = tracker, reservation

    async def on_llm_end(self, response, *, run_id, **kwargs):
        generation = response.generations[0][0] if response.generations else None
        usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
        await self.finish_call(run_id, "ok", usage)

    async def on_llm_error(self, error, *, run_id, **kwargs):
        await self.finish_call(
            run_id, "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
        )

    async def finish_call(self, run_id, status, usage=None):
        async with self.lock:
            entry = self.calls.pop(run_id, None)
            if entry:
                tracker, reservation = entry
                await tracker.finish(reservation, status, usage)

    async def close_pending(self, status):
        """框架取消时回调可能仍在shield收尾，等待同一锁后再发布权威终态。"""
        async with self.lock:
            for tracker, reservation in list(self.calls.values()):
                await tracker.finish(reservation, status)
            self.calls.clear()


class ObservedSummarizationMiddleware(SummarizationMiddleware):
    """直接委托锁版官方算法，不重写cutoff、消息分区、裁剪或状态替换。"""

    def __init__(self, model, *, source="parent", **kwargs):
        self.source = source
        self.usage_callback = SummaryUsageCallback()
        # 1. 对齐DeerFlow v2的TAG_NOSTREAM；本锁版提供公开summarizer扩展点，
        # 使用同配置模型的浅副本挂观察回调，不改框架私有Runnable或model/profile。
        callbacks = model.callbacks
        if isinstance(callbacks, BaseCallbackManager):
            callbacks = callbacks.copy()
            callbacks.add_handler(self.usage_callback)
        else:
            callbacks = [*(callbacks or []), self.usage_callback]
        summary_model = model.model_copy(
            update={"callbacks": callbacks, "tags": [*(model.tags or []), TAG_NOSTREAM]}
        )
        super().__init__(model=model, summarizer=summary_model, **kwargs)

    async def _acreate_summary(self, messages_to_summarize):
        try:
            summary = await super()._acreate_summary(messages_to_summarize)
            if not summary.strip():
                raise SummarizationError("SUMMARY_FAILED")
            return summary
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise
        except Exception:  # noqa: BLE001 - 只传播稳定摘要错误，不把Provider正文写入Checkpoint
            raise SummarizationError("SUMMARY_FAILED") from None

    async def abefore_model(self, state, runtime):
        # 1. 只检查取消/Deadline；消息分区和摘要调用完全委托官方实现。
        tracker = getattr(runtime.context, "budget_tracker", None)
        if tracker:
            await tracker.check()
        token = _tracker.set(tracker)
        started = time.monotonic()
        before = len(state["messages"])
        before_tokens = self.token_counter(state["messages"])
        try:
            result = await super().abefore_model(state, runtime)
        except BaseException as exc:
            await self.usage_callback.close_pending(
                "cancelled" if isinstance(exc, asyncio.CancelledError) else "error"
            )
            raise
        finally:
            _tracker.reset(token)
        if result and tracker:
            # 2. 官方替换准备成功后，记录纯数值观察；不修改其消息或Todo更新。
            messages = [m for m in result["messages"] if not isinstance(m, RemoveMessage)]
            tracker.compactions += 1
            diagnostic = {
                "old_message_count": before,
                "new_message_count": len(messages),
                "estimated_before": before_tokens,
                "estimated_after": self.token_counter(messages),
                "estimate_unit": "langchain_approximate_tokens",
                "reason": "NATIVE_THRESHOLD",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "source": self.source,
            }
            await tracker.repository.summary_observation(tracker.run_id, diagnostic)
            await tracker.flush()
            await tracker.emit("context_compacted", {"run_id": tracker.run_id, **diagnostic})
        return result


def summary_configuration(settings):
    """未知窗口使用可见的近似Token/消息触发；已确认窗口仅收紧摘要触发参数。"""
    trigger = settings.summarization_trigger_tokens
    trim = settings.summarization_trim_tokens
    window = settings.model_context_window_tokens
    if window is not None:
        trigger = min(trigger, max(1, int(window * 0.65)))
        trim = min(trim, max(1, window // 2))
    return {
        "enabled": settings.summarization_enabled,
        "trigger_tokens": trigger,
        "trigger_messages": settings.summarization_trigger_messages,
        "keep_messages": settings.summarization_keep_messages,
        "trim_tokens": trim,
        "estimate_unit": "langchain_approximate_tokens",
        "confirmed_model_window": window,
    }


def summarization_middleware(model, settings, *, source="parent"):
    """父/子图共用官方摘要策略；Child仍由既有35秒时限和只读Guard约束。"""
    config = summary_configuration(settings)
    if not config["enabled"]:
        return []
    return [
        ObservedSummarizationMiddleware(
            model,
            source=source,
            trigger=[
                ("tokens", config["trigger_tokens"]),
                ("messages", config["trigger_messages"]),
            ],
            keep=("messages", config["keep_messages"]),
            trim_tokens_to_summarize=config["trim_tokens"],
        )
    ]
