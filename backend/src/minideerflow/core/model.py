"""模型构造工厂，集中处理配置校验。"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from minideerflow.config import Settings


class ModelNotConfigured(Exception):
    """模型未配置异常"""


def build_chat_model(settings: Settings) -> BaseChatModel:
    """根据配置创建一个 ChatOpenAI 模型"""
    # 1. 校验并获取模型名称与 API 密钥
    name = (settings.model_name or "").strip()
    key = settings.model_api_key
    if not name or key is None or not key.get_secret_value().strip():
        raise ModelNotConfigured("model name and API key are required")
    # 2. 创建 ChatOpenAI 模型实例
    return ChatOpenAI(
        model=name,
        api_key=key,
        base_url=settings.model_base_url or None,
        timeout=settings.model_timeout_seconds,
        max_retries=0,
    )
