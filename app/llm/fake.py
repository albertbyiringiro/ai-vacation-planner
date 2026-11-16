"""A scripted stand-in for the real client, for tests (ADR 0003)."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.llm.client import Effort, LLMResponse, Message, Usage


class ScriptExhausted(AssertionError):
    """The code under test made more LLM calls than the test scripted."""


@dataclass(frozen=True)
class Call:
    messages: list[Message]
    system: str | None
    max_tokens: int
    effort: Effort | None
    model: str


class FakeLLMClient:
    """Answers calls from a script, in order. An entry is a string (becomes a response with
    zero-cost usage), a ready-made `LLMResponse`, or an exception, which is raised. Every call is
    recorded in `calls`. Running past the end of the script fails loudly."""

    def __init__(
        self,
        script: Sequence[str | LLMResponse | Exception],
        *,
        default_model: str = "claude-sonnet-5-5",
    ) -> None:
        self._script = list(script)
        self.default_model = default_model
        self.calls: list[Call] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: Effort | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        used_model = model or self.default_model
        self.calls.append(Call(list(messages), system, max_tokens, effort, used_model))
        if not self._script:
            raise ScriptExhausted(
                f"LLM call number {len(self.calls)} was not scripted in the FakeLLMClient"
            )
        entry = self._script.pop(0)
        if isinstance(entry, Exception):
            raise entry
        if isinstance(entry, str):
            return LLMResponse(
                text=entry,
                model=used_model,
                usage=Usage(input_tokens=0, output_tokens=0),
                stop_reason="end_turn",
            )
        return entry
