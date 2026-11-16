"""The real LLMClient: the one place the Anthropic SDK is called."""

import email.utils
import math
import time
from collections.abc import Callable, Sequence

import anthropic
import httpx2

from app.llm.client import Effort, LLMResponse, Message, Usage
from app.llm.errors import (
    LLMAuthError,
    LLMBadRequestError,
    LLMConnectionError,
    LLMError,
    LLMOverloadedError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from app.settings import Settings

CONNECT_TIMEOUT_SECONDS = 5.0


def retry_after_seconds(headers: httpx2.Headers) -> float | None:
    """The wait a response asks for, in seconds, read the way the SDK reads it: the
    `retry-after-ms` header first, then `retry-after` as seconds, then as an HTTP date."""
    try:
        return float(headers["retry-after-ms"]) / 1000
    except (KeyError, ValueError):
        pass
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
        return None if math.isnan(seconds) else seconds
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_tz(value)
        if parsed is None:
            return None
        return float(email.utils.mktime_tz(parsed) - time.time())
    except (ValueError, OverflowError):
        # e.g. a date in the year 99999 cannot be converted: that is no hint, not a failure
        return None


def clamp_retry_after(max_seconds: float) -> Callable[[httpx2.Response], None]:
    """An HTTP response hook that cuts any requested wait down to `max_seconds`.

    The SDK obeys `retry-after` with no practical upper limit (its own cap is about 49 days), so a
    provider or proxy asking for an hour would hold a request thread for an hour. Clamping the
    header keeps the SDK's retries and bounds the sleep."""

    def hook(response: httpx2.Response) -> None:
        if response.status_code < 400:
            return  # only a failed call is ever retried, so only its header matters
        wait = retry_after_seconds(response.headers)
        if wait is None:
            # A header we cannot read is no hint at all. Remove it: the SDK parses these headers
            # with no protection (a date in the year 99999 makes it raise a bare ValueError), and
            # without a usable header it simply backs off by itself.
            response.headers.pop("retry-after-ms", None)
            response.headers.pop("retry-after", None)
        elif wait > max_seconds:
            response.headers.pop("retry-after-ms", None)  # the SDK reads this one first
            response.headers["retry-after"] = f"{max_seconds:g}"

    return hook


def translate(error: anthropic.APIError) -> LLMError:
    """Turn an SDK exception into one of our own types. The caller chains the original."""
    if isinstance(error, anthropic.APITimeoutError):
        return LLMTimeoutError()
    if isinstance(error, anthropic.APIConnectionError):
        return LLMConnectionError()
    if not isinstance(error, anthropic.APIStatusError):
        return LLMError()
    status = error.status_code
    details = {
        "request_id": error.request_id,
        "status_code": status,
        "retry_after": _positive(retry_after_seconds(error.response.headers)),
    }
    if status in (401, 403):
        return LLMAuthError(**details)
    if status == 429:
        return LLMRateLimitError(**details)
    if status in (503, 529):
        return LLMOverloadedError(**details)
    if status == 504:
        return LLMTimeoutError(**details)
    if status in (400, 404, 413, 422):
        return LLMBadRequestError(**details)
    if status >= 500:
        return LLMServerError(**details)
    return LLMError(**details)


def _positive(seconds: float | None) -> float | None:
    return seconds if seconds is not None and seconds > 0 else None


class AnthropicLLMClient:
    def __init__(self, sdk: anthropic.Anthropic, *, default_model: str) -> None:
        self._sdk = sdk
        self.default_model = default_model

    def __repr__(self) -> str:  # never include the SDK client: it holds the API key
        return f"AnthropicLLMClient(default_model={self.default_model!r})"

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: Effort | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        # Only what was asked for is sent. Sampling parameters (temperature, top_p) are left out on
        # purpose: the current models reject non-default values. Thinking and effort stay at the
        # model's own defaults unless the caller passes an effort.
        params: dict = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system is not None:
            params["system"] = system
        if effort is not None:
            params["output_config"] = {"effort": effort}
        try:
            message = self._sdk.messages.create(**params)
        except anthropic.APIError as error:
            # The SDK has already retried what it should (settings: llm_max_retries). What reaches
            # here is final, and becomes our own type with a safe message; `error` stays as the cause.
            raise translate(error) from error
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        details = usage.output_tokens_details
        return LLMResponse(
            text=text,
            model=message.model,
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_input_tokens=usage.cache_read_input_tokens or 0,
                cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
                thinking_tokens=details.thinking_tokens if details else None,
            ),
            stop_reason=message.stop_reason,
            request_id=message._request_id,
        )


def build_sdk_client(
    settings: Settings, *, transport: httpx2.BaseTransport | None = None
) -> anthropic.Anthropic:
    if settings.anthropic_api_key is None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set: add it to .env to call the model"
        )
    http_client = anthropic.DefaultHttpxClient(
        transport=transport,
        event_hooks={
            "response": [clamp_retry_after(settings.llm_max_retry_wait_seconds)]
        },
    )
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        base_url=settings.anthropic_base_url,
        # The connect timeout can never exceed the total one, so a tiny total timeout fails while
        # connecting, before any request is sent.
        timeout=httpx2.Timeout(
            settings.llm_timeout_seconds,
            connect=min(CONNECT_TIMEOUT_SECONDS, settings.llm_timeout_seconds),
        ),
        max_retries=settings.llm_max_retries,
        http_client=http_client,
    )


def build_llm_client(
    settings: Settings, *, transport: httpx2.BaseTransport | None = None
) -> AnthropicLLMClient:
    sdk = build_sdk_client(settings, transport=transport)
    return AnthropicLLMClient(sdk, default_model=settings.llm_model)
