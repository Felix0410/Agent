"""FastAPI 应用创建入口，P01 仅提供本地调试接口。"""

import logging

from fastapi import FastAPI

from minideerflow.api.demo import router
from minideerflow.config import get_settings


def create_app() -> FastAPI:
    """注册演示 API 和基础健康检查，应用启动不要求模型已配置。"""
    settings = get_settings()
    logging.getLogger("minideerflow").setLevel(settings.log_level)
    app = FastAPI(title="Mini DeerFlow", version="0.1.0")

    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    # 允许直接在 PyCharm 中运行 main.py；仅监听本机，避免暴露无鉴权 Demo。
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
