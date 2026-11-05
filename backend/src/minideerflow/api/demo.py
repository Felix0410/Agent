from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from minideerflow.tools.calculator import CalculatorError, safe_calculate

router = APIRouter(prefix="/api/demo")


class CalculateRequest(BaseModel):
    expression: str


class CalculateResponse(BaseModel):
    result: str


@router.post("/calculate", response_model=CalculateResponse)
async def calculate_endpoint(request: CalculateRequest) -> CalculateResponse:
    try:
        return CalculateResponse(result=safe_calculate(request.expression))
    except CalculatorError as exc:
        raise HTTPException(422, detail={"code": exc.code, "message": exc.message}) from None
