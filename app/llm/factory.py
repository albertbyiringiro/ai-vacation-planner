"""Builds the LLM client the application uses: the real client, wrapped to log and keep a ledger."""

import threading

from app.llm.anthropic_client import build_llm_client
from app.llm.client import LLMClient
from app.llm.errors import LLMNotConfigured
from app.llm.observed import Ledger, LoggingLLMClient
from app.settings import Settings, get_settings

_client: LLMClient | None = None
_lock = threading.Lock()


def create_llm_client(settings: Settings) -> LLMClient:
    return LoggingLLMClient(
        build_llm_client(settings), ledger=Ledger(settings.llm_ledger_path)
    )


def get_llm_client() -> LLMClient:
    """The one client the appplication shared (it holds a connection pool)"""
    global _client
    with _lock:
        if _client is None:
            settings = get_settings()
            if settings.anthropic_api_key is None:
                raise LLMNotConfigured

            _client = create_llm_client(settings)

        return _client


def reset_llm_client() -> None:
    """Close and forget the shared client (at shutdown, and between tests"""
    global _client
    with _lock:
        client, _client = _client, None

    close = getattr(client, "close", None)
    if close is not None:
        close()
