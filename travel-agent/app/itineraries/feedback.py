"""Private, user-authored visit records; no model inference or public writes."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.itineraries.models import Input, ItineraryError, RevisionConflict


class VisitFeedback(Input):
    expected_revision: int = Field(ge=1)
    rating: int = Field(ge=1, le=5, strict=True)
    actual_cost_yuan: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=2)
    cost_scope: Literal["person", "party"] = "person"
    queue_minutes: int | None = Field(default=None, ge=0, le=1440, strict=True)
    experience: str = Field(min_length=1, max_length=1500)
    would_return: bool | None = None
    draft_title: str | None = Field(default=None, min_length=1, max_length=100)
    draft_content: str | None = Field(default=None, min_length=1, max_length=2500)

    @field_validator("experience", "draft_title", "draft_content")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("请输入有效文字")
        return value.strip() if value is not None else None


def make_draft(stop, feedback):
    """Only restate user claims; never substitute estimated itinerary costs."""
    lines = [feedback.experience, f"我的评分：{feedback.rating}/5"]
    if feedback.actual_cost_yuan is not None:
        scope = "人均" if feedback.cost_scope == "person" else "本次同行人合计"
        lines.append(f"实际花费（{scope}）：¥{feedback.actual_cost_yuan:.2f}")
    if feedback.queue_minutes is not None:
        lines.append(f"排队：{feedback.queue_minutes}分钟")
    if feedback.would_return is not None:
        lines.append("还想再去。" if feedback.would_return else "暂时不考虑再去。")
    return {"title": feedback.draft_title or f"{stop['place']['name']} · 我的体验"[:100],
            "content": feedback.draft_content or "\n\n".join(lines), "status": "private_draft"}


async def save_feedback(store, owner, itinerary_id, stop_id: UUID, feedback: VisitFeedback):
    plan = await asyncio.to_thread(store.get, owner, itinerary_id)
    if plan["revision"] != feedback.expected_revision:
        raise RevisionConflict("行程已更新，请刷新后再保存反馈。")
    plan = deepcopy(plan)
    stop = next((s for s in plan["stops"] if s["id"] == str(stop_id)), None)
    if stop is None or not stop["completed"]:
        raise ItineraryError("请先将此站标记为已完成，再记录实际体验。")
    now = datetime.now(timezone.utc).isoformat()
    stop["feedback"] = {**feedback.model_dump(mode="json", exclude={"expected_revision", "draft_title", "draft_content"}),
                        "source": "user_reported", "updated_at": now,
                        "draft": make_draft(stop, feedback)}
    plan["changes"] = [*plan.get("changes", []), {"action": "visit_feedback", "stop_id": str(stop_id), "at": now}][-30:]
    for key in ("id", "revision", "created_at", "updated_at"):
        plan.pop(key, None)
    return await asyncio.to_thread(store.update, owner, itinerary_id, feedback.expected_revision, plan)
