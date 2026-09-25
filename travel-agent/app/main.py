from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.middleware import RequestContextMiddleware
from app.api.models import ErrorResponse
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.context import get_request_context
from app.core.exceptions import AppError
from app.core.lifecycle import create_lifespan
from app.core.logging import configure_logging, get_logger


def create_app(settings: Settings | None = None) -> FastAPI:
    effective_settings = settings or get_settings()
    configure_logging(effective_settings.log_level)
    app = FastAPI(
        title=effective_settings.app_name,
        version="0.1.0",
        lifespan=create_lifespan(effective_settings),
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        context = get_request_context()
        get_logger("exception").warning(
            "application_error",
            error_code=exc.code,
            path=request.url.path,
        )
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            request_id=context.request_id,
            details=exc.details,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    return app


app = create_app()

