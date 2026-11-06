"""局部测试隔离：不加载用户 .env、不写真实数据库、不消费模型额度。"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from minideerflow.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_runtime_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    # 1. 在每个测试开始前切断真实配置；显式传入的 Fake 模型仍可正常验证 Agent。
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setenv("RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.sqlite3"))
    monkeypatch.setenv("WORKSPACE_ROOT_PATH", str(tmp_path / "workspaces"))
    get_settings.cache_clear()
    yield
    # 2. 防止 Settings 缓存把临时路径或测试密钥带到下一个测试。
    get_settings.cache_clear()
