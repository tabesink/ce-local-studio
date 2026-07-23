from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.models import Conversation, User
from context_engine.services.auth import iso_utc

MAX_CONVERSATION_TITLE_CHARS = 120


class ConversationError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _not_found() -> ConversationError:
    return ConversationError(404, "conversation_not_found", "Conversation not found.")


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
        "id": conversation.id,
        "title": conversation.title,
        "createdAt": iso_utc(conversation.created_at),
        "updatedAt": iso_utc(conversation.updated_at),
    }


def get_owned_conversation(db: Session, *, owner: User, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_user_id == owner.id,
        )
    )
    if conversation is None:
        raise _not_found()
    return conversation


def list_conversations(db: Session, *, owner: User) -> list[dict[str, Any]]:
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.owner_user_id == owner.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc(), Conversation.id)
    )
    return [safe_conversation_summary(conversation) for conversation in conversations]


def create_conversation(db: Session, *, owner: User, title: str | None = None) -> Conversation:
    conversation = Conversation(owner_user_id=owner.id, title=normalize_conversation_title(title))
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def update_conversation_title(db: Session, *, owner: User, conversation_id: str, title: str | None) -> Conversation:
    conversation = get_owned_conversation(db, owner=owner, conversation_id=conversation_id)
    conversation.title = normalize_conversation_title(title)
    conversation.updated_at = utc_now()
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, *, owner: User, conversation_id: str) -> None:
    conversation = get_owned_conversation(db, owner=owner, conversation_id=conversation_id)
    db.delete(conversation)
    db.commit()
