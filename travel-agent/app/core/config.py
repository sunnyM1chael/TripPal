from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated process configuration loaded once at application startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "travel-agent"
    app_env: Literal["local", "test", "production"] = "local"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    hmdp_base_url: HttpUrl = HttpUrl("http://127.0.0.1:8085")
    hmdp_timeout: float = Field(default=5.0, gt=0, le=120)
    memory_db_path: Path = Path("data/travel-memory.sqlite3")
    memory_backend: Literal["sqlite", "mysql"] = "sqlite"
    memory_mysql_host: str = "127.0.0.1"
    memory_mysql_port: int = Field(default=3306, ge=1, le=65535)
    memory_mysql_database: str = Field(default="travel_agent", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    memory_mysql_user: str | None = None
    memory_mysql_password: SecretStr | None = None
    memory_mysql_pool_size: int = Field(default=5, ge=1, le=30)
    memory_mysql_ssl_ca: Path | None = None
    memory_retention_days: int = Field(default=90, ge=1, le=3650)
    travel_requests_per_minute: int = Field(default=20, ge=1, le=200)
    amap_api_key: SecretStr | None = None
    amap_timeout: float = Field(default=8, gt=0, le=30)

    llm_provider: str = "fake"
    llm_model: str = "fake-local"
    llm_base_url: HttpUrl | None = None
    llm_api_key: SecretStr | None = None
    llm_timeout: float = Field(default=30.0, gt=0, le=300)
    llm_max_attempts: int = Field(default=3, ge=1, le=5)

    @field_validator("app_name", "host", "llm_provider", "llm_model")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_llm_provider_configuration(self) -> "Settings":
        if self.memory_backend == "mysql" and (not self.memory_mysql_user or self.memory_mysql_password is None):
            raise ValueError("MySQL记忆需要 MEMORY_MYSQL_USER 和 MEMORY_MYSQL_PASSWORD")
        provider = self.llm_provider.lower().replace("-", "_")
        if provider in {"openai", "openai_compatible"}:
            if self.llm_base_url is None:
                raise ValueError("LLM_BASE_URL is required for an OpenAI-compatible provider")
            if self.llm_api_key is None or not self.llm_api_key.get_secret_value().strip():
                raise ValueError("LLM_API_KEY is required for an OpenAI-compatible provider")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
