from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.context import bind_request_context, new_request_context, reset_request_context
from app.core.logging import get_logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        context = new_request_context(
            request_id=request.headers.get("x-request-id"),
            conversation_id=request.headers.get("x-conversation-id"),
            user_id=request.headers.get("x-user-id"),
            metadata={"method": request.method, "path": request.url.path},
        )
        token = bind_request_context(context)
        logger = get_logger("http")
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = context.request_id
            response.headers["x-conversation-id"] = context.conversation_id
            logger.info(
                "request_complete",
                status_code=response.status_code,
                method=request.method,
                path=request.url.path,
                latency_ms=round((perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            reset_request_context(token)

