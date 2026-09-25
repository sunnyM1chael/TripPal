from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import ChatMessage


class StatusResponse(BaseModel):
    status: str
    service: str


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    conversation_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    request_id: str
    conversation_id: str
    output: str
    messages: list[ChatMessage]
    metadata: dict[str, Any]


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

