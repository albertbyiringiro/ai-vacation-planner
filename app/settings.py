"""The single place configuration is read: environment variables and an optional `.env` file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    # Unknown entries in .env are rejected (pydantic-settings default), so a typo like
    # ANTHROPIC_API_KY fails at startup instead of silently leaving the key unset.
    # Empty values count as unset so `.env.example` can be copied as-is.
    # hide_input_in_errors: a failed validation must not print the loaded values (secrets) in the
    # startup error, which ends up in terminals and logs.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    app_env: AppEnv = "development"
    database_url: str = "sqlite:///./app.db"
    # Required: the key that signs access tokens. HS256 needs at least 32 bytes (RFC 7518 3.2).
    jwt_secret: SecretStr = Field(min_length=32)
    # At most a week: without a bound a huge value starts fine and overflows at the first login.
    access_token_expire_minutes: int = Field(default=30, gt=0, le=10080)
    anthropic_api_key: SecretStr | None = None  # needed by the LLM client (app/llm)
    # The default model for LLM calls. Lower-case model IDs only, e.g. claude-sonnet-5-5; the live
    # tests pick their own cheaper model.
    llm_model: str = Field(
        default="claude-sonnet-5-5", pattern=r"^[a-z0-9][a-z0-9.-]{0,99}$"
    )
    # Optional: send API calls through a proxy or gateway instead of api.anthropic.com.
    anthropic_base_url: str | None = None
    log_level: LogLevel = "INFO"
    # Where every LLM call is recorded (one JSON line each) for scripts/spend.py. Git-ignored.
    llm_ledger_path: Path = Path("llm-ledger.jsonl")
    # Bounds on one LLM call. The timeout applies to each phase of a request (connect, write,
    # read), not to the whole call, so a normal failing call lasts about (retries + 1) x timeout
    # plus waits of at most llm_max_retry_wait_seconds, but a response that trickles bytes slowly
    # can run longer (ADR 0022). The wait cap must be above 0: the SDK treats a 0 wait as "no hint".
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300, allow_inf_nan=False)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_retry_wait_seconds: float = Field(
        default=20, gt=0, le=60, allow_inf_nan=False
    )

    @field_validator("anthropic_base_url")
    @classmethod
    def base_url_is_http(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("must be an http:// or https:// URL")
        if parsed.username or parsed.password:
            raise ValueError("must not contain a user name or password")
        # The API key travels in every request: only a local gateway may use plain http.
        if parsed.scheme == "http" and parsed.hostname not in LOCAL_HOSTS:
            raise ValueError("must use https unless the host is localhost")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
