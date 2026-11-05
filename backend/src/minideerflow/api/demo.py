"""P01 本地演示接口：健康检查以外的计算和 Agent 请求入口。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from minideerflow.agents.service import (
    AgentExecutionError,
    AgentResponse,
    run_agent_once,
    validate_message,
)
from minideerflow.core.model import ModelNotConfigured
from minideerflow.tools.calculator import CalculatorError, safe_calculate

# P01 的临时调试路由；P02 再引入正式 Thread / Run 协议。
router = APIRouter(prefix="/api/demo")


class CalculateRequest(BaseModel):
    expression: str


class CalculateResponse(BaseModel):
    result: str


class AgentRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        return validate_message(value)


@router.post("/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest) -> AgentResponse:
    """返回一次 Agent 执行结果，统一转换模型缺失、超时与上游错误。"""
    try:
        return await run_agent_once(request.message)
    # 业务错误只映射为稳定状态码与短消息，不向浏览器传递内部异常。
    except ModelNotConfigured:
        raise HTTPException(
            503,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": "Set MODEL_NAME and MODEL_API_KEY"},
        ) from None
    except AgentExecutionError as exc:
        status = 504 if exc.code == "MODEL_TIMEOUT" else 502
        raise HTTPException(status, detail={"code": exc.code, "message": exc.message}) from None


@router.post("/calculate", response_model=CalculateResponse)
async def calculate_endpoint(request: CalculateRequest) -> CalculateResponse:
    """直接调用计算纯函数；错误以可区分的 422 业务码返回。"""
    try:
        return CalculateResponse(result=safe_calculate(request.expression))
    except CalculatorError as exc:
        raise HTTPException(422, detail={"code": exc.code, "message": exc.message}) from None
