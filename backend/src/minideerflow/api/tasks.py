"""计划与任务仅提供历史读取，写入只允许可信 Agent Tool。"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from minideerflow.runtime.repository import RepositoryError

router = APIRouter(prefix="/api/runs")


@router.get("/{run_id}/todos")
async def get_todos(run_id: str, request: Request):
    """未知 Run 与没有计划的已知 Run 明确区分。"""
    try:
        return await request.app.state.plans.list_todos(run_id)
    except RepositoryError:
        return JSONResponse(
            status_code=404, content={"code": "RUN_NOT_FOUND", "message": "Run not found"}
        )


@router.get("/{run_id}/subtasks")
async def get_subtasks(run_id: str, request: Request):
    """只从业务库读取真实任务，绝不解析助手文字。"""
    try:
        return await request.app.state.plans.list_subtasks(run_id)
    except RepositoryError:
        return JSONResponse(
            status_code=404, content={"code": "RUN_NOT_FOUND", "message": "Run not found"}
        )
