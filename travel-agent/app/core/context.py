from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import structlog


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    conversation_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def new_request_context(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RequestContext:
    return RequestContext(
        request_id=request_id or str(uuid4()),
        conversation_id=conversation_id or str(uuid4()),
        user_id=user_id,
        metadata=metadata or {},
    )


def bind_request_context(context: RequestContext) -> Token[RequestContext | None]:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=context.request_id,
        conversation_id=context.conversation_id,
        user_id=context.user_id,
    )
    return _request_context.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    _request_context.reset(token)
    structlog.contextvars.clear_contextvars()


def get_request_context() -> RequestContext:
    context = _request_context.get()
    if context is None:
        context = new_request_context()
        bind_request_context(context)
    return context

