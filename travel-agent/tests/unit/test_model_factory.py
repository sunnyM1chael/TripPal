import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.llm.factory import create_chat_model
from app.llm.fake import FakeModel
from app.llm.openai_compatible import OpenAICompatibleChatModel


def test_factory_builds_fake_model_without_client() -> None:
    assert isinstance(create_chat_model(Settings(_env_file=None)), FakeModel)


@pytest.mark.asyncio
async def test_factory_builds_openai_compatible_model() -> None:
    settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="https://llm.example/v1",
        llm_api_key="test-key",
        _env_file=None,
    )
    client = httpx.AsyncClient(base_url="https://llm.example/v1/")
    try:
        assert isinstance(create_chat_model(settings, client), OpenAICompatibleChatModel)
    finally:
        await client.aclose()


def test_factory_rejects_unknown_provider() -> None:
    settings = Settings(llm_provider="unknown", _env_file=None)
    with pytest.raises(ConfigurationError, match="not supported"):
        create_chat_model(settings)
