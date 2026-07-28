from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from context_engine.adapters.object_storage import ObjectStorageError, object_store_from_root
from context_engine.config import Settings
from context_engine.models import ROLE_ADMINISTRATOR, User


SUPPORTED_ALEMBIC_HEAD = "e9f2a1b83c70"


class ReadinessError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Service is not ready.")


def probe_object_store(source_storage_root: str) -> None:
    """Exercise the same filesystem store composition product code uses."""
    store = object_store_from_root(source_storage_root)
    stored = store.put(b"ce-ready-probe")
    store.delete(stored.key)


def check_database_schema(db: Session) -> None:
    """DB reachable and exact Alembic head — shared by API and worker readiness."""
    try:
        db.execute(text("SELECT 1"))
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SUPPORTED_ALEMBIC_HEAD:
            raise ReadinessError("schema_incompatible")
    except ReadinessError:
        raise
    except Exception as exc:
        raise ReadinessError("database_unavailable") from exc


def check_object_store_ready(settings: Settings) -> None:
    try:
        probe_object_store(settings.source_storage_root)
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
