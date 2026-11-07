"""运行配置与本地环境变量加载。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：基础服务可独立启动，模型字段仅在调用 Agent 时校验。"""

    # 从仓库根目录加载本地 .env，避免 PyCharm 与终端工作目录不同导致读取失败。
    # 真实环境变量优先于 .env；密钥字段使用 SecretStr，禁止日志输出明文。
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    mcp_config_path: Path | None = None
    model_name: str | None = None
    model_api_key: SecretStr | None = None
    model_base_url: str | None = None
    model_timeout_seconds: float = Field(default=45, gt=0, le=300)
    # 默认数据目录固定在 backend 下，避免 PyCharm 与终端从不同 cwd 创建多份库。
    runtime_db_path: Path = Path(__file__).resolve().parents[2] / "data/runtime.sqlite3"
    checkpoint_db_path: Path = Path(__file__).resolve().parents[2] / "data/checkpoints.sqlite3"
    workspace_root_path: Path = Path(__file__).resolve().parents[2] / "data/workspaces"
    run_max_concurrency: int = Field(default=2, ge=1, le=2)
    run_queue_size: int = Field(default=8, ge=1, le=8)
    # P04 父持久 Run 与 P01 单轮时限分离；上限与前端180秒轮询保持一致。
    run_timeout_seconds: float = Field(default=600, gt=0, le=600)
    run_max_model_calls: int = Field(default=40, ge=1, le=40)
    run_max_tool_calls: int = Field(default=30, ge=1, le=30)
    run_max_input_tokens_estimate: int = Field(default=120000, ge=1, le=120000)
    subagent_timeout_seconds: float = Field(default=35, gt=0, le=35)
    subagent_recursion_limit: int = Field(default=14, ge=2, le=14)
    max_subagent_concurrency: int = Field(default=3, ge=1, le=3)
    max_subagent_calls_per_run: int = Field(default=4, ge=1, le=4)

    @field_validator("mcp_config_path", mode="before")
    @classmethod
    def mcp_path(cls, value):
        """空配置不连接；相对路径以backend为准，不依赖IDE工作目录。"""
        if value is None or value == "":
            return None
        path = Path(value).expanduser()
        return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path

    @field_validator("runtime_db_path", "checkpoint_db_path", mode="before")
    @classmethod
    def resolve_database_path(cls, value: str | Path) -> Path:
        """相对配置也以 backend 为基准，保持从 PyCharm/终端启动的一致性。"""
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path.resolve()

    @model_validator(mode="after")
    def separate_database_files(self) -> "Settings":
        """业务库与 Graph 库必须分开，不能误认为两者有原子事务。"""
        if self.runtime_db_path == self.checkpoint_db_path:
            raise ValueError("runtime and checkpoint databases must use separate files")
        if any(
            path == self.workspace_root_path or path.is_relative_to(self.workspace_root_path)
            for path in (self.runtime_db_path, self.checkpoint_db_path)
        ):
            raise ValueError("workspace must not contain runtime databases")
        return self

    @field_validator("workspace_root_path", mode="before")
    @classmethod
    def workspace_path(cls, value: str | Path) -> Path:
        """不 resolve 工作区 symlink，交给存储层逐级无跟随校验。"""
        import os

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return Path(os.path.abspath(path))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """复用同一份已解析配置；修改 .env 后需要重启进程或显式清缓存。"""
    return Settings()
