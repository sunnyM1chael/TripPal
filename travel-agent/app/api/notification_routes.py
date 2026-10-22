"""Owner-scoped inbox; events are emitted in the itinerary transaction."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_container
from app.api.travel_routes import limited_owner
from app.container import ApplicationContainer
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def inbox(unread_only: bool = False, page: int = Query(default=1, ge=1, le=1000),
                owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    def read():
        store = container.itineraries.store
        store.require_ready()
        with store.memory.connection() as db:
            count = db.execute("SELECT count(*) AS n FROM notifications WHERE owner=? AND is_read=0", (owner,)).fetchone()["n"]
            rows = db.execute("SELECT id,title,body,itinerary_id,is_read,created FROM notifications WHERE owner=?"
                              + (" AND is_read=0" if unread_only else "")
                              + " ORDER BY created DESC,id DESC LIMIT 20 OFFSET ?", (owner, (page - 1) * 20)).fetchall()
        return {"items": [dict(row) for row in rows], "unread_count": count, "page": page}
    return await asyncio.to_thread(read)


@router.post("/read-all")
async def read_all(owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    def mark():
        container.itineraries.store.require_ready()
        with container.memory.connection() as db:
            db.execute("UPDATE notifications SET is_read=1 WHERE owner=? AND is_read=0", (owner,))
    await asyncio.to_thread(mark)
    return {"read": True}


@router.post("/{notification_id}/read")
async def read_one(notification_id: UUID, owner=Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    def mark():
        container.itineraries.store.require_ready()
        with container.memory.connection() as db:
            if not db.execute("SELECT id FROM notifications WHERE id=? AND owner=?", (str(notification_id), owner)).fetchone():
                raise NotFoundError("消息不存在或无权访问。")
            db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND owner=?", (str(notification_id), owner))
    await asyncio.to_thread(mark)
    return {"read": True}
