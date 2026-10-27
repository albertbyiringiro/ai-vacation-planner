from logging.config import fileConfig

from alembic import context

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.database import Base, make_engine
from app.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# render_as_batch: SQLite cannot ALTER most things, so Alembic recreates the table ("batch mode").
# compare_type is already on by default; it is spelled out so the choice is visible.
CONTEXT_OPTIONS = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
    "compare_type": True,
}


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_settings().database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **CONTEXT_OPTIONS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(get_settings().database_url, foreign_keys=False)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, **CONTEXT_OPTIONS)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()  # also when a migration fails, or the pooled connection leaks


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
