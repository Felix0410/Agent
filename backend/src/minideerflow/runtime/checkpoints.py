"""独立管理官方 SQLite Saver，不直接操作其内部表。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def open_checkpointer(path: Path) -> AsyncIterator[AsyncSqliteSaver]:
    """打开受控本地检查点库，退出时由官方上下文管理器关闭连接。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        # from_conn_string 无 serde 参数；显式使用严格内置类型集合，不开放任意导入或 pickle。
        saver.serde = JsonPlusSerializer(allowed_msgpack_modules=None)
        yield saver


def thread_config(thread_id: str) -> RunnableConfig:
    """同一业务 Thread 始终映射到相同 Graph 会话，不混用 run_id。"""
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 12}
