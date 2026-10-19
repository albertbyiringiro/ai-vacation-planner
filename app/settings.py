from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )
    app_env: AppEnv = "development"
    database_url: str = "sqlite:///./vacation.db"
    anthropic_api_key: SecretStr | None = None
    jwt_secret: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
