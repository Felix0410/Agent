"""Run 请求只完成准入与查询，模型执行由生命周期管理的后台 worker 负责。"""

import asyncio

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from minideerflow.agents.service import AgentExecutionError
from minideerflow.api.demo import AgentRequest
from minideerflow.core.model import ModelNotConfigured
from minideerflow.runtime.events import EventBus, EventStreamError, Subscription
from minideerflow.runtime.models import RunAccepted, RunDto
from minideerflow.runtime.repository import RepositoryError
from minideerflow.runtime.runner import RunServiceError

router = APIRouter()
HEARTBEAT_SECONDS = 15


async def event_frames(bus: EventBus, run_id: str, subscription: Subscription):
    """心跳不分配业务 ID，断线仅清理订阅，不取消后台执行。"""
    try:
        while True:
            try:
                event = await asyncio.wait_for(subscription.next_event(), HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            except StopAsyncIteration:
                return
            identifier = "" if event.type == "stream_gap" else f"id: {event.event_id}\n"
            yield f"{identifier}event: {event.type}\ndata: {event.model_dump_json()}\n\n"
            if event.type in ("run_end", "stream_gap"):
                return
    finally:
        await bus.unsubscribe(run_id, subscription)


@router.post("/api/threads/{thread_id}/runs", status_code=202, response_model=RunAccepted)
async def start_run(thread_id: str, body: AgentRequest, request: Request) -> RunAccepted:
    """202 只表示成功接收，完成与失败均通过后续 GET Run 查询。"""
    try:
        return await request.app.state.runner.start_run(thread_id, body.message)
    except RepositoryError as exc:
        status = 404 if exc.code == "THREAD_NOT_FOUND" else 409
        raise HTTPException(status, detail={"code": exc.code, "message": exc.message}) from None
    except ModelNotConfigured:
        raise HTTPException(
            503,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "Set MODEL_NAME and MODEL_API_KEY"},
        ) from None
    except RunServiceError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None
    except AgentExecutionError as exc:
        raise HTTPException(502, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}", response_model=RunDto)
async def get_run(run_id: str, request: Request) -> RunDto:
    try:
        return await request.app.state.repository.get_run(run_id)
    except RepositoryError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}/usage")
async def get_usage(run_id: str, request: Request):
    """统计从SQL恢复；没有Provider数字时为NULL，绝不虚构零费用。"""
    try:
        return await request.app.state.runner.usage.get(run_id)
    except RepositoryError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}/events")
async def get_events(
    run_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> StreamingResponse:
    """存在性、过期和 cursor 都必须在发送 200 流响应头之前校验。"""
    await get_run(run_id, request)
    bus: EventBus = request.app.state.events
    try:
        subscription = await bus.subscribe(run_id, last_event_id)
    except EventStreamError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None
    return StreamingResponse(
        event_frames(bus, run_id, subscription),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=BackgroundTask(bus.unsubscribe, run_id, subscription),
    )
