"""运行配置与本地环境变量加载。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    model_name: str | None = None
    model_api_key: SecretStr | None = None
    model_base_url: str | None = None
    model_timeout_seconds: float = Field(default=45, gt=0, le=300)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """复用同一份已解析配置；修改 .env 后需要重启进程或显式清缓存。"""
    return Settings()
