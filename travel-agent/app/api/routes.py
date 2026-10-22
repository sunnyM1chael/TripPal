from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.api.dependencies import get_agent_service, get_container
from app.api.models import AgentRunRequest, AgentRunResponse, StatusResponse
from app.container import ApplicationContainer
from app.core.context import get_request_context
from app.domain.models import AgentExecutionRequest
from app.services.agent import AgentService
from app.api.travel_routes import router as travel_router
from app.api.itinerary_routes import router as itinerary_router
from app.api.notification_routes import router as notification_router
from app.api.subscription_routes import router as subscription_router


router = APIRouter()
router.include_router(travel_router)
router.include_router(itinerary_router)
router.include_router(notification_router)
router.include_router(subscription_router)


@router.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(url="/assistant")


@router.get("/assistant", include_in_schema=False)
async def assistant_page():
    return FileResponse(Path(__file__).parent.parent / "static" / "assistant.html")


@router.get("/health", response_model=StatusResponse, tags=["platform"])
async def health(container: ApplicationContainer = Depends(get_container)) -> StatusResponse:
    return StatusResponse(status="ok", service=container.settings.app_name)


@router.get("/ready", response_model=StatusResponse, tags=["platform"])
async def ready(container: ApplicationContainer = Depends(get_container)) -> StatusResponse:
    status = "ready" if container.initialized else "not_ready"
    return StatusResponse(status=status, service=container.settings.app_name)


@router.post("/api/v1/agent/run", response_model=AgentRunResponse, tags=["agent"])
async def run_agent(
    payload: AgentRunRequest,
    request: Request,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    context = get_request_context()
    execution = AgentExecutionRequest(
        prompt=payload.prompt,
        request_id=context.request_id,
        conversation_id=payload.conversation_id or context.conversation_id,
        user_id=payload.user_id or context.user_id,
        metadata=payload.metadata,
    )
    result = await service.run(execution)
    return AgentRunResponse.model_validate(result.model_dump())

