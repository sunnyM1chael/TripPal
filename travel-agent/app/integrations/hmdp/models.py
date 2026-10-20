from typing import Generic, TypeVar

from pydantic import BaseModel, field_validator


T = TypeVar("T")


class HmdpResponse(BaseModel, Generic[T]):
    """Integration-only representation of Java Result<T>."""

    success: bool
    errorMsg: str | None = None
    data: T | None = None
    total: int | None = None

    @field_validator("total", mode="before")
    @classmethod
    def normalize_empty_total(cls, value):
        # Java JsonCustomSerializer serializes a null Long as an empty string.
        return None if value == "" else value


class AuthContext(BaseModel):
    """Opaque downstream identity; its value is forwarded verbatim."""

    authorization_value: str | None = None

