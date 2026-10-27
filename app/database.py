import sqlite3
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import (
    Engine,
    MetaData,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)
from sqlalchemy.pool import ConnectionPoolEntry

from app.settings import get_settings

# Every constraint gets a predictable name, which Alembic needs to alter or drop it later
# (SQLAlchemy docs: constraint naming conventions). Check constraints must be named explicitly.
# column_0_N_name joins all columns, so UNIQUE(itinerary_id, number) is not named after one.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": ("fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s"),
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base for all ORM models and Alembic metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enable_sqlite_foreign_keys(
    dbapi_connection: sqlite3.Connection,
    connection_record: ConnectionPoolEntry,
) -> None:
    """Enable SQLite foreign-key enforcement on every connection."""
    # SQLite ignores FOREIGN KEY constraints unless this is set on every connection, and the
    # pragma has no effect inside a transaction, so autocommit is switched on around it.
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


def make_engine(
    url: str,
    *,
    foreign_keys: bool = True,
) -> Engine:
    """Create a SQLite engine using modern transaction handling."""

    if not url.startswith("sqlite"):
        raise ValueError(
            f"Only SQLite URLs are supported (ADR 0001), got: {url.split(':', 1)[0]}"
        )

    # autocommit=False makes the sqlite3 driver (3.12+) use real transactions: without it DDL and
    # SAVEPOINT are not rolled back with their transaction.
    engine = create_engine(
        url,
        connect_args={
            "autocommit": False,
            "timeout": 10.0,
        },
    )

    if foreign_keys:
        event.listen(
            engine,
            "connect",
            _enable_sqlite_foreign_keys,
        )

    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        get_engine(),
        expire_on_commit=False,
    )


def reset_database_caches() -> None:
    """Clear cached database resources, primarily for tests."""

    get_session_factory.cache_clear()

    if get_engine.cache_info().currsize:
        get_engine().dispose()

    get_engine.cache_clear()


def get_db() -> Iterator[Session]:
    """Provide one SQLAlchemy session per request."""

    with get_session_factory()() as session:
        yield session
