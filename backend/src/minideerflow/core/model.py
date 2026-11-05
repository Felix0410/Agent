from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from minideerflow.config import Settings


class ModelNotConfigured(Exception):
    pass


def build_chat_model(settings: Settings) -> BaseChatModel:
    name = (settings.model_name or "").strip()
    key = settings.model_api_key
    if not name or key is None or not key.get_secret_value().strip():
        raise ModelNotConfigured("model name and API key are required")
    return ChatOpenAI(
        model=name,
        api_key=key,
        base_url=settings.model_base_url or None,
        timeout=settings.model_timeout_seconds,
        max_retries=0,
    )
