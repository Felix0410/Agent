"""父图结构化计划：完整替换通道，不使用追加 reducer。"""

from typing import Literal, NotRequired

from langchain.agents import AgentState
from pydantic import BaseModel, ConfigDict, Field


class TodoInput(BaseModel):
    """模型可写的业务字段，位置由服务器按列表顺序产生。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    todo_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=120)
    status: Literal["pending", "in_progress", "completed"]


class TodoItem(TodoInput):
    position: int = Field(ge=0, le=7)


class P04AgentState(AgentState):
    """父图结构化计划状态"""

    # 继承默认字段 messages: list[BaseMessage]
    todos: NotRequired[list[dict]]
    context_summary: NotRequired[str]
