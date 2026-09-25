from app.domain.models import ChatMessage


class FakeModel:
    """Deterministic local model for framework validation and tests."""

    async def ainvoke(self, messages: list[ChatMessage]) -> ChatMessage:
        latest = next((message.content for message in reversed(messages) if message.role == "user"), "")
        return ChatMessage(role="assistant", content=f"Fake model response: {latest}")

