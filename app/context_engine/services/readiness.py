from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import ObjectStorageError, object_store_from_settings
from context_engine.config import Settings
from context_engine.models import ROLE_ADMINISTRATOR, User


SUPPORTED_ALEMBIC_HEAD = "d4e7a1b92c80"


class ReadinessError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Service is not ready.")


def probe_object_store(settings: Settings) -> None:
    """Exercise the same store composition product code uses (filesystem or S3)."""
    store = object_store_from_settings(settings)
    stored = store.put(b"ce-ready-probe")
    store.delete(stored.key)


def check_catalog_compatibility(db: Session) -> None:
    """Exact head catalog must match the versioned Path 1 snapshot."""
    from context_engine.services.schema_compatibility import (
        classify_inventory,
        collect_inventory,
    )

    connection = db.connection()
    inventory = collect_inventory(connection)
    verdict = classify_inventory(inventory, policy="startup", supported_head=SUPPORTED_ALEMBIC_HEAD)
    if not verdict.accepted:
        raise ReadinessError("schema_incompatible")


def check_database_schema(db: Session) -> None:
    """DB reachable, exact Alembic head, and catalog match — API and worker readiness."""
    try:
        db.execute(text("SELECT 1"))
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SUPPORTED_ALEMBIC_HEAD:
            raise ReadinessError("schema_incompatible")
        check_catalog_compatibility(db)
    except ReadinessError:
        raise
    except Exception as exc:
        raise ReadinessError("database_unavailable") from exc


def check_object_store_ready(settings: Settings) -> None:
    try:
        probe_object_store(settings)
    except (ObjectStorageError, OSError, TypeError, ValueError) as exc:
        raise ReadinessError("object_store_unavailable") from exc
    except Exception as exc:
        raise ReadinessError("object_store_unavailable") from exc


def check_worker_readiness(db: Session, settings: Settings | None = None) -> None:
    """Internal worker readiness: schema + store. Does not require an administrator."""
    resolved = settings if settings is not None else Settings()
    check_database_schema(db)
    check_object_store_ready(resolved)


def check_readiness(db: Session, settings: Settings | None = None) -> None:
    resolved = settings if settings is not None else Settings()
    check_database_schema(db)
    try:
        administrator_exists = db.scalar(
            select(User.id)
            .where(
                User.role == ROLE_ADMINISTRATOR,
                User.is_disabled.is_(False),
            )
            .limit(1)
        )
        if administrator_exists is None:
            raise ReadinessError("bootstrap_incomplete")
    except ReadinessError:
        raise
    except Exception as exc:
        raise ReadinessError("database_unavailable") from exc

    check_object_store_ready(resolved)
