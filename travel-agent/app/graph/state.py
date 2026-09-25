from typing import Any, TypedDict

from app.domain.models import ChatMessage


class AgentState(TypedDict):
    request_id: str
    conversation_id: str
    user_id: str | None
    messages: list[ChatMessage]
    context: dict[str, Any]
    tool_results: list[dict[str, Any]]
    metadata: dict[str, Any]
    errors: list[str]

