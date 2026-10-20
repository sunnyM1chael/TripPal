from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class AgentExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    request_id: str
    conversation_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionResult(BaseModel):
    request_id: str
    conversation_id: str
    output: str
    messages: list[ChatMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)

