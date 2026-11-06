from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from minideerflow.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setitem(Settings.model_config, "env_file", tmp_path / ".env")
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


def test_dotenv_loaded_from_other_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "APP_ENV=test\nLOG_LEVEL=DEBUG\nMODEL_NAME=test-model\n"
        "MODEL_API_KEY=dotenv-test-secret\nMODEL_BASE_URL=http://127.0.0.1:9999/v1\n"
        "UNRELATED_SETTING=ignored\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.model_name == "test-model"
    assert settings.model_api_key.get_secret_value() == "dotenv-test-secret"
    assert settings.model_base_url == "http://127.0.0.1:9999/v1"
    assert "dotenv-test-secret" not in settings.model_dump_json()


def test_environment_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    assert get_settings().log_level == "WARNING"


def test_invalid_dotenv_rejected(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("LOG_LEVEL=INVALID\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        get_settings()


def test_runtime_defaults_are_backend_absolute_paths(monkeypatch, tmp_path: Path) -> None:
    for name in ["RUNTIME_DB_PATH", "CHECKPOINT_DB_PATH"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    settings = get_settings()
    backend = Path(__file__).resolve().parents[1]
    assert settings.runtime_db_path == backend / "data/runtime.sqlite3"
    assert settings.checkpoint_db_path == backend / "data/checkpoints.sqlite3"
    assert settings.run_max_concurrency == 2
    assert settings.run_queue_size == 8


def test_relative_database_config_is_based_on_backend(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_DB_PATH", "data/alternate.sqlite3")
    assert (
        get_settings().runtime_db_path
        == Path(__file__).resolve().parents[1] / "data/alternate.sqlite3"
    )


def test_business_and_checkpoint_paths_cannot_collide(monkeypatch, tmp_path: Path) -> None:
    path = str(tmp_path / "same.sqlite3")
    monkeypatch.setenv("RUNTIME_DB_PATH", path)
    monkeypatch.setenv("CHECKPOINT_DB_PATH", path)
    with pytest.raises(ValidationError):
        get_settings()


@pytest.mark.parametrize(
    ("field", "value"), [("RUN_MAX_CONCURRENCY", "3"), ("RUN_QUEUE_SIZE", "9")]
)
def test_runtime_capacity_bounds(monkeypatch, field: str, value: str) -> None:
    monkeypatch.setenv(field, value)
    with pytest.raises(ValidationError):
        get_settings()
