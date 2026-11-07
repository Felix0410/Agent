"""运行时业务数据合同；Graph 消息由独立 Checkpointer 保存。"""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from minideerflow.agents.service import ToolTrace

ThreadTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ThreadDto(BaseModel):
    id: str
    title: ThreadTitle = "新会话"
    needs_recovery: bool = False
    created_at: str
    updated_at: str


class RunDto(BaseModel):
    id: str
    thread_id: str
    input_message: str
    status: RunStatus
    answer: str | None = None
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    error_code: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested_at: str | None = None


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    thread_id: str
    type: str
    timestamp: str
    payload: dict[str, Any]
    task_id: str | None = None


class RunAccepted(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["CREATED"] = "CREATED"


def utc_now_iso() -> str:
    """统一使用带 UTC 时区的 ISO8601 文本，便于 SQLite 按时间排序。"""
    return datetime.now(UTC).isoformat()
