"""FastAPI 应用与 SQLite 资源生命周期；保留 P01 调试入口。"""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from minideerflow.api.demo import router
from minideerflow.api.threads import router as threads_router
from minideerflow.config import get_settings
from minideerflow.runtime.checkpoints import open_checkpointer
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.repository import RuntimeRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """按依赖顺序初始化资源；启动失败和正常退出都按反序释放连接。"""
    settings = get_settings()
    logging.getLogger("minideerflow").setLevel(settings.log_level)
    async with AsyncExitStack() as stack:
        # 1. 先初始化业务库，并立刻登记清理，避免后续初始化失败泄漏连接。
        database = await RuntimeDatabase.open(settings.runtime_db_path)
        stack.push_async_callback(database.close)
        await database.init_schema()
        # 2. 官方 Saver 独立持有另一个连接，不读写业务库内部状态。
        saver = await stack.enter_async_context(open_checkpointer(settings.checkpoint_db_path))
        repository = RuntimeRepository(database)
        await repository.reconcile_orphans()
        app.state.database = database
        app.state.checkpointer = saver
        app.state.repository = repository
        # 3. A 只提供 Thread API；后台 Runner/SSE 尚未建立。
        yield


def create_app() -> FastAPI:
    """注册演示 API 和基础健康检查，应用启动不要求模型已配置。"""
    app = FastAPI(title="Mini DeerFlow", version="0.1.0", lifespan=lifespan)

    app.include_router(router)
    app.include_router(threads_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    # 允许直接在 PyCharm 中运行 main.py；仅监听本机，避免暴露无鉴权 Demo。
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
