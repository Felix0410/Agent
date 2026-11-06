"""Run 请求只完成准入与查询，模型执行由生命周期管理的后台 worker 负责。"""

from fastapi import APIRouter, HTTPException, Request

from minideerflow.agents.service import AgentExecutionError
from minideerflow.api.demo import AgentRequest
from minideerflow.core.model import ModelNotConfigured
from minideerflow.runtime.models import RunAccepted, RunDto
from minideerflow.runtime.repository import RepositoryError
from minideerflow.runtime.runner import RunServiceError

router = APIRouter()


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
