"""委派 DTO 统一定义，历史权威来自 SQL。"""

from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    summary: str = Field(default="", max_length=1600)
    error_code: str | None = None
    source_file_ids: list[str] = Field(default_factory=list)
    truncated: bool = False


class TaskRecord(BaseModel):
    id: str
    run_id: str
    thread_id: str
    agent_type: str
    description: str
    todo_id: str | None = None
    status: TaskStatus
    result_summary: str | None = None
    error_code: str | None = None
    source_file_ids: list[str] = Field(default_factory=list)
    truncated: bool = False
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
