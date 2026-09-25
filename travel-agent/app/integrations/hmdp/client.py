from __future__ import annotations

from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.exceptions import (
    IntegrationError,
    UpstreamBusinessError,
    UpstreamProtocolError,
    UpstreamTimeoutError,
)
from app.core.logging import get_logger
from app.integrations.hmdp.models import AuthContext, HmdpResponse


T = TypeVar("T")


class _RetryableTransportError(Exception):
    pass


class _RetryableTimeout(_RetryableTransportError):
    pass


class HmdpClient:
    """Async HMDP transport. Java response details terminate at this boundary."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout: float,
        max_attempts: int = 2,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._client = client
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._logger = get_logger("integration.hmdp")

    async def request_data(
        self,
        method: str,
        path: str,
        response_type: type[T],
        *,
        auth: AuthContext | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        retry: bool | None = None,
    ) -> T | None:
        method = method.upper()
        should_retry = method in {"GET", "HEAD", "OPTIONS"} if retry is None else retry
        attempts = self._max_attempts if should_retry else 1
        started = perf_counter()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(multiplier=0.05, max=0.2),
                retry=retry_if_exception_type(_RetryableTransportError),
                reraise=True,
            ):
                with attempt:
                    response = await self._send(method, path, auth=auth, params=params, json=json)
            return self._parse(response, response_type)
        except _RetryableTimeout as exc:
            raise UpstreamTimeoutError("HMDP request timed out") from exc
        except _RetryableTransportError as exc:
            raise IntegrationError("HMDP connection failed") from exc
        finally:
            self._logger.info(
                "integration_request_complete",
                method=method,
                path=path,
                latency_ms=round((perf_counter() - started) * 1000, 2),
            )

    async def _send(
        self,
        method: str,
        path: str,
        *,
        auth: AuthContext | None,
        params: dict[str, Any] | None,
        json: Any,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if auth and auth.authorization_value is not None:
            headers["authorization"] = auth.authorization_value
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise _RetryableTimeout() from exc
        except httpx.TransportError as exc:
            raise _RetryableTransportError() from exc

        if response.status_code >= 500:
            raise _RetryableTransportError(f"upstream HTTP {response.status_code}")
        if response.status_code >= 400:
            raise IntegrationError(
                f"HMDP returned HTTP {response.status_code}",
                details={"status_code": response.status_code},
            )
        return response

    @staticmethod
    def _parse(response: httpx.Response, response_type: type[T]) -> T | None:
        try:
            payload = response.json()
            envelope = TypeAdapter(HmdpResponse[response_type]).validate_python(payload)
        except (ValueError, ValidationError, TypeError) as exc:
            raise UpstreamProtocolError("HMDP returned an invalid response envelope") from exc
        if not envelope.success:
            raise UpstreamBusinessError(envelope.errorMsg or "HMDP business operation failed")
        return envelope.data
