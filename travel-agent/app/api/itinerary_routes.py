import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_container
from app.api.travel_routes import limited_owner
from app.container import ApplicationContainer
from app.core.exceptions import AppError
from app.itineraries.models import CreateItinerary, EditItinerary
from app.itineraries.feedback import VisitFeedback, save_feedback


router = APIRouter(prefix="/api/v1/itineraries", tags=["itineraries"])


@router.get("")
async def list_itineraries(owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return {"itineraries": await asyncio.to_thread(container.itineraries.store.list, owner)}


@router.get("/{itinerary_id}")
async def get_itinerary(itinerary_id: UUID, owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return await asyncio.to_thread(container.itineraries.store.get, owner, str(itinerary_id))


async def bounded(operation):
    try:
        return await operation
    except TimeoutError as exc:
        error = AppError("行程查询超时，请减少地点后重试。")
        error.code, error.status_code = "itinerary_timeout", 504
        raise error from exc


@router.post("", status_code=201)
async def create_itinerary(payload: CreateItinerary, owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return await bounded(container.itineraries.create(owner, payload))


@router.patch("/{itinerary_id}")
async def edit_itinerary(itinerary_id: UUID, payload: EditItinerary, owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return await bounded(container.itineraries.edit(owner, str(itinerary_id), payload))


@router.delete("/{itinerary_id}")
async def delete_itinerary(itinerary_id: UUID, expected_revision: int = Query(ge=1), owner=Depends(limited_owner),
                           container: ApplicationContainer = Depends(get_container)):
    await asyncio.to_thread(container.itineraries.store.delete, owner, str(itinerary_id), expected_revision)
    return {"deleted": True}


@router.put("/{itinerary_id}/stops/{stop_id}/feedback")
async def visit_feedback(itinerary_id: UUID, stop_id: UUID, payload: VisitFeedback,
                         owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return await save_feedback(container.itineraries.store, owner, str(itinerary_id), stop_id, payload)
