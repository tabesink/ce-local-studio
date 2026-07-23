from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.api.conventions import format_utc_timestamp
from context_engine.db import utc_now
from context_engine.models import AuthSession, ROLE_ADMINISTRATOR, ROLE_MEMBER, User
from context_engine.security import generate_session_token, hash_password, hash_session_token, verify_password


def iso_utc(value: datetime) -> str:
    return format_utc_timestamp(value)


def safe_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "isDisabled": user.is_disabled,
    }


def seed_admin(db: Session, settings: Settings) -> User | None:
    if not settings.admin_username or not settings.admin_password:
        return None

    now = utc_now()
    user = db.scalar(select(User).where(User.username == settings.admin_username))
    password_hash = hash_password(settings.admin_password)
    if user is None:
        user = User(
            username=settings.admin_username,
            password_hash=password_hash,
            role=ROLE_ADMINISTRATOR,
            is_disabled=False,
            password_changed_at=now,
        )
        db.add(user)
    else:
        user.password_hash = password_hash
        user.role = ROLE_ADMINISTRATOR
        user.is_disabled = False
        user.password_changed_at = now
        user.updated_at = now
    db.commit()
    db.refresh(user)
    return user


def create_user(db: Session, username: str, password: str, role: str = ROLE_MEMBER, is_disabled: bool = False) -> User:
    now = utc_now()
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_disabled=is_disabled,
        password_changed_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or user.is_disabled:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def create_auth_session(db: Session, user: User, settings: Settings) -> tuple[str, AuthSession]:
    token = generate_session_token()
    now = utc_now()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
        created_at=now,
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return token, auth_session


def revoke_session_token(db: Session, token: str) -> bool:
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
    if auth_session is None or auth_session.revoked_at is not None:
        return False
    auth_session.revoked_at = utc_now()
    db.commit()
    return True
