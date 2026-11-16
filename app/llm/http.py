"""How LLM errors look to an HTTP client: one status and one safe message per error type."""

import math

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.llm.errors import (
    LLMError,
    LLMOverloadedError,
    LLMRateLimitError,
    LLMTimeoutError,
)

STATUS = {
    LLMRateLimitError: 503,
    LLMOverloadedError: 503,
    LLMTimeoutError: 504,
    LLMError: 502,
}


def llm_error_response(request: Request, exc: Exception) -> JSONResponse:
    # Starlette types handlers as taking Exception. Only LLMError reaches this one, so narrow it here.
    if not isinstance(exc, LLMError):
        raise exc

    status = next(STATUS[cls] for cls in type(exc).__mro__ if cls in STATUS)
    headers: dict[str, str] = {}

    if status == 503 and exc.retry_after is not None:
        headers["Retry-After"] = str(math.ceil(exc.retry_after))

    return JSONResponse(
        status_code=status, content={"detail": exc.message}, headers=headers
    )


def register_llm_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LLMError, llm_error_response)
