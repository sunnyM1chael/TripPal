from typing import Protocol

from app.domain.models import ChatMessage


class ChatModel(Protocol):
    async def ainvoke(self, messages: list[ChatMessage]) -> ChatMessage: ...

