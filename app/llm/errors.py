"""Our own error types for LLM calls"""

import math
from typing import Any


class LLMError(Exception):
    message = "The AI service had a problem. Please try again"

    def __init__(
        self,
        *,
        request_id: str | None = None,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(self.message)
        self.request_id = request_id
        self.status_code = status_code
        usable = (
            retry_after is not None and math.isfinite(retry_after) and retry_after > 0
        )
        self.retry_after = retry_after if usable else None

    def __reduce__(self):
        # __init__ takes keyword-only arguments: tell copy and pickle how to rebuild the error.
        return (
            _rebuild,
            (type(self), self.request_id, self.status_code, self.retry_after),
        )


def _rebuild(cls, request_id, status_code, retry_after):
    return cls(request_id=request_id, status_code=status_code, retry_after=retry_after)


class LLMAuthError(LLMError):
    """Our key was rejected or lacks permission: a configuration problem, not the caller's."""

    message = "The AI service is not set up correctly. Please try again later."


class LLMBadRequestError(LLMError):
    """The provider refused our request (a bug or misconfiguration on our side)."""

    message = "The AI service could not process the request."


class LLMRateLimitError(LLMError):
    message = "The AI service is busy. Please try again shortly."


class LLMOverloadedError(LLMError):
    message = "The AI service is busy. Please try again shortly."


class LLMServerError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    message = "The AI service took too long to answer."


class LLMConnectionError(LLMError):
    message = "The AI service could not be reached."


class LLMNotConfigured(LLMError):
    """No API key is set on this server: nothing was sent anywhere"""

    message = "The AI service is not configured on this server."


class LLMUnusableAnswerError(LLMError):
    """The model answered, but the answer is not an itinerary we can store. `reason` is a short
    code for logs (never the text of the answer)."""

    message = "The AI service returned an itinerary we could not use. Please try again."

    def __init__(self, reason: str = "unusable", **details) -> None:
        super().__init__(**details)
        self.reason = reason

    def __reduce__(self) -> tuple[Any, ...]:
        # The extra `reason` must survive copy and pickle (a worker pool pickles errors).
        return (
            _rebuild_unusable,
            (self.reason, self.request_id, self.status_code, self.retry_after),
        )


def _rebuild_unusable(reason, request_id, status_code, retry_after):
    return LLMUnusableAnswerError(
        reason, request_id=request_id, status_code=status_code, retry_after=retry_after
    )
