from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import auth, health
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None, None]:
    get_settings()
    yield


app = FastAPI(title="AI Vacation Planner", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {key: value for key, value in error.items() if key != "input"}
        for error in exc.errors()
    ]

    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})
