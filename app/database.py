import sqlite3
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.settings import get_settings


class Base(DeclarativeBase):
    """Parent of every ORM model"""


def _enable_sqlite_foreign_keys(
    dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
) -> None:
    # SQLite ignores FOREIGN KEY constraints unless this is set on every connection, and the pragma
    # has no effect inside a transaction, so autocommit is switched on around it.
    previous = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
    finally:
        dbapi_connection.autocommit = previous


def make_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        raise ValueError(f"Only SQLite URLs are supported, got: {url.split(':', 1)[0]}")

    engine = create_engine(url, connect_args={"auto-commit": False})
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(get_engine(), expire_on_commit=False)


def reset_database_caches() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()

    get_engine.cache_clear()
    get_session_factory.cache_clear()


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
