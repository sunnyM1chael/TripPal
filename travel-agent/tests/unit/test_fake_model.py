import pytest

from app.domain.models import ChatMessage
from app.llm.fake import FakeModel


@pytest.mark.asyncio
async def test_fake_model_is_deterministic() -> None:
    response = await FakeModel().ainvoke([ChatMessage(role="user", content="hello")])
    assert response.role == "assistant"
    assert response.content == "Fake model response: hello"

