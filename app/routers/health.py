from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import SettingsDep
from app.settings import AppEnv

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: AppEnv


@router.get("/health")
def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.app_env)
