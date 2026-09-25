from collections.abc import Callable
from typing import TypeVar

from app.integrations.hmdp.models import HmdpResponse


IntegrationT = TypeVar("IntegrationT")
DomainT = TypeVar("DomainT")


def adapt_data(response: HmdpResponse[IntegrationT], adapter: Callable[[IntegrationT], DomainT]) -> DomainT | None:
    """Explicit boundary for translating integration DTOs into domain models."""

    if response.data is None:
        return None
    return adapter(response.data)

