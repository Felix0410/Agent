"""FastAPI 应用与 SQLite 资源生命周期；保留 P01 调试入口。"""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from minideerflow.api.capabilities import router as capabilities_router
from minideerflow.api.demo import router
from minideerflow.api.files import router as files_router
from minideerflow.api.research import router as research_router
from minideerflow.api.runs import router as runs_router
from minideerflow.api.tasks import router as tasks_router
from minideerflow.api.threads import router as threads_router
from minideerflow.config import get_settings
from minideerflow.research.provider import TavilyProvider
from minideerflow.research.repository import ResearchRepository
from minideerflow.research.service import ResearchService
from minideerflow.runtime.checkpoints import open_checkpointer
from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.events import EventBus
from minideerflow.runtime.plan_repository import PlanRepository
from minideerflow.runtime.plan_service import PlanService
from minideerflow.runtime.repository import RuntimeRepository
from minideerflow.runtime.runner import RunService
from minideerflow.runtime.task_registry import TaskRegistry
from minideerflow.skills.loader import SkillCatalog
from minideerflow.tools.mcp_adapter import register_mcp_tools
from minideerflow.tools.registry import ToolRegistry, register_builtin_tools
from minideerflow.tools.research_tools import register_research_tools
from minideerflow.tools.skill_tools import register_skill_tools
from minideerflow.workspace.repository import WorkspaceRepository
from minideerflow.workspace.service import WorkspaceService
from minideerflow.workspace.storage import WorkspaceStorage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI 应用与 SQLite 资源生命周期管理"""
    # 1. 初始化配置
    settings = get_settings()
    logging.getLogger("minideerflow").setLevel(settings.log_level)
    async with AsyncExitStack() as stack:
        # 2. 初始化数据库连接
        database = await RuntimeDatabase.open(settings.runtime_db_path)
        stack.push_async_callback(database.close)
        await database.init_schema()
        # 3. 初始化检查点数据库连接
        saver = await stack.enter_async_context(open_checkpointer(settings.checkpoint_db_path))
        # 4. 初始化运行时仓库
        repository = RuntimeRepository(database)
        await repository.reconcile_orphans()
        app.state.database = database
        app.state.checkpointer = saver
        app.state.repository = repository
        # 5. 初始化计划仓库
        app.state.plans = PlanRepository(database)
        await app.state.plans.reconcile_orphaned_subtasks()
        # 6. 初始化工作空间仓库
        storage = WorkspaceStorage(settings.workspace_root_path)
        storage.open()
        stack.callback(storage.close)
        app.state.workspace = WorkspaceService(WorkspaceRepository(database), storage)
        # 7. 初始化事件总线
        events = EventBus()
        events.start()
        stack.push_async_callback(events.shutdown)
        app.state.events = events
        # 8. 初始化任务注册器
        registry = TaskRegistry(
            settings.max_subagent_concurrency, settings.max_subagent_calls_per_run
        )
        app.state.task_registry = registry
        stack.push_async_callback(registry.shutdown)
        # 9. 初始化工具注册器
        tool_registry = ToolRegistry()
        register_builtin_tools(tool_registry)
        # 研究服务只连固定Tavily API；无Key保持旧能力且不注册联网工具。
        research_repository = ResearchRepository(database)
        await research_repository.reconcile_orphans()
        key = settings.tavily_api_key
        provider = TavilyProvider(key) if key and key.get_secret_value().strip() else None
        app.state.research = ResearchService(research_repository, provider, app.state.workspace)
        register_research_tools(tool_registry, provider is not None)
        # 10. 初始化 MCP 工具注册器
        await register_mcp_tools(tool_registry, settings.mcp_config_path)
        # 11. 初始化技能工具注册器
        register_skill_tools(tool_registry)
        app.state.skill_service = SkillCatalog(tool_registry)
        tool_registry.freeze()
        app.state.tool_registry = tool_registry
        # 12. 初始化运行服务
        runner = RunService(
            repository,
            saver,
            settings,
            events=events,
            workspace=app.state.workspace,
            plans=PlanService(app.state.plans),
            task_registry=registry,
            tool_registry=tool_registry,
            skill_service=app.state.skill_service,
            research_service=app.state.research,
        )
        # 13. 启动运行服务
        runner.start()
        stack.push_async_callback(runner.shutdown)
        app.state.runner = runner
        yield


def create_app() -> FastAPI:
    """注册演示 API 和基础健康检查，应用启动不要求模型已配置。"""
    app = FastAPI(title="Mini DeerFlow", version="0.1.0", lifespan=lifespan)

    app.include_router(router)
    app.include_router(threads_router)
    app.include_router(runs_router)
    app.include_router(files_router)
    app.include_router(tasks_router)
    app.include_router(capabilities_router)
    app.include_router(research_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    # 允许直接在 PyCharm 中运行 main.py；仅监听本机，避免暴露无鉴权 Demo。
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
