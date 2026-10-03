import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.database import DATABASE_URL, Base
from app.models import Show, Seat, Reservation, ReservationSeat, UserShowBookingState

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema='service',
        include_schemas=True,
    )

    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS service")
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        version_table_schema='service',
        include_schemas=True,
        # Only migrate the service schema
        include_name=lambda name, type_, parent_names: (type_ == "schema" and name == "service") or (type_ != "schema" and parent_names and "service" in parent_names) or (type_ != "schema" and not parent_names)
    )

    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS service")
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
