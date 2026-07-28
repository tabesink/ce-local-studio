from __future__ import annotations

import base64
import json
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from context_engine.models import User
from context_engine.services.auth import safe_user

DEFAULT_USER_LIST_PAGE_SIZE = 50
MAX_USER_LIST_PAGE_SIZE = 100


class UserDirectoryError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _encode_user_cursor(user: User) -> str:
    payload = json.dumps(
        {"version": 1, "userId": user.id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_user_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        user_id = str(payload["userId"])
        if set(payload) != {"version", "userId"} or payload["version"] != 1 or not user_id:
            raise ValueError
        return user_id
    except (KeyError, TypeError, ValueError):
        raise UserDirectoryError(410, "cursor_expired", "The cursor has expired.") from None


def list_admin_users(
    db: Session,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_USER_LIST_PAGE_SIZE,
) -> dict[str, Any]:
    if not 1 <= limit <= MAX_USER_LIST_PAGE_SIZE:
        raise UserDirectoryError(422, "validation_error", "Request validation failed.")

    statement = select(User)
    if cursor:
        user_id = _decode_user_cursor(cursor)
        anchor = db.get(User, user_id)
        if anchor is None:
            raise UserDirectoryError(410, "cursor_expired", "The cursor has expired.")
        statement = statement.where(
            or_(
                User.created_at < anchor.created_at,
                and_(User.created_at == anchor.created_at, User.id < anchor.id),
            )
        )

    rows = list(
        db.scalars(statement.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1))
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    return {
        "users": [safe_user(user) for user in page_rows],
        "nextCursor": _encode_user_cursor(page_rows[-1]) if has_more and page_rows else None,
    }
