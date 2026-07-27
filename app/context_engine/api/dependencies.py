from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.api.errors import ApiError, request_id_from
from context_engine.config import Settings
from context_engine.db import session_scope, utc_now
from context_engine.models import AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED, AUDIT_OUTCOME_DENIED, AuthSession, ROLE_ADMINISTRATOR, User
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext, AuditError, AuditService


@dataclass(frozen=True)
class CurrentSession:
    user: User
    auth_session: AuthSession


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from session_scope(request.app.state.session_factory)


def _unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "Authentication required.")


def require_current_session(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> CurrentSession:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _unauthenticated()

    token_hash = hash_session_token(token)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    now = utc_now()
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise _unauthenticated()
    last_used_at = auth_session.last_used_at or auth_session.created_at
    if last_used_at.timestamp() + settings.session_idle_ttl_seconds <= now.timestamp():
        raise _unauthenticated()

    user = db.get(User, auth_session.user_id)
    if user is None or user.is_disabled:
        raise _unauthenticated()

    if last_used_at.timestamp() + settings.session_touch_interval_seconds <= now.timestamp():
        auth_session.last_used_at = now
        db.commit()
    request.state.actor_kind = user.role
    request.state.actor_user_id = user.id
    return CurrentSession(user=user, auth_session=auth_session)


def require_current_user(current: CurrentSession = Depends(require_current_session)) -> User:
    return current.user


def require_admin(
    request: Request,
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> User:
    if current.user.role != ROLE_ADMINISTRATOR:
        try:
            AuditService(db).record(
                AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED,
                context=AuditContext(actor_user=current.user, request_id=request_id_from(request)),
                outcome=AUDIT_OUTCOME_DENIED,
                safe_error_code="forbidden",
            )
            db.commit()
        except AuditError:
            raise
        except Exception:
            db.rollback()
            raise AuditError() from None
        raise ApiError(403, "forbidden", "Forbidden.")
    return current.user
