from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class HmdpResponse(BaseModel, Generic[T]):
    """Integration-only representation of Java Result<T>."""

    success: bool
    errorMsg: str | None = None
    data: T | None = None
    total: int | None = None


class AuthContext(BaseModel):
    """Opaque downstream identity; its value is forwarded verbatim."""

    authorization_value: str | None = None

