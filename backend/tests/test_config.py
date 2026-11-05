from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from minideerflow.config import get_settings


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in (
        "APP_ENV",
        "LOG_LEVEL",
        "MODEL_NAME",
        "MODEL_API_KEY",
        "MODEL_BASE_URL",
        "MODEL_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"


def test_settings_reject_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INVALID")
    with pytest.raises(ValidationError) as exc_info:
        get_settings()
    assert exc_info.value.errors()[0]["loc"] == ("log_level",)


def test_optional_model_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ["MODEL_NAME", "MODEL_API_KEY", "MODEL_BASE_URL"]:
        monkeypatch.delenv(name, raising=False)
    settings = get_settings()
    assert settings.model_name is None
    assert settings.model_api_key is None
    assert settings.model_base_url is None


def test_model_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-secret")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:9999/v1")
    settings = get_settings()
    assert "unit-test-secret" not in repr(settings)
    assert "unit-test-secret" not in settings.model_dump_json()
    assert settings.model_api_key.get_secret_value() == "unit-test-secret"


def test_model_factory_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from minideerflow.core.model import ModelNotConfigured, build_chat_model

    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(ModelNotConfigured):
        build_chat_model(get_settings())


def test_model_factory_constructs_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from minideerflow.core.model import build_chat_model

    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-secret")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:9999/v1")
    model = build_chat_model(get_settings())
    assert model.model_name == "test-model"
    assert model.openai_api_base == "http://127.0.0.1:9999/v1"
    assert model.max_retries == 0
    assert model.request_timeout == 45
