"""Structured logging: one JSON object per line, from the standard library only."""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Formats a record as one JSON line: ts, level, logger, message, then any `fields` passed
    with `extra={"fields": {...}}`. Fields can never replace the standard keys. An exception is
    recorded by type only: its message can hold text we do not want in logs."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC)
        data = {
            "ts": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in getattr(record, "fields", {}).items():
            data.setdefault(key, value)
        if record.exc_info and record.exc_info[0] is not None:
            data["exc_type"] = record.exc_info[0].__name__
        return json.dumps(data, default=str)


def configure_logging(level: str) -> None:
    """Send the application's logs (the `app` logger and its children) to stderr as JSON lines.
    Safe to call more than once."""
    logger = logging.getLogger("app")
    logger.setLevel(level)
    logger.propagate = False  # the root logger would print every line a second time
    if not any(getattr(h, "_json_handler", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        handler._json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
