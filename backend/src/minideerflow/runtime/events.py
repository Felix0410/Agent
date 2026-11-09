"""有限内存 SSE 窗口：业务终态仍以 Repository 为准。"""

import asyncio
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from minideerflow.runtime.models import RunEvent, utc_now_iso


class EventStreamError(Exception):
    """事件流错误基类"""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(eq=False)
class Subscription:
    """事件订阅"""

    initial: deque[RunEvent] # 初始事件队列
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=64)) # 实时事件队列
    gap: RunEvent | None = None # 流 gap 事件
    closed: bool = False # 是否已关闭

    async def next_event(self) -> RunEvent:
        """获取下一个事件"""
        # 如果有 gap 事件，先返回 gap 事件
        if self.gap is not None:
            # 获取 gap 事件并重置 gap 事件为 None
            event, self.gap = self.gap, None
            # 清空初始事件队列
            self.initial.clear()
            # 清空实时事件队列
            while not self.queue.empty():
                self.queue.get_nowait()
            self.closed = True
            return event
        # 如果还有初始事件，先处理初始事件队列
        if self.initial:
            return self.initial.popleft()
        # 如果订阅已关闭，直接返回
        if self.closed and self.queue.empty():
            raise StopAsyncIteration
        # 处理实时事件队列
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        if item.type == "stream_gap":
            self.gap = None
            self.closed = True
        return item


@dataclass
class _RunBuffer:
    """Run 事件缓冲区"""
    thread_id: str
    events: deque[RunEvent] = field(default_factory=lambda: deque(maxlen=512))
    sequence: int = 0
    closed_at: float | None = None
    subscribers: set[Subscription] = field(default_factory=set)


class EventBus:
    """事件总线：管理 Run 事件缓冲与订阅。"""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._runs: dict[str, _RunBuffer] = {}
        self._lock = asyncio.Lock()
        self._clock = clock
        self._pruner: asyncio.Task | None = None

    def start(self) -> None:
        """启动事件"""
        self._pruner = asyncio.create_task(self._prune_loop(), name="event-pruner")

    async def _prune_loop(self) -> None:
        """清理过期的 Run 事件缓冲区，每 30 秒调用一次。"""
        while True:
            await asyncio.sleep(30)
            await self.prune()

    def _prune_locked(self) -> None:
        """清理过期的 Run 事件缓冲区，需要在锁下调用。"""
        for run_id, record in list(self._runs.items()):
            if record.closed_at is not None and self._clock() - record.closed_at >= 600:
                del self._runs[run_id]

    async def prune(self) -> None:
        """清理过期的 Run 事件缓冲区"""
        async with self._lock:
            self._prune_locked()

    async def ensure_run(self, run_id: str, thread_id: str) -> None:
        """在成功创建 Run 后、入队前准备缓冲，首订阅不会错过开头。"""
        async with self._lock:
            self._prune_locked()
            if run_id not in self._runs:
                self._runs[run_id] = _RunBuffer(thread_id)
            elif self._runs[run_id].thread_id != thread_id:
                raise ValueError("run/thread mismatch")

    def _gap(self, run_id: str, record: _RunBuffer) -> RunEvent:
        """生成流 gap 事件，用于通知订阅者丢失了事件。"""
        return RunEvent(
            event_id=f"{run_id}:{record.sequence}",
            run_id=run_id,
            thread_id=record.thread_id,
            type="stream_gap",
            timestamp=utc_now_iso(),
            payload={"code": "EVENT_STREAM_GAP"},
        )

    async def publish(self, run_id: str, kind: str, payload: dict[str, Any]) -> RunEvent:
        """发布事件"""
        # 1. 上锁
        async with self._lock:
            # 2. 检查 Run 是否已关闭
            record = self._runs[run_id]
            if record.closed_at is not None:
                raise ValueError("run stream already closed")
            # 3. 生成事件
            record.sequence += 1
            event = RunEvent(
                event_id=f"{run_id}:{record.sequence}",
                run_id=run_id,
                thread_id=record.thread_id,
                type=kind,
                timestamp=utc_now_iso(),
                payload=payload,
            )
            # 4. 缓冲事件写入
            record.events.append(event)
            # 5. 通知订阅者
            for subscription in list(record.subscribers):
                # 5.1 处理慢订阅者
                if subscription.queue.full():
                    # 5.2 创建 gap 事件通知订阅者丢失了事件
                    subscription.gap = self._gap(run_id, record)
                    # 5.3 清空积压的实时事件队列
                    while not subscription.queue.empty():
                        subscription.queue.get_nowait()
                    # 5.4 发送 gap 事件
                    subscription.queue.put_nowait(subscription.gap)
                    # 5.5 从订阅列表中移除该订阅者，订阅者需重新连接
                    record.subscribers.discard(subscription)
                else:
                    # 5.6 处理正常订阅者，将事件添加到实时事件队列
                    subscription.queue.put_nowait(event)
            return event

    async def subscribe(self, run_id: str, last_event_id: str | None = None) -> Subscription:
        """订阅事件"""
        # 1. 上锁
        async with self._lock:
            # 2. 清理过期 Run 事件缓冲区
            self._prune_locked()
            # 3. 获取 Run 公共事件缓冲区
            record = self._runs.get(run_id)
            if record is None:
                raise EventStreamError("EVENT_STREAM_EXPIRED", "Event stream expired", 410)
            cursor = 0
            # 4. 判断是否需要恢复订阅
            if last_event_id is not None:
                # 4.1 拿到游标id和游标值
                prefix = f"{run_id}:"
                value = last_event_id[len(prefix) :] if last_event_id.startswith(prefix) else ""
                # 4.2 检查游标值是否有效
                if (
                    len(value) > 20
                    or not re.fullmatch(r"0|[1-9][0-9]*", value)
                    or int(value) > record.sequence
                ):
                    raise EventStreamError("INVALID_EVENT_CURSOR", "Invalid event cursor", 422)
                # 4.3 有效游标，更新游标值
                cursor = int(value)
            # 5. 创建订阅并根据游标值初始化恢复初始事件队列
            subscription = Subscription(
                deque(e for e in record.events if int(e.event_id.rsplit(":", 1)[1]) > cursor)
            )
            # 6. 检查当前游标值是否在有效范围内，即是否丢失了首条事件
            if record.events and cursor < record.sequence - len(record.events):
                # 发送 gap 事件，通知订阅者丢失了首条事件，无法恢复订阅
                subscription.gap = self._gap(run_id, record)
            # 7. 有效游标，订阅未关闭，添加到订阅列表
            elif record.closed_at is None:
                record.subscribers.add(subscription)
            # 8. 订阅已关闭，直接返回
            else:
                subscription.closed = True
            return subscription

    async def unsubscribe(self, run_id: str, subscription: Subscription) -> None:
        """取消订阅事件"""
        async with self._lock:
            if run_id in self._runs:
                self._runs[run_id].subscribers.discard(subscription)
            subscription.closed = True

    async def close_run(self, run_id: str) -> None:
        """关闭 Run 事件缓冲区"""
        async with self._lock:
            record = self._runs[run_id]
            # 检查是否还有订阅者未关闭
            if record.closed_at is None:
                record.closed_at = self._clock()
            # 通知订阅者 Run 已关闭
            for subscription in record.subscribers:
                subscription.closed = True
                if not subscription.queue.full():
                    subscription.queue.put_nowait(None)
            record.subscribers.clear()

    async def shutdown(self) -> None:
        """关闭事件流"""
        if self._pruner is not None:
            self._pruner.cancel()
            await asyncio.gather(self._pruner, return_exceptions=True)
        async with self._lock:
            for record in self._runs.values():
                for subscription in record.subscribers:
                    subscription.closed = True
                    if not subscription.queue.full():
                        subscription.queue.put_nowait(None)
            self._runs.clear()
