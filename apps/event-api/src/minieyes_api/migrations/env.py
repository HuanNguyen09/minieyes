"""Alembic environment: online migrations only, against the URL set by migrate.config()."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from minieyes_api.db import metadata

config = context.config

engine = engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
