"""Logging and spend tracking around any LLMClient: one log record and one ledger row per call."""

import json
import logging
import os
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from app.llm.client import Effort, LLMClient, LLMResponse, Message
from app.llm.pricing import estimate_cost

logger = logging.getLogger("app.llm")

MAX_TEXT = 200  # longest string kept in a record, so one ledger line always stays short


def clip(value: object) -> object:
    """Strings from outside (request ids, stop reasons) are cut to a safe length."""
    return value[:MAX_TEXT] if isinstance(value, str) else value


class Ledger:
    """An append-only file with one JSON object per line, readable and writable only by its owner.
    Writing is serialised within the process, and each row is a single short write to a file
    opened for appending, so rows from several processes do not interleave either."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict) -> None:
        row = {
            "ts": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        }
        row.update(record)
        line = json.dumps(row, default=str, allow_nan=False) + "\n"
        with self._lock:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # 0o600 applies when the file is created; the folder was created 0o700 just above.
            # (The built-in open takes an opener; Path.open does not.)
            with open(
                self.path,
                "a",
                encoding="utf-8",
                opener=lambda path, flags: os.open(path, flags, 0o600),
            ) as file:
                file.write(line)


class LoggingLLMClient:
    """Wraps an LLMClient. Records model, latency, tokens, status, request id and estimated cost
    for every call, whether it succeeds or fails. It never records prompt, system or answer text.

    Recording can never change the outcome of a call: whatever goes wrong while recording is
    logged as a warning, a successful answer is still returned and a failure is still raised.

    Latency is wall-clock time for the whole call, so it includes any retries the provider's SDK
    made inside it (the number of attempts is not visible from here)."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        ledger: Ledger | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._clock = clock

    def __repr__(self) -> str:
        return f"LoggingLLMClient({self._inner!r})"

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: Effort | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        requested = model or getattr(self._inner, "default_model", None)
        started = self._clock()
        try:
            response = self._inner.complete(
                messages,
                system=system,
                max_tokens=max_tokens,
                effort=effort,
                model=model,
            )
        except Exception as error:
            latency_ms = round((self._clock() - started) * 1000, 1)
            self._record_safely(
                logging.WARNING,
                partial(self._failure_fields, error, requested, latency_ms),
            )
            raise
        latency_ms = round((self._clock() - started) * 1000, 1)
        self._record_safely(
            logging.INFO,
            partial(self._success_fields, response, requested, latency_ms),
        )
        return response

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            close()

    @staticmethod
    def _failure_fields(
        error: Exception, requested: str | None, latency_ms: float
    ) -> dict:
        return {
            "event": "llm_call",
            "status": "error",
            "error_type": type(error).__name__,
            "http_status": getattr(error, "status_code", None),
            "request_id": clip(getattr(error, "request_id", None)),
            "requested_model": clip(requested),
            "model": None,
            "latency_ms": latency_ms,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
            "stop_reason": None,
            "service_tier": None,
            "est_cost_usd": None,
        }

    @staticmethod
    def _success_fields(
        response: LLMResponse, requested: str | None, latency_ms: float
    ) -> dict:
        usage = response.usage
        return {
            "event": "llm_call",
            "status": "ok",
            "error_type": None,
            "http_status": None,
            "request_id": clip(response.request_id),
            "requested_model": clip(requested),
            "model": clip(response.model),
            "latency_ms": latency_ms,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "thinking_tokens": usage.thinking_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
            "stop_reason": clip(response.stop_reason),
            "service_tier": clip(usage.service_tier),
            "est_cost_usd": estimate_cost(response.model, usage),
        }

    def _record_safely(self, level: int, build_fields: Callable[[], dict]) -> None:
        try:
            self._record(level, build_fields())
        except Exception as error:  # noqa: BLE001 - recording must never change a call's outcome
            # Losing a record is bad; losing a paid answer, or hiding the real error, is worse.
            logger.warning(
                "llm_call record failed",
                extra={
                    "fields": {
                        "event": "record_error",
                        "error_type": type(error).__name__,
                    }
                },
            )

    def _record(self, level: int, fields: dict) -> None:
        logger.log(level, "llm_call", extra={"fields": fields})
        if self._ledger is None:
            return
        try:
            self._ledger.append(fields)
        except Exception as error:  # noqa: BLE001 - a ledger problem must not fail the request
            # Losing a spend row is bad; failing the user's request because of it is worse.
            logger.warning(
                "ledger write failed",
                extra={
                    "fields": {
                        "event": "ledger_error",
                        "error_type": type(error).__name__,
                    }
                },
            )
