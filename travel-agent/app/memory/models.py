from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    default_city: str | None = Field(default=None, max_length=40)
    budget_per_person: float | None = Field(default=None, ge=0, le=100000)
    cuisines: list[str] = Field(default_factory=list, max_length=12)
    dietary_notes: list[str] = Field(default_factory=list, max_length=12)
    transport: Literal["driving", "walking"] | None = None

    @field_validator("cuisines", "dietary_notes")
    @classmethod
    def valid_items(cls, items):
        if any(not item.strip() or len(item) > 60 for item in items):
            raise ValueError("偏好条目须为1到60个字符")
        return list(dict.fromkeys(item.strip() for item in items))
