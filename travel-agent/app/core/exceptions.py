from typing import Any


class AppError(Exception):
    code = "app_error"
    status_code = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    code = "configuration_error"


class AgentError(AppError):
    code = "agent_error"


class LLMError(AppError):
    code = "llm_error"


class LLMTimeoutError(LLMError):
    code = "llm_timeout"
    status_code = 504


class LLMAuthenticationError(LLMError):
    code = "llm_authentication_error"
    status_code = 502


class LLMRateLimitError(LLMError):
    code = "llm_rate_limit_error"
    status_code = 503


class LLMServiceError(LLMError):
    code = "llm_service_error"
    status_code = 502


class LLMProtocolError(LLMError):
    code = "llm_protocol_error"
    status_code = 502


class ToolError(AppError):
    code = "tool_error"


class IntegrationError(AppError):
    code = "integration_error"
    status_code = 502


class UpstreamTimeoutError(IntegrationError):
    code = "upstream_timeout"
    status_code = 504


class UpstreamBusinessError(IntegrationError):
    code = "upstream_business_error"


class UpstreamProtocolError(IntegrationError):
    code = "upstream_protocol_error"
