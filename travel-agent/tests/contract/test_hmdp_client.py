from typing import Callable

import httpx
import pytest
from pydantic import BaseModel

from app.core.exceptions import (
    IntegrationError,
    UpstreamBusinessError,
    UpstreamProtocolError,
    UpstreamTimeoutError,
)
from app.integrations.hmdp.client import HmdpClient
from app.integrations.hmdp.models import AuthContext


class SampleData(BaseModel):
    identifier: int
    name: str


def make_client(handler: Callable[[httpx.Request], httpx.Response], attempts: int = 1) -> tuple[HmdpClient, httpx.AsyncClient]:
    async_client = httpx.AsyncClient(
        base_url="http://hmdp.test",
        transport=httpx.MockTransport(handler),
    )
    return HmdpClient(async_client, timeout=0.1, max_attempts=attempts), async_client


@pytest.mark.asyncio
async def test_http_success_and_business_success() -> None:
    client, raw = make_client(
        lambda request: httpx.Response(
            200,
            json={"success": True, "errorMsg": None, "data": {"identifier": 7, "name": "shop"}, "total": 1},
        )
    )
    try:
        result = await client.request_data("GET", "/shop/7", SampleData)
    finally:
        await raw.aclose()
    assert result == SampleData(identifier=7, name="shop")


@pytest.mark.asyncio
async def test_http_success_and_business_failure() -> None:
    client, raw = make_client(lambda request: httpx.Response(200, json={"success": False, "errorMsg": "not found"}))
    try:
        with pytest.raises(UpstreamBusinessError, match="not found"):
            await client.request_data("GET", "/shop/7", SampleData)
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_timeout_is_mapped() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, raw = make_client(timeout)
    try:
        with pytest.raises(UpstreamTimeoutError):
            await client.request_data("GET", "/slow", SampleData)
    finally:
        await raw.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_http_error_is_mapped(status: int) -> None:
    client, raw = make_client(lambda request: httpx.Response(status, text="failure"))
    try:
        with pytest.raises(IntegrationError):
            await client.request_data("GET", "/failure", SampleData)
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_connection_error_is_mapped() -> None:
    def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client, raw = make_client(disconnected)
    try:
        with pytest.raises(IntegrationError):
            await client.request_data("GET", "/failure", SampleData)
    finally:
        await raw.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"data": {"identifier": 1, "name": "x"}}),
        httpx.Response(200, json={"success": True, "data": {"identifier": "bad", "name": "x"}}),
    ],
)
async def test_malformed_response_is_protocol_error(response: httpx.Response) -> None:
    client, raw = make_client(lambda request: response)
    try:
        with pytest.raises(UpstreamProtocolError):
            await client.request_data("GET", "/malformed", SampleData)
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_authorization_is_forwarded_verbatim() -> None:
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json={"success": True, "data": None})

    client, raw = make_client(handler)
    try:
        await client.request_data(
            "GET",
            "/me",
            SampleData,
            auth=AuthContext(authorization_value="opaque-token-without-bearer"),
        )
    finally:
        await raw.aclose()
    assert observed["authorization"] == "opaque-token-without-bearer"


@pytest.mark.asyncio
async def test_idempotent_retry_is_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("refused", request=request)

    client, raw = make_client(handler, attempts=2)
    try:
        with pytest.raises(IntegrationError):
            await client.request_data("GET", "/failure", SampleData)
    finally:
        await raw.aclose()
    assert calls == 2
