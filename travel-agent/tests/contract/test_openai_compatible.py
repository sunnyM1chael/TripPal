import json
from collections.abc import Callable

import httpx
import pytest

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from app.domain.models import ChatMessage
from app.graph.workflow import build_graph
from app.llm.openai_compatible import OpenAICompatibleChatModel


def make_model(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    attempts: int = 1,
) -> tuple[OpenAICompatibleChatModel, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
    )
    model = OpenAICompatibleChatModel(
        client,
        model="model-1",
        api_key="secret-test-key",
        timeout=0.1,
        max_attempts=attempts,
    )
    return model, client


def successful_response(content: str = "hello") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "completion-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content, "refusal": None},
                    "finish_reason": "stop",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_success_uses_expected_contract_and_auth() -> None:
    observed: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["authorization"] = request.headers["authorization"]
        observed["body"] = json.loads(request.content)
        return successful_response("provider response")

    model, client = make_model(handler)
    try:
        result = await model.ainvoke(
            [
                ChatMessage(role="system", content="system instruction"),
                ChatMessage(role="user", content="hello"),
            ]
        )
    finally:
        await client.aclose()

    assert result == ChatMessage(role="assistant", content="provider response")
    assert observed == {
        "path": "/v1/chat/completions",
        "authorization": "Bearer secret-test-key",
        "body": {
            "model": "model-1",
            "messages": [
                {"role": "system", "content": "system instruction"},
                {"role": "user", "content": "hello"},
            ],
        },
    }


@pytest.mark.asyncio
async def test_logs_exclude_prompt_key_and_response(capsys: pytest.CaptureFixture[str]) -> None:
    model, client = make_model(lambda request: successful_response("private-response"))
    try:
        await model.ainvoke([ChatMessage(role="user", content="private-prompt")])
    finally:
        await client.aclose()
    logs = capsys.readouterr().out
    assert "secret-test-key" not in logs
    assert "private-prompt" not in logs
    assert "private-response" not in logs


@pytest.mark.asyncio
async def test_provider_executes_inside_compiled_graph() -> None:
    model, client = make_model(lambda request: successful_response("graph response"))
    try:
        graph = build_graph(model)
        result = await graph.ainvoke(
            {
                "request_id": "req-real-provider",
                "conversation_id": "conv-real-provider",
                "user_id": None,
                "messages": [ChatMessage(role="user", content="graph request")],
                "context": {},
                "tool_results": [],
                "metadata": {},
                "errors": [],
            }
        )
    finally:
        await client.aclose()
    assert result["messages"][-1] == ChatMessage(role="assistant", content="graph response")


@pytest.mark.asyncio
async def test_refusal_is_returned_as_assistant_content() -> None:
    response = httpx.Response(
        200,
        json={"choices": [{"index": 0, "message": {"role": "assistant", "content": None, "refusal": "declined"}}]},
    )
    model, client = make_model(lambda request: response)
    try:
        result = await model.ainvoke([ChatMessage(role="user", content="request")])
    finally:
        await client.aclose()
    assert result.content == "declined"


@pytest.mark.asyncio
async def test_timeout_is_retried_and_mapped() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out", request=request)

    model, client = make_model(handler, attempts=2)
    try:
        with pytest.raises(LLMTimeoutError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
    assert calls == 2


@pytest.mark.asyncio
async def test_connection_failure_is_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    model, client = make_model(handler)
    try:
        with pytest.raises(LLMServiceError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_authentication_error_is_not_retried(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": {"message": "sensitive upstream detail"}})

    model, client = make_model(handler, attempts=3)
    try:
        with pytest.raises(LLMAuthenticationError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
    assert calls == 1


@pytest.mark.asyncio
async def test_rate_limit_retry_is_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    model, client = make_model(handler, attempts=2)
    try:
        with pytest.raises(LLMRateLimitError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
    assert calls == 2


@pytest.mark.asyncio
async def test_server_error_can_recover_on_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="unavailable")
        return successful_response("recovered")

    model, client = make_model(handler, attempts=2)
    try:
        result = await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
    assert calls == 2
    assert result.content == "recovered"


@pytest.mark.asyncio
async def test_persistent_server_error_is_mapped() -> None:
    model, client = make_model(lambda request: httpx.Response(500), attempts=1)
    try:
        with pytest.raises(LLMServiceError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_non_retryable_request_error_is_mapped() -> None:
    model, client = make_model(lambda request: httpx.Response(400, text="invalid"), attempts=3)
    try:
        with pytest.raises(LLMError) as captured:
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
    assert captured.value.details == {"status_code": 400}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"index": 0, "message": {"role": "assistant"}}]}),
        httpx.Response(200, json={"choices": [{"index": 0, "message": {"role": "user", "content": "bad"}}]}),
    ],
)
async def test_malformed_response_is_protocol_error(response: httpx.Response) -> None:
    model, client = make_model(lambda request: response)
    try:
        with pytest.raises(LLMProtocolError):
            await model.ainvoke([ChatMessage(role="user", content="hello")])
    finally:
        await client.aclose()
