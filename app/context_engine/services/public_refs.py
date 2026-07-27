from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

PUBLIC_REF_COLLISION_ATTEMPTS = 3


class PublicRefCollisionError(RuntimeError):
    pass


def new_public_ref_candidate(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def generate_unique_public_ref(
    db: Session,
    *,
    prefix: str,
    column: InstrumentedAttribute[str],
) -> str:
    for _attempt in range(PUBLIC_REF_COLLISION_ATTEMPTS):
        candidate = new_public_ref_candidate(prefix)
        if db.scalar(select(column).where(column == candidate)) is None:
            return candidate
    raise PublicRefCollisionError("Unable to allocate an opaque public reference.")
