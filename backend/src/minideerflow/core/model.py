"""ChatOpenAI 模型构造工厂，集中处理配置校验。"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from minideerflow.config import Settings


class ModelNotConfigured(Exception):
    """请求模型时缺少名称或密钥；不影响基础服务启动。"""


def build_chat_model(settings: Settings) -> BaseChatModel:
    """在实际 Agent 请求到达时创建模型，避免健康检查依赖外部服务。"""
    # 1. 校验模型名称与保密字段；配置不完整时不尝试访问 Provider。
    name = (settings.model_name or "").strip()
    key = settings.model_api_key
    if not name or key is None or not key.get_secret_value().strip():
        raise ModelNotConfigured("model name and API key are required")
    # 2. 统一设置模型端点、超时和重试次数，避免多个入口各自构造客户端。
    return ChatOpenAI(
        model=name,
        api_key=key,
        base_url=settings.model_base_url or None,
        timeout=settings.model_timeout_seconds,
        max_retries=0,
    )
