import asyncio
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import get_container
from app.api.identity import travel_identity
from app.container import ApplicationContainer
from app.core.exceptions import AgentError, AppError, PreferenceClearPendingError
from app.integrations.amap import RouteRequest
from app.memory.models import Preferences
from app.services.travel import HistoryMessage, TravelRequest, TravelResponse, run_travel
from app.tools.travel import TravelTools
from app.skills.catalog import catalog


router = APIRouter(prefix="/api/v1", tags=["travel"])


@router.get("/travel/skills")
async def travel_skills():
    return {"skills": catalog()}


def may_remember(prompt: str) -> bool:
    if re.search(r"不要.{0,8}(?:记|保存)|不必.{0,8}(?:记|保存)|别.{0,5}(?:记|保存)|不保存", prompt):
        return False
    return bool(re.search(r"(?:记住|记一下|保存我的偏好)[：，,\s]*(?:我|以后|人均|预算|喜欢|常用|默认|不吃|出行)", prompt))


async def limited_owner(request: Request, owner: str = Depends(travel_identity)):
    container = get_container(request)
    await asyncio.to_thread(container.memory.check_rate, owner, container.settings.travel_requests_per_minute)
    return owner


@router.post("/travel/chat", response_model=TravelResponse)
async def travel_chat(payload: TravelRequest, request: Request, owner: str = Depends(limited_owner),
                      container: ApplicationContainer = Depends(get_container)):
    remember_allowed = may_remember(payload.prompt)
    tools = TravelTools(container.hmdp_client, request.headers.get("authorization"), maps=container.maps,
                        memory=container.memory, preferences=container.preferences, owner=owner, remember_allowed=remember_allowed)
    if container.settings.llm_provider.lower() == "fake":
        return await run_travel(container.llm, tools, payload, fake=True)
    conversation_id, lease = await asyncio.to_thread(container.memory.begin, owner,
        str(payload.conversation_id) if payload.conversation_id else None, payload.prompt)
    try:
        conversation = await asyncio.to_thread(container.memory.conversation, owner, conversation_id)
        history = await asyncio.to_thread(container.memory.history, owner, conversation_id)
        preferences = await container.preferences.get(owner, request.headers.get("authorization"))
        recall = await asyncio.to_thread(container.memory.recall, owner, payload.prompt, conversation_id)
        latest = conversation["turns"][-1:]
        observations = latest[0]["tools"] if latest else []
        # The server owns history. Client-provided history cannot replace persisted turns.
        execution = payload.model_copy(update={"history": [HistoryMessage.model_validate(message) for message in history]})
        memory_context = {"preferences": preferences, "task_summary": conversation.get("summary", []), "past_conversations": recall,
                          "last_tool_observations": json_bounded(observations),
                          "notice": "历史商户价格与路线可能过期，需要重新查证；当前要求优先于长期偏好。"}
        result = await run_travel(container.llm, tools, execution, memory_context=memory_context)
        result.conversation_id = conversation_id
        await asyncio.to_thread(container.memory.finish, owner, conversation_id, lease, payload.prompt, result)
        return result
    except TimeoutError as exc:
        error = AgentError("旅行查询超时，请缩小查询范围后重试。")
        error.status_code = 504
        raise error from exc
    finally:
        await asyncio.shield(asyncio.to_thread(container.memory.release, owner, conversation_id, lease))


def json_bounded(observations):
    import json
    text = json.dumps(observations, ensure_ascii=False)
    # Clipped text is explicitly data, never parsed as instructions or trusted current evidence.
    return text[:12000]


@router.get("/travel/state")
async def state(request: Request, owner: str = Depends(travel_identity), container: ApplicationContainer = Depends(get_container)):
    return {"preferences": await container.preferences.get(owner, request.headers.get("authorization")),
            "conversations": await asyncio.to_thread(container.memory.list_conversations, owner),
            "guest": owner.startswith("guest:"), "preferences_editable": owner.startswith("user:"), "maps_configured": container.maps.configured,
            "retention_days": container.settings.memory_retention_days}


@router.get("/travel/conversations/{conversation_id}")
async def conversation(conversation_id: UUID, owner: str = Depends(travel_identity), container: ApplicationContainer = Depends(get_container)):
    return await asyncio.to_thread(container.memory.conversation, owner, str(conversation_id))


@router.delete("/travel/conversations/{conversation_id}")
async def delete_conversation(conversation_id: UUID, owner: str = Depends(travel_identity), container: ApplicationContainer = Depends(get_container)):
    await asyncio.to_thread(container.memory.delete_conversation, owner, str(conversation_id))
    return {"deleted": True}


@router.put("/travel/preferences")
async def preferences(payload: Preferences, request: Request, owner: str = Depends(travel_identity), container: ApplicationContainer = Depends(get_container)):
    return {"preferences": await container.preferences.update(owner, request.headers.get("authorization"), payload.model_dump(exclude_unset=True))}


@router.delete("/travel/memory")
async def forget(request: Request, owner: str = Depends(travel_identity), container: ApplicationContainer = Depends(get_container)):
    await asyncio.to_thread(container.memory.forget, owner)
    try:
        await container.preferences.clear(owner, request.headers.get("authorization"))
    except AppError as exc:
        raise PreferenceClearPendingError("聊天历史已清除，长期偏好清除尚未确认，请重试。") from exc
    return {"deleted": True}


@router.get("/maps/status")
async def maps_status(container: ApplicationContainer = Depends(get_container)):
    return {"configured": container.maps.configured, "provider": "amap"}


@router.get("/maps/cities")
async def cities(keyword: str = Query(min_length=1, max_length=40), owner: str = Depends(limited_owner),
                 container: ApplicationContainer = Depends(get_container)):
    return await container.maps.cities(keyword)


@router.get("/maps/places")
async def places(city: str = Query(min_length=1, max_length=40), keyword: str = Query(min_length=1, max_length=100),
                 page: int = Query(default=1, ge=1, le=20), owner: str = Depends(limited_owner),
                 container: ApplicationContainer = Depends(get_container)):
    return await container.maps.search(city, keyword, page)


@router.get("/maps/places/{poi_id}")
async def place_detail(poi_id: str, owner: str = Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,40}", poi_id):
        from fastapi import HTTPException
        raise HTTPException(422, "无效地点ID")
    return await container.maps.detail(poi_id)


@router.post("/maps/route")
async def route(payload: RouteRequest, owner: str = Depends(limited_owner), container: ApplicationContainer = Depends(get_container)):
    return await container.maps.route(payload)


@router.get("/maps/preview")
async def preview(origin: str = Query(max_length=50), destination: str = Query(max_length=50),
                  path: str = Query(default="", max_length=2500), owner: str = Depends(limited_owner),
                  container: ApplicationContainer = Depends(get_container)):
    data = await container.maps.preview(origin, destination, path)
    return Response(content=data, media_type="image/png" if data.startswith(b"\x89PNG") else "image/jpeg",
                    headers={"Cache-Control": "private, max-age=120"})
