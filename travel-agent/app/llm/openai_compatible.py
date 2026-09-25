from __future__ import annotations

from time import perf_counter
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMProtocolError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from app.core.logging import get_logger
from app.domain.models import ChatMessage


class _ResponseMessage(BaseModel):
    role: Literal["assistant"]
    content: str | None = None
    refusal: str | None = None


class _Choice(BaseModel):
    index: int
    message: _ResponseMessage


class _ChatCompletionResponse(BaseModel):
    choices: list[_Choice]


class _RetryableProviderError(Exception):
    def __init__(
        self,
        kind: Literal["timeout", "rate_limit", "service"],
        status_code: int | None = None,
    ) -> None:
        super().__init__(kind)
        self.kind = kind
        self.status_code = status_code


class OpenAICompatibleChatModel:
    """Minimal OpenAI-compatible Chat Completions adapter."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        model: str,
        api_key: str,
        timeout: float,
        max_attempts: int,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        if not api_key.strip():
            raise ValueError("api_key must not be blank")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._client = client
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._logger = get_logger("llm.openai_compatible")

    async def ainvoke(self, messages: list[ChatMessage]) -> ChatMessage:
        started = perf_counter()
        status_code: int | None = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_attempts),
                wait=wait_exponential(multiplier=0.1, max=1.0),
                retry=retry_if_exception_type(_RetryableProviderError),
                reraise=True,
            ):
                with attempt:
                    response = await self._send(messages)
                    status_code = response.status_code
            return self._parse(response)
        except _RetryableProviderError as exc:
            status_code = exc.status_code
            if exc.kind == "timeout":
                raise LLMTimeoutError("LLM provider request timed out") from exc
            if exc.kind == "rate_limit":
                raise LLMRateLimitError("LLM provider rate limit exceeded") from exc
            raise LLMServiceError("LLM provider is unavailable") from exc
        finally:
            self._logger.info(
                "llm_request_complete",
                provider="openai_compatible",
                model=self._model,
                status_code=status_code,
                latency_ms=round((perf_counter() - started) * 1000, 2),
            )

    async def _send(self, messages: list[ChatMessage]) -> httpx.Response:
        payload = {
            "model": self._model,
            "messages": [message.model_dump() for message in messages],
        }
        try:
            response = await self._client.post(
                "chat/completions",
                headers={"authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise _RetryableProviderError("timeout") from exc
        except httpx.TransportError as exc:
            raise _RetryableProviderError("service") from exc

        if response.status_code in {401, 403}:
            raise LLMAuthenticationError("LLM provider rejected the configured credentials")
        if response.status_code == 429:
            raise _RetryableProviderError("rate_limit", response.status_code)
        if response.status_code >= 500:
            raise _RetryableProviderError("service", response.status_code)
        if response.status_code >= 400:
            raise LLMError(
                "LLM provider rejected the request",
                details={"status_code": response.status_code},
            )
        return response

    @staticmethod
    def _parse(response: httpx.Response) -> ChatMessage:
        try:
            completion = _ChatCompletionResponse.model_validate(response.json())
        except (ValueError, ValidationError, TypeError) as exc:
            raise LLMProtocolError("LLM provider returned an invalid response") from exc
        if not completion.choices:
            raise LLMProtocolError("LLM provider returned no choices")
        message = completion.choices[0].message
        content = message.content if message.content is not None else message.refusal
        if content is None:
            raise LLMProtocolError("LLM provider returned no text content")
        return ChatMessage(role="assistant", content=content)
