"""Thread HTTP 边界：只校验请求和调用 Repository，不执行 SQL 或模型。"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from minideerflow.runtime.models import RunDto, ThreadDto, ThreadTitle
from minideerflow.runtime.repository import RepositoryError, RuntimeRepository

router = APIRouter(prefix="/api/threads")


class CreateThreadRequest(BaseModel):
    title: ThreadTitle = "新会话"


@router.post("", status_code=201, response_model=ThreadDto)
async def create_thread(body: CreateThreadRequest, request: Request) -> ThreadDto:
    repository: RuntimeRepository = request.app.state.repository
    return await repository.create_thread(body.title)


@router.get("", response_model=list[ThreadDto])
async def list_threads(request: Request) -> list[ThreadDto]:
    return await request.app.state.repository.list_threads()


@router.get("/{thread_id}/runs", response_model=list[RunDto])
async def list_runs(
    thread_id: str, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[RunDto]:
    try:
        return await request.app.state.repository.list_runs(thread_id, limit)
    except RepositoryError as exc:
        # 这里只读历史；不存在的 Thread 不能伪装成尚无历史的空会话。
        if exc.code != "THREAD_NOT_FOUND":
            raise
        raise HTTPException(404, detail={"code": exc.code, "message": exc.message}) from None
