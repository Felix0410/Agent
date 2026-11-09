"""研究HTTP仅展示真实历史，不提供绕过Agent预算的联网入口。"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from minideerflow.runtime.repository import RepositoryError

router = APIRouter(prefix="/api")


@router.get("/research/status")
async def status(request: Request):
    enabled = request.app.state.research.provider is not None
    return {
        "enabled": enabled,
        "provider": "tavily" if enabled else None,
        "status": "available" if enabled else "not_configured",
    }


@router.get("/runs/{run_id}/research/evidence")
async def evidence(run_id: str, request: Request):
    try:
        run = await request.app.state.repository.get_run(run_id)
        return await request.app.state.research.repository.list(run_id, run.thread_id)
    except RepositoryError:
        return JSONResponse(
            status_code=404, content={"code": "RUN_NOT_FOUND", "message": "Run not found"}
        )


@router.get("/runs/{run_id}/research/report")
async def report(run_id: str, request: Request):
    try:
        await request.app.state.repository.get_run(run_id)
        return None
    except RepositoryError:
        return JSONResponse(
            status_code=404, content={"code": "RUN_NOT_FOUND", "message": "Run not found"}
        )
