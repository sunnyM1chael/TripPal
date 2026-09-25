from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class ToolDefinition(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    handler: ToolHandler

    model_config = {"arbitrary_types_allowed": True}


class ToolResult(BaseModel):
    tool_name: str
    output: Any
    latency_ms: float

