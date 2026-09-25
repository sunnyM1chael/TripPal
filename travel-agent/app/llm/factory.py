import httpx

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.llm.base import ChatModel
from app.llm.fake import FakeModel
from app.llm.openai_compatible import OpenAICompatibleChatModel


def create_chat_model(settings: Settings, client: httpx.AsyncClient | None = None) -> ChatModel:
    provider = settings.llm_provider.lower().replace("-", "_")
    if provider == "fake":
        return FakeModel()
    if provider in {"openai", "openai_compatible"}:
        if client is None:
            raise ConfigurationError("OpenAI-compatible provider requires a managed HTTP client")
        if settings.llm_api_key is None:
            raise ConfigurationError("OpenAI-compatible provider requires LLM_API_KEY")
        return OpenAICompatibleChatModel(
            client,
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.llm_timeout,
            max_attempts=settings.llm_max_attempts,
        )
    raise ConfigurationError(
        f"LLM provider '{settings.llm_provider}' is not supported"
    )
