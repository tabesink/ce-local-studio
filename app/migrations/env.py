from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from context_engine.db import Base
import context_engine.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

database_url = os.environ.get("CONTEXT_ENGINE_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

SQLITE_EXPRESSION_INDEX_NAMES = {
    "ix_audit_events_actor_created",
    "ix_audit_events_created_at",
    "ix_audit_events_event_created",
    "ix_audit_events_target_created",
    "ix_conversations_owner_updated",
    "ix_conversation_turns_conversation_created",
    "ix_domain_operations_domain_created",
    "ix_source_documents_domain_created",
    "ix_source_preparation_operations_domain_created",
    "ix_source_preparation_operations_source_created",
}
comparing_sqlite = config.get_main_option("sqlalchemy.url").startswith("sqlite")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
baseline_without_event_ledger = context.get_x_argument(as_dictionary=True).get("baseline") == "true"


def include_object(_object, name: str | None, type_: str, _reflected: bool, _compare_to) -> bool:
    if comparing_sqlite and type_ == "index" and name in SQLITE_EXPRESSION_INDEX_NAMES:
        return False
    if (
        baseline_without_event_ledger and type_ == "table" and name == "conversation_turn_events"
    ):
        return False
    return True

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
