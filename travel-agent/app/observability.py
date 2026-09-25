from time import perf_counter
from typing import Any, Protocol

from app.core.logging import get_logger


class Instrumentation(Protocol):
    def event(self, name: str, **attributes: Any) -> None: ...


class StructuredLogInstrumentation:
    """Vendor-neutral instrumentation boundary backed by structured logs."""

    def __init__(self) -> None:
        self._logger = get_logger("observability")

    def event(self, name: str, **attributes: Any) -> None:
        self._logger.info(name, **attributes)


class Timer:
    def __init__(self) -> None:
        self._started = perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return round((perf_counter() - self._started) * 1000, 2)

