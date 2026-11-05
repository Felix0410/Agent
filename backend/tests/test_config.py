from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from minideerflow.config import get_settings


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
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
