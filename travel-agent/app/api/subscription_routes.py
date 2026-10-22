from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import get_container
from app.api.travel_routes import limited_owner
from app.container import ApplicationContainer
from app.services.voucher_subscription import ConfirmSubscription, PrepareSubscription, SubscriptionRequest


router = APIRouter(prefix="/api/v1/voucher-subscriptions", tags=["voucher subscriptions"])


@router.get("/status")
async def status(request: Request, shop_id: int = Query(gt=0, le=9223372036854775807),
                 voucher_id: int = Query(gt=0, le=9223372036854775807), owner=Depends(limited_owner),
                 container: ApplicationContainer = Depends(get_container)):
    return await container.subscriptions.status(owner, request.headers.get("authorization"),
        SubscriptionRequest(shop_id=shop_id, voucher_id=voucher_id))


@router.post("/prepare")
async def prepare(payload: PrepareSubscription, request: Request, owner=Depends(limited_owner),
                  container: ApplicationContainer = Depends(get_container)):
    return await container.subscriptions.prepare(owner, request.headers.get("authorization"), payload)


@router.post("/{action_id}/confirm")
async def confirm(action_id: UUID, payload: ConfirmSubscription, request: Request, owner=Depends(limited_owner),
                  container: ApplicationContainer = Depends(get_container)):
    # No tool grants a model access to this endpoint; confirmation comes from the UI.
    return await container.subscriptions.confirm(owner, request.headers.get("authorization"), str(action_id), payload)
