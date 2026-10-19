from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import health
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None, None]:
    get_settings()
    yield


app = FastAPI(title="AI Vacation Planner", lifespan=lifespan)

app.include_router(health.router)
