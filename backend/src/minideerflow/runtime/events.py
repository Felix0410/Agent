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
    """在发送流响应头前可明确映射的错误。"""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(eq=False)
class Subscription:
    """快照回放与实时队列共享同一原子注册点；溢出只发一次 gap。"""

    initial: deque[RunEvent]
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    gap: RunEvent | None = None
    closed: bool = False

    async def next_event(self) -> RunEvent:
        """消费有界消息；心跳超时由 Router 控制，不影响队列与 worker。"""
        if self.gap is not None:
            event, self.gap = self.gap, None
            self.initial.clear()
            while not self.queue.empty():
                self.queue.get_nowait()
            self.closed = True
            return event
        if self.initial:
            return self.initial.popleft()
        if self.closed and self.queue.empty():
            raise StopAsyncIteration
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        if item.type == "stream_gap":
            self.gap = None
            self.closed = True
        return item


@dataclass
class _RunBuffer:
    thread_id: str
    events: deque[RunEvent] = field(default_factory=lambda: deque(maxlen=512))
    sequence: int = 0
    closed_at: float | None = None
    subscribers: set[Subscription] = field(default_factory=set)


class EventBus:
    """所有快照/发布/注册动作在同一锁内，不让慢客户端阻塞模型。"""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._runs: dict[str, _RunBuffer] = {}
        self._lock = asyncio.Lock()
        self._clock = clock
        self._pruner: asyncio.Task | None = None

    def start(self) -> None:
        """定期回收终态窗口，避免长期无请求时保留过期内存。"""
        self._pruner = asyncio.create_task(self._prune_loop(), name="event-pruner")

    async def _prune_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            await self.prune()

    def _prune_locked(self) -> None:
        for run_id, record in list(self._runs.items()):
            if record.closed_at is not None and self._clock() - record.closed_at >= 600:
                del self._runs[run_id]

    async def prune(self) -> None:
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
        # 控制事件不分配新序号，也不放进业务事件回放；Router 不为 gap 写 SSE id。
        return RunEvent(
            event_id=f"{run_id}:{record.sequence}",
            run_id=run_id,
            thread_id=record.thread_id,
            type="stream_gap",
            timestamp=utc_now_iso(),
            payload={"code": "EVENT_STREAM_GAP"},
        )

    async def publish(self, run_id: str, kind: str, payload: dict[str, Any]) -> RunEvent:
        """先进入 512 窗口再非阻塞通知；订阅者超限时显式终结为 gap。"""
        async with self._lock:
            record = self._runs[run_id]
            if record.closed_at is not None:
                raise ValueError("run stream already closed")
            record.sequence += 1
            event = RunEvent(
                event_id=f"{run_id}:{record.sequence}",
                run_id=run_id,
                thread_id=record.thread_id,
                type=kind,
                timestamp=utc_now_iso(),
                payload=payload,
            )
            # 1. 缓冲先写，POST 后才订阅也能回放。
            record.events.append(event)
            for subscription in list(record.subscribers):
                # 2. 消费者落后不能拖慢 worker；清理待消费消息，用 gap 唤醒等待者。
                if subscription.queue.full():
                    subscription.gap = self._gap(run_id, record)
                    while not subscription.queue.empty():
                        subscription.queue.get_nowait()
                    subscription.queue.put_nowait(subscription.gap)
                    record.subscribers.discard(subscription)
                else:
                    subscription.queue.put_nowait(event)
            return event

    async def subscribe(self, run_id: str, last_event_id: str | None = None) -> Subscription:
        """先检查过期/cursor，再在同一锁内获得快照并登记实时订阅。"""
        async with self._lock:
            self._prune_locked()
            record = self._runs.get(run_id)
            if record is None:
                raise EventStreamError("EVENT_STREAM_EXPIRED", "Event stream expired", 410)
            cursor = 0
            if last_event_id is not None:
                prefix = f"{run_id}:"
                value = last_event_id[len(prefix) :] if last_event_id.startswith(prefix) else ""
                if (
                    len(value) > 20
                    or not re.fullmatch(r"0|[1-9][0-9]*", value)
                    or int(value) > record.sequence
                ):
                    raise EventStreamError("INVALID_EVENT_CURSOR", "Invalid event cursor", 422)
                cursor = int(value)
            subscription = Subscription(
                deque(e for e in record.events if int(e.event_id.rsplit(":", 1)[1]) > cursor)
            )
            # 若 cursor 之后应有的首条已丢失，不把半段窗口冒充完整流。
            if record.events and cursor < record.sequence - len(record.events):
                subscription.gap = self._gap(run_id, record)
            elif record.closed_at is None:
                record.subscribers.add(subscription)
            else:
                subscription.closed = True
            return subscription

    async def unsubscribe(self, run_id: str, subscription: Subscription) -> None:
        async with self._lock:
            if run_id in self._runs:
                self._runs[run_id].subscribers.discard(subscription)
            subscription.closed = True

    async def close_run(self, run_id: str) -> None:
        """终态提交后保留十分钟，唤醒等待者但不取消任何后台任务。"""
        async with self._lock:
            record = self._runs[run_id]
            if record.closed_at is None:
                record.closed_at = self._clock()
            for subscription in record.subscribers:
                subscription.closed = True
                if not subscription.queue.full():
                    subscription.queue.put_nowait(None)
            record.subscribers.clear()

    async def shutdown(self) -> None:
        """在 Runner 之后清理内存与保留窗口回收任务。"""
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
