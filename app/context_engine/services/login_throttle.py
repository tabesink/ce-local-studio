from __future__ import annotations

from datetime import timedelta
import hashlib
import math

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import LoginThrottleBucket


CLEANUP_AGE = timedelta(hours=24)
CLEANUP_LIMIT = 100


class LoginRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("Login temporarily unavailable.")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def throttle_key(client_bucket: str, username: str) -> tuple[str, str]:
    return _hash(client_bucket), _hash(username.strip().casefold())


def assert_login_allowed(db: Session, *, client_bucket: str, username: str) -> None:
    client_hash, username_hash = throttle_key(client_bucket, username)
    row = db.scalar(
        select(LoginThrottleBucket).where(
            LoginThrottleBucket.client_bucket_hash == client_hash,
            LoginThrottleBucket.username_hash == username_hash,
        )
    )
    now = utc_now()
    if row is not None and row.blocked_until is not None and row.blocked_until > now:
        raise LoginRateLimited(math.ceil((row.blocked_until - now).total_seconds()))


def _cleanup_stale(db: Session, now) -> None:
    stale_ids = list(
        db.scalars(
            select(LoginThrottleBucket.id)
            .where(LoginThrottleBucket.updated_at < now - CLEANUP_AGE)
            .order_by(LoginThrottleBucket.updated_at, LoginThrottleBucket.id)
            .limit(CLEANUP_LIMIT)
        )
    )
    if stale_ids:
        db.execute(delete(LoginThrottleBucket).where(LoginThrottleBucket.id.in_(stale_ids)))


def record_login_failure(
    db: Session,
    settings: Settings,
    *,
    client_bucket: str,
    username: str,
) -> None:
    client_hash, username_hash = throttle_key(client_bucket, username)
    now = utc_now()
    window_cutoff = now - timedelta(seconds=settings.login_throttle_window_seconds)
    blocked_until = now + timedelta(seconds=settings.login_throttle_block_seconds)
    table = LoginThrottleBucket.__table__
    statement = insert(table).values(
        id=hashlib.sha256(f"{client_hash}:{username_hash}".encode("ascii")).hexdigest()[:36],
        client_bucket_hash=client_hash,
        username_hash=username_hash,
        window_started_at=now,
        failure_count=1,
        blocked_until=None,
        updated_at=now,
    )
    window_expired = table.c.window_started_at <= window_cutoff
    next_count = case((window_expired, 1), else_=table.c.failure_count + 1)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.client_bucket_hash, table.c.username_hash],
        set_={
            "window_started_at": case((window_expired, now), else_=table.c.window_started_at),
            "failure_count": next_count,
            "blocked_until": case(
                (window_expired, None),
                (table.c.blocked_until > now, table.c.blocked_until),
                (next_count >= settings.login_throttle_max_failures, blocked_until),
                else_=None,
            ),
            "updated_at": now,
        },
    )
    db.execute(statement)
    _cleanup_stale(db, now)
    db.commit()


def clear_login_failures(db: Session, *, client_bucket: str, username: str) -> None:
    client_hash, username_hash = throttle_key(client_bucket, username)
    db.execute(
        delete(LoginThrottleBucket).where(
            LoginThrottleBucket.client_bucket_hash == client_hash,
            LoginThrottleBucket.username_hash == username_hash,
        )
    )
    _cleanup_stale(db, utc_now())
    db.commit()
