"""Thread HTTP 边界：只校验请求和调用 Repository，不执行 SQL 或模型。"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from minideerflow.runtime.models import RunDto, ThreadDto, ThreadTitle
from minideerflow.runtime.repository import RepositoryError, RuntimeRepository

# 前缀路径
router = APIRouter(prefix="/api/threads")


class CreateThreadRequest(BaseModel):
    title: ThreadTitle = "新会话"


@router.post("", status_code=201, response_model=ThreadDto)
async def create_thread(body: CreateThreadRequest, request: Request) -> ThreadDto:
    """创建新会话"""
    repository: RuntimeRepository = request.app.state.repository
    return await repository.create_thread(body.title)


@router.get("", response_model=list[ThreadDto])
async def list_threads(request: Request) -> list[ThreadDto]:
    """列出所有会话"""
    return await request.app.state.repository.list_threads()


@router.get("/{thread_id}/runs", response_model=list[RunDto])
async def list_runs(
    thread_id: str, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[RunDto]:
    """列出会话 thread_id 的所有run"""
    try:
        return await request.app.state.repository.list_runs(thread_id, limit)
    except RepositoryError as exc:
        if exc.code != "THREAD_NOT_FOUND":
            raise
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None
