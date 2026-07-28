"""Generate the versioned Path 1 expected-catalog snapshot from a pristine head DB.

Usage (against an empty database URL that this process may migrate):

  CONTEXT_ENGINE_DATABASE_URL=postgresql+psycopg://.../empty_db \\
    python -m context_engine.generate_schema_snapshot

The database must start empty. The module runs `alembic upgrade head`, collects
pg_catalog inventory, and writes
`context_engine/schema_snapshots/<SUPPORTED_ALEMBIC_HEAD>.json`.
"""

from __future__ import annotations

from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from context_engine.config import Settings
from context_engine.migrate_release import _bound_database_url_env
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.schema_compatibility import (
    collect_inventory_from_engine,
    is_empty_inventory,
    write_snapshot,
)


APP_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(APP_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(APP_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def generate(database_url: str | None = None) -> Path:
    settings = Settings(database_url=database_url) if database_url else Settings()
    target_url = settings.database_url
    with _bound_database_url_env(target_url):
        engine = create_engine(target_url, pool_pre_ping=True)
        try:
            inventory = collect_inventory_from_engine(engine)
            if not is_empty_inventory(inventory):
                raise SystemExit(
                    "refused: database is not empty; "
                    "provision a pristine database before generating the snapshot"
                )

            command.upgrade(_alembic_config(target_url), "head")
            with engine.connect() as connection:
                head = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if head != SUPPORTED_ALEMBIC_HEAD:
                raise SystemExit(
                    f"refused: upgraded head {head!r} != SUPPORTED_ALEMBIC_HEAD "
                    f"{SUPPORTED_ALEMBIC_HEAD!r}"
                )
            after = collect_inventory_from_engine(engine)
            return write_snapshot(after, head=SUPPORTED_ALEMBIC_HEAD)
        finally:
            engine.dispose()


def main() -> None:
    path = generate()
    print(f"Wrote schema snapshot: {path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
