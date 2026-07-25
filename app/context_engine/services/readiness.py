from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from context_engine.models import ROLE_ADMINISTRATOR, User


SUPPORTED_ALEMBIC_HEAD = "b5c8e2d19f47"


class ReadinessError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("Service is not ready.")


def check_readiness(db: Session) -> None:
    try:
        db.execute(text("SELECT 1"))
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SUPPORTED_ALEMBIC_HEAD:
            raise ReadinessError("schema_incompatible")

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
