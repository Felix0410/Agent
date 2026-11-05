import logging

from fastapi import FastAPI

from minideerflow.api.demo import router
from minideerflow.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.getLogger("minideerflow").setLevel(settings.log_level)
    app = FastAPI(title="Mini DeerFlow", version="0.1.0")

    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
