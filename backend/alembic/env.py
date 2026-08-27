"""
Alembic environment — async SQLAlchemy 2.0 configuration.

Imports all domain models so Alembic can autogenerate migrations
against the platform (control-plane) metadata database.
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

# Import all models so their metadata is registered for autogenerate
import app.domain.auth.models  # noqa: F401
import app.domain.chat.models  # noqa: F401
import app.domain.connections.models  # noqa: F401
import app.domain.projects.models  # noqa: F401
import app.domain.schema_introspection.models  # noqa: F401
import app.domain.semantic_layer.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.core.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    if not url:
        url = "postgresql+asyncpg://platform:change_me@postgres:5432/platform_db"
    return url


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_database_url())
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn, target_metadata=target_metadata
            )
        )
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
