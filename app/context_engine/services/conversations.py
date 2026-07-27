from __future__ import annotations

import base64
import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_CONVERSATION_CREATED,
    AUDIT_EVENT_CONVERSATION_DELETED,
    AUDIT_EVENT_CONVERSATION_RENAMED,
    AuthSession,
    Conversation,
    User,
)
from context_engine.services.audit import AuditContext, commit_protected_mutation
from context_engine.services.auth import MutationAuthenticationError, iso_utc, revalidate_mutation_actor
from context_engine.services.public_refs import generate_unique_public_ref

MAX_CONVERSATION_TITLE_CHARS = 120
DEFAULT_CONVERSATION_PAGE_SIZE = 50
MAX_CONVERSATION_PAGE_SIZE = 100


class ConversationError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ConversationPage:
    conversations: list[dict[str, Any]]
    next_cursor: str | None


def _not_found() -> ConversationError:
    return ConversationError(404, "not_found", "Conversation not found.")


def _stale_revision() -> ConversationError:
    return ConversationError(409, "stale_revision", "The conversation changed. Refresh and try again.")


def normalize_conversation_title(value: str | None) -> str | None:
    if value is None:
        return None
    title = value.strip()
    if not title:
        return None
    if len(title) > MAX_CONVERSATION_TITLE_CHARS:
        raise ConversationError(422, "validation_error", "Request validation failed.")
    if any(unicodedata.category(char)[0] == "C" for char in title):
        raise ConversationError(422, "validation_error", "Request validation failed.")
    return title


def safe_conversation_summary(conversation: Conversation) -> dict[str, Any]:
    return {
        "id": conversation.public_ref,
        "title": conversation.title,
        "createdAt": iso_utc(conversation.created_at),
        "updatedAt": iso_utc(conversation.updated_at),
        "version": conversation.version,
    }


def get_owned_conversation(db: Session, *, owner: User, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.public_ref == conversation_id,
            Conversation.owner_user_id == owner.id,
        )
    )
    if conversation is None:
        raise _not_found()
    return conversation


def get_owned_conversation_detail(db: Session, *, owner: User, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.public_ref == conversation_id,
            Conversation.owner_user_id == owner.id,
        )
        .with_for_update(read=True)
    )
    if conversation is None:
        raise _not_found()
    return conversation


def lock_owned_conversation(db: Session, *, owner: User, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.public_ref == conversation_id,
            Conversation.owner_user_id == owner.id,
        )
        .with_for_update()
    )
    if conversation is None:
        raise _not_found()
    return conversation


def _encode_cursor(conversation: Conversation) -> str:
    payload = json.dumps(
        {"version": 1, "conversationRef": conversation.public_ref},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        conversation_ref = str(payload["conversationRef"])
        if (
            set(payload) != {"version", "conversationRef"}
            or payload["version"] != 1
            or not conversation_ref.startswith("conv_")
        ):
            raise ValueError
        return conversation_ref
    except (KeyError, TypeError, ValueError):
        raise ConversationError(410, "cursor_expired", "The cursor has expired.") from None


def list_conversations(
    db: Session,
    *,
    owner: User,
    cursor: str | None = None,
    limit: int = DEFAULT_CONVERSATION_PAGE_SIZE,
) -> ConversationPage:
    if not 1 <= limit <= MAX_CONVERSATION_PAGE_SIZE:
        raise ConversationError(422, "validation_error", "Request validation failed.")

    statement = select(Conversation).where(Conversation.owner_user_id == owner.id)
    if cursor:
        public_ref = _decode_cursor(cursor)
        anchor = db.scalar(
            select(Conversation).where(
                Conversation.owner_user_id == owner.id,
                Conversation.public_ref == public_ref,
            )
        )
        if anchor is None:
            raise ConversationError(410, "cursor_expired", "The cursor has expired.")
        statement = statement.where(
            or_(
                Conversation.created_at < anchor.created_at,
                and_(Conversation.created_at == anchor.created_at, Conversation.id < anchor.id),
            )
        )

    rows = list(
        db.scalars(
            statement.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    return ConversationPage(
        conversations=[safe_conversation_summary(conversation) for conversation in page_rows],
        next_cursor=_encode_cursor(page_rows[-1]) if has_more and page_rows else None,
    )


def _revalidate_mutation_actor(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    auth_session: AuthSession,
) -> User:
    try:
        return revalidate_mutation_actor(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
        )
    except MutationAuthenticationError:
        raise ConversationError(401, "unauthenticated", "Authentication required.")


def create_conversation(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    title: str | None = None,
    auth_session: AuthSession,
    audit_context: AuditContext | None = None,
) -> Conversation:
    locked_owner = _revalidate_mutation_actor(
        db,
        settings=settings,
        owner=owner,
        auth_session=auth_session,
    )
    conversation = Conversation(
        public_ref=generate_unique_public_ref(
            db,
            prefix="conv",
            column=Conversation.public_ref,
        ),
        owner_user_id=locked_owner.id,
        title=normalize_conversation_title(title),
    )

    def mutate() -> Conversation:
        db.add(conversation)
        db.flush()
        return conversation

    result = commit_protected_mutation(
        db,
        mutate,
        event_name=AUDIT_EVENT_CONVERSATION_CREATED,
        context=audit_context or AuditContext(actor_user=locked_owner),
        target_kind="conversation",
        target_id=conversation.public_ref,
    )
    db.refresh(result)
    return result


def update_conversation_title(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    conversation_id: str,
    title: str | None,
    expected_version: int,
    auth_session: AuthSession,
    audit_context: AuditContext | None = None,
) -> Conversation:
    locked_owner = _revalidate_mutation_actor(
        db,
        settings=settings,
        owner=owner,
        auth_session=auth_session,
    )
    conversation = lock_owned_conversation(
        db,
        owner=locked_owner,
        conversation_id=conversation_id,
    )
    if conversation.version != expected_version:
        raise _stale_revision()

    def mutate() -> Conversation:
        conversation.title = normalize_conversation_title(title)
        conversation.version += 1
        conversation.updated_at = utc_now()
        db.flush()
        return conversation

    result = commit_protected_mutation(
        db,
        mutate,
        event_name=AUDIT_EVENT_CONVERSATION_RENAMED,
        context=audit_context or AuditContext(actor_user=locked_owner),
        target_kind="conversation",
        target_id=conversation.public_ref,
    )
    db.refresh(result)
    return result


def delete_conversation(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    conversation_id: str,
    expected_version: int,
    auth_session: AuthSession,
    audit_context: AuditContext | None = None,
) -> None:
    locked_owner = _revalidate_mutation_actor(
        db,
        settings=settings,
        owner=owner,
        auth_session=auth_session,
    )
    conversation = lock_owned_conversation(
        db,
        owner=locked_owner,
        conversation_id=conversation_id,
    )
    if conversation.version != expected_version:
        raise _stale_revision()
    public_ref = conversation.public_ref

    def mutate() -> None:
        db.delete(conversation)
        db.flush()

    commit_protected_mutation(
        db,
        mutate,
        event_name=AUDIT_EVENT_CONVERSATION_DELETED,
        context=audit_context or AuditContext(actor_user=locked_owner),
        target_kind="conversation",
        target_id=public_ref,
    )
