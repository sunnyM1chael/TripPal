import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "local"
    assert settings.port == 8000
    assert settings.llm_provider == "fake"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "platform-test")
    monkeypatch.setenv("PORT", "9001")
    settings = Settings(_env_file=None)
    assert settings.app_name == "platform-test"
    assert settings.port == 9001


def test_settings_reject_invalid_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(hmdp_timeout=0, _env_file=None)


@pytest.mark.parametrize("missing", ["base_url", "api_key"])
def test_openai_compatible_settings_require_credentials(missing: str) -> None:
    values = {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://llm.example/v1",
        "llm_api_key": "test-key",
    }
    values[f"llm_{missing}"] = None
    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


def test_openai_compatible_settings_are_valid() -> None:
    settings = Settings(
        llm_provider="openai-compatible",
        llm_model="model-1",
        llm_base_url="https://llm.example/v1",
        llm_api_key="test-key",
        llm_timeout=10,
        llm_max_attempts=2,
        _env_file=None,
    )
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "test-key"
    assert settings.llm_max_attempts == 2
