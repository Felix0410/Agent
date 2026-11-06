"""事件窗口/慢消费者/心跳的确定性测试，不等待真实十分钟。"""

import asyncio

import pytest

from minideerflow.api import runs
from minideerflow.runtime.events import EventBus, EventStreamError


def test_sequence_replay_and_run_isolation():
    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        await bus.ensure_run("other", "other-t")
        for kind in ["run_start", "assistant_delta", "run_end"]:
            await bus.publish("r", kind, {})
        await bus.close_run("r")
        sub = await bus.subscribe("r")
        assert [(await sub.next_event()).event_id for _ in range(3)] == ["r:1", "r:2", "r:3"]
        with pytest.raises(StopAsyncIteration):
            await sub.next_event()
        sub = await bus.subscribe("r", "r:1")
        assert (await sub.next_event()).event_id == "r:2"
        assert (await sub.next_event()).event_id == "r:3"
        empty = await bus.subscribe("r", "r:3")
        with pytest.raises(StopAsyncIteration):
            await empty.next_event()
        assert bus._runs["other"].sequence == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("cursor", ["other:1", "r:-1", "r:xyz", "r:999", "r:01"])
def test_invalid_cursor(cursor):
    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        with pytest.raises(EventStreamError) as error:
            await bus.subscribe("r", cursor)
        assert error.value.status_code == 422

    asyncio.run(scenario())


def test_snapshot_and_live_subscription_no_gap():
    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        await bus.publish("r", "run_start", {})
        sub = await bus.subscribe("r")
        await bus.publish("r", "assistant_delta", {"text": "x"})
        assert (await sub.next_event()).event_id == "r:1"
        assert (await sub.next_event()).event_id == "r:2"
        await bus.unsubscribe("r", sub)
        assert not bus._runs["r"].subscribers

    asyncio.run(scenario())


def test_missing_initial_window_and_old_cursor_send_one_gap():
    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        for _ in range(514):
            await bus.publish("r", "assistant_delta", {"text": "x"})
        assert len(bus._runs["r"].events) == 512
        for cursor in [None, "r:1"]:
            sub = await bus.subscribe("r", cursor)
            event = await sub.next_event()
            assert event.type == "stream_gap"
            assert event.payload == {"code": "EVENT_STREAM_GAP"}
            with pytest.raises(StopAsyncIteration):
                await sub.next_event()
        # cursor=2 后需要的首个序号是3，仍完整保留，允许连续回放。
        sub = await bus.subscribe("r", "r:2")
        assert (await sub.next_event()).event_id == "r:3"

    asyncio.run(scenario())


def test_slow_subscriber_never_blocks_publisher():
    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        sub = await bus.subscribe("r")
        async with asyncio.timeout(1):
            for _ in range(100):
                await bus.publish("r", "assistant_delta", {})
        assert sub.queue.qsize() <= 64
        assert (await sub.next_event()).type == "stream_gap"
        with pytest.raises(StopAsyncIteration):
            await sub.next_event()
        assert not bus._runs["r"].subscribers

    asyncio.run(scenario())


def test_expiration_and_shutdown():
    async def scenario():
        now = [0.0]
        bus = EventBus(clock=lambda: now[0])
        bus.start()
        await bus.ensure_run("r", "t")
        await bus.publish("r", "run_end", {})
        await bus.close_run("r")
        now[0] = 599
        assert (await (await bus.subscribe("r")).next_event()).type == "run_end"
        now[0] = 600
        await bus.prune()
        with pytest.raises(EventStreamError) as error:
            await bus.subscribe("r")
        assert error.value.status_code == 410
        await bus.shutdown()
        assert bus._pruner.done()

    asyncio.run(scenario())


def test_heartbeat_keeps_stream_alive_and_disconnect_cleans_subscription(monkeypatch):
    monkeypatch.setattr(runs, "HEARTBEAT_SECONDS", 0.001)

    async def scenario():
        bus = EventBus()
        await bus.ensure_run("r", "t")
        sub = await bus.subscribe("r")
        frames = runs.event_frames(bus, "r", sub)
        assert await anext(frames) == ": ping\n\n"
        assert bus._runs["r"].sequence == 0
        await bus.publish("r", "run_start", {})
        frame = await anext(frames)
        assert "id: r:1\nevent: run_start\ndata:" in frame
        await frames.aclose()
        assert not bus._runs["r"].subscribers

    asyncio.run(scenario())
