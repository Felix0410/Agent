"""P01 演示 API 局部测试：计算、Agent 参数和错误映射。"""

import pytest
from fastapi.testclient import TestClient

from minideerflow.agents.service import AgentExecutionError, AgentResponse
from minideerflow.api import demo
from minideerflow.config import Settings, get_settings
from minideerflow.main import app

client = TestClient(app)


def test_calculator_api() -> None:
    response = client.post("/api/demo/calculate", json={"expression": "(12+8)*3"})
    assert response.status_code == 200
    assert response.json() == {"result": "60"}


def test_calculator_error() -> None:
    response = client.post("/api/demo/calculate", json={"expression": "1/0"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CALC_DIV_ZERO"


@pytest.mark.parametrize("message", ["", "  ", "x" * 2001, 42, None])
def test_agent_invalid_input(message) -> None:
    assert client.post("/api/demo/agent", json={"message": message}).status_code == 422


def test_agent_success(monkeypatch) -> None:
    async def fake(message):
        assert message == "hello"
        return AgentResponse(answer="Hello", tool_calls=[])

    monkeypatch.setattr(demo, "run_agent_once", fake)
    response = client.post("/api/demo/agent", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json() == {"answer": "Hello", "tool_calls": []}


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("MODEL_TIMEOUT", 504),
        ("MODEL_UPSTREAM_ERROR", 502),
        ("AGENT_EXECUTION_FAILED", 502),
    ],
)
def test_agent_error_mapping(monkeypatch, code, status) -> None:
    # 模拟下游错误，只验证 HTTP 状态码及脱敏后的稳定业务消息。
    async def fake(message):
        raise AgentExecutionError(code, "Safe message")

    monkeypatch.setattr(demo, "run_agent_once", fake)
    response = client.post("/api/demo/agent", json={"message": "hello"})
    assert response.status_code == status
    assert response.json()["detail"] == {"code": code, "message": "Safe message"}


def test_model_not_configured(monkeypatch) -> None:
    # 无模型配置时 Agent 返回 503，但健康检查仍应独立可用。
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in ["MODEL_NAME", "MODEL_API_KEY", "MODEL_BASE_URL"]:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    try:
        response = client.post("/api/demo/agent", json={"message": "hello"})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "MODEL_NOT_CONFIGURED"
        assert client.get("/health").json() == {"status": "ok"}
    finally:
        get_settings.cache_clear()
