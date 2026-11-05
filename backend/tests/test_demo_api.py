from fastapi.testclient import TestClient

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
