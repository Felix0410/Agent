"""仅公开能力目录，不接受执行、注册或权限变更。"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/tools")
async def tools(request: Request):
    """列表仅含安全的工具名/来源/能力级别/状态。"""
    return request.app.state.tool_registry.list_catalog()


@router.get("/skills")
async def skills(request: Request):
    """真实元信息与脱敏警告，既不展示正文也不能安装。"""
    return request.app.state.skill_service.catalog()
