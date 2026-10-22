from typing import Literal
from datetime import date, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.exceptions import AppError


class ItineraryError(AppError):
    code = "itinerary_invalid"
    status_code = 422


class RevisionConflict(AppError):
    code = "itinerary_conflict"
    status_code = 409


class ItineraryUnavailable(AppError):
    code = "itinerary_unavailable"
    status_code = 503


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StopInput(Input):
    poi_id: str = Field(pattern=r"^[A-Za-z0-9_-]{5,40}$")
    stay_minutes: int = Field(default=60, ge=5, le=480)
    kind: Literal["visit", "meal", "rest"] = "visit"
    day: int = Field(default=1, ge=1, le=7, description="第几天；地点按天、按游览顺序排列")


class CreateItinerary(Input):
    title: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=40)
    people: int = Field(default=1, ge=1, le=20)
    budget_yuan: float | None = Field(default=None, ge=0, le=1000000)
    mode: Literal["walking", "driving"] = "walking"
    start_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    rest_minutes: int = Field(default=20, ge=0, le=180)
    day_count: int = Field(default=1, ge=1, le=7, description="单城市行程天数；多人总预算覆盖所有天")
    start_date: date | None = Field(default=None, description="用户提供的出发日期；未提供则留空，不猜日期")
    preferences: list[str] = Field(default_factory=list, max_length=8, description="用户本次声明的兴趣、节奏、忌口或步行需求")
    stops: list[StopInput] = Field(min_length=1, max_length=28)

    @field_validator("preferences")
    @classmethod
    def bounded_preferences(cls, values):
        if any(not value.strip() or len(value) > 60 for value in values):
            raise ValueError("偏好应为1至60字")
        return list(dict.fromkeys(value.strip() for value in values))

    @field_validator("title", "city")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("请输入有效文字")
        return value.strip()

    @model_validator(mode="after")
    def validate_plan(self):
        ids = [(stop.day, stop.poi_id) for stop in self.stops]
        if len(ids) != len(set(ids)):
            raise ValueError("同一天不能重复添加相同地点")
        days = [stop.day for stop in self.stops]
        if set(days) != set(range(1, self.day_count + 1)) or days != sorted(days):
            raise ValueError("每天至少安排一个地点，按第1天至最后一天排序，不能跳天")
        limit = 6 if self.day_count == 1 else 4
        if any(days.count(day) > limit for day in set(days)):
            raise ValueError("单日行程最多6站；多日行程每天最多4站")
        if self.start_date:
            try:
                self.start_date + timedelta(days=self.day_count - 1)
            except OverflowError as exc:
                raise ValueError("行程日期超出支持范围") from exc
        if self.end_time and (not self.start_time or self.end_time <= self.start_time):
            raise ValueError("每天结束时间须晚于开始时间，不支持跨午夜安排")
        return self


class EditItinerary(Input):
    expected_revision: int = Field(ge=1)
    action: Literal["complete_stop", "remove_stop", "move_stop", "replace_stop", "update_stop", "update_plan", "refresh_routes"]
    stop_id: UUID | None = None
    replacement: StopInput | None = None
    target_index: int | None = Field(default=None, ge=0, le=27, description="整个stops数组的零起始下标；只能移动到同一天")
    stay_minutes: int | None = Field(default=None, ge=5, le=480)
    kind: Literal["visit", "meal", "rest"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)
    budget_yuan: float | None = Field(default=None, ge=0, le=1000000)
    mode: Literal["walking", "driving"] | None = None
    start_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    rest_minutes: int | None = Field(default=None, ge=0, le=180)

    @model_validator(mode="after")
    def action_fields(self):
        required = {
            "complete_stop": {"stop_id"}, "remove_stop": {"stop_id"},
            "move_stop": {"stop_id", "target_index"}, "replace_stop": {"stop_id", "replacement"},
            "update_stop": {"stop_id"}, "update_plan": set(), "refresh_routes": set(),
        }
        allowed = {
            "complete_stop": {"stop_id"}, "remove_stop": {"stop_id"},
            "move_stop": {"stop_id", "target_index"}, "replace_stop": {"stop_id", "replacement"},
            "update_stop": {"stop_id", "stay_minutes", "kind"},
            "update_plan": {"title", "budget_yuan", "mode", "start_time", "end_time", "rest_minutes"},
            "refresh_routes": set(),
        }
        supplied = self.model_fields_set - {"expected_revision", "action"}
        if not required[self.action] <= supplied or supplied - allowed[self.action]:
            raise ValueError("调整参数与操作不匹配")
        if any(getattr(self, key) is None for key in required[self.action]):
            raise ValueError("缺少操作所需参数")
        if self.action in {"update_stop", "update_plan"} and not (supplied - {"stop_id"}):
            raise ValueError("请提供要修改的内容")
        if any(getattr(self, key) is None for key in supplied & {"mode", "title", "kind", "stay_minutes", "rest_minutes"}):
            raise ValueError("该字段不能留空")
        return self
