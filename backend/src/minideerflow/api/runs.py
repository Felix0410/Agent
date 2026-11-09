"""Run 请求只完成准入与查询，模型执行由生命周期管理的后台 worker 负责。"""

import asyncio

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
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
    """生成事件帧流"""
    try:
        while True:
            try:
                # 等待事件
                event = await asyncio.wait_for(subscription.next_event(), HEARTBEAT_SECONDS)
            # 处理超时异常，发送心跳事件
            except TimeoutError:
                yield ": ping\n\n"
                continue
            # 处理事件流结束异常
            except StopAsyncIteration:
                return
            # 处理正常事件，生成事件帧
            identifier = "" if event.type == "stream_gap" else f"id: {event.event_id}\n"
            # 发送事件帧流
            yield f"{identifier}event: {event.type}\ndata: {event.model_dump_json()}\n\n"
            # 处理运行结束事件或流结束事件
            if event.type in ("run_end", "stream_gap"):
                return
    finally:
        await bus.unsubscribe(run_id, subscription)


@router.post("/api/threads/{thread_id}/runs", status_code=202, response_model=RunAccepted)
async def start_run(thread_id: str, body: AgentRequest, request: Request) -> RunAccepted:
    """启动一个运行任务"""
    try:
        # 调用运行服务启动任务
        return await request.app.state.runner.start_run(thread_id, body.message)
    # 处理仓库异常
    except RepositoryError as exc:
        status = 404 if exc.code == "THREAD_NOT_FOUND" else 409
        raise HTTPException(status, detail={"code": exc.code, "message": exc.message}) from None
    # 处理模型未配置异常
    except ModelNotConfigured:
        raise HTTPException(
            503,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "Set MODEL_NAME and MODEL_API_KEY"},
        ) from None
    # 处理运行服务异常
    except RunServiceError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": exc.message}
        ) from None
    # 处理agent执行异常
    except AgentExecutionError as exc:
        raise HTTPException(502, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}", response_model=RunDto)
async def get_run(run_id: str, request: Request) -> RunDto:
    """查询一个运行任务"""
    try:
        return await request.app.state.repository.get_run(run_id)
    except RepositoryError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None


@router.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request):
    """取消一个运行任务"""
    # 1. 检查请求体是否为空
    if await request.body():
        raise HTTPException(
            422, detail={"code": "INVALID_CANCEL_REQUEST", "message": "No request body expected"}
        )
    try:
        # 2. 调用运行服务取消任务
        run, changed = await request.app.state.runner.cancel(run_id)
        # 3. 根据任务状态判断是否成功取消
        status = 202 if changed or run.status in ("CREATED", "RUNNING") else 200
        # 4. 返回响应
        return JSONResponse(
            status_code=status,
            content={
                "run_id": run.id,
                "status": run.status.value,
                "cancel_requested_at": run.cancel_requested_at,
            },
        )
    # 处理仓库异常
    except RepositoryError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}/usage")
async def get_usage(run_id: str, request: Request):
    """查询一个运行任务的使用情况"""
    try:
        return await request.app.state.runner.usage.get(run_id)
    except RepositoryError as exc:
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None


@router.get("/api/runs/{run_id}/events")
async def get_events(
    run_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> StreamingResponse:
    """订阅一个运行任务的事件流"""
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
