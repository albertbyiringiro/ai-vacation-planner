from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Usage:
    """Tokens billed for one call. `thinking_tokens` is part of `output_tokens`, not extra."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    thinking_tokens: int | None = None
    service_tier: str | None = None
    inference_geo: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: Usage
    stop_reason: str | None
    request_id: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: Effort | None = None,
        model: str | None = None,
    ) -> LLMResponse: ...
