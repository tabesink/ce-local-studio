from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_TEMPLATE,
    PROMPT_TEMPLATE_STATE_APPROVED,
    TURN_STATUS_COMPLETED,
    ComposerRefToken,
    Conversation,
    ConversationTurnComposerRef,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    Domain,
    PromptTemplate,
    SourceDocument,
    User,
)
from context_engine.services.domains import controller_from_settings, domain_available
from context_engine.services.indexing import source_is_query_eligible
from context_engine.services.prompt_templates import safe_prompt_template_ref

MAX_COMPOSER_REFS = 25
MAX_COMPOSER_REFS_PER_KIND = 4
COMPOSER_REF_TOKEN_TTL_SECONDS = 15 * 60
MAX_DISCOVERY_QUERY_CHARS = 200
MAX_DISCOVERY_LIMIT = 25
PHASE_ONE_COMPOSER_REF_KINDS = (
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_TEMPLATE,
)


class ComposerRefError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _validation_error() -> ComposerRefError:
    return ComposerRefError(422, "validation_error", "Request validation failed.")


def _normalize_kinds(kinds: list[str] | None) -> list[str]:
    if not kinds:
        return list(PHASE_ONE_COMPOSER_REF_KINDS)
    if len(kinds) > len(PHASE_ONE_COMPOSER_REF_KINDS):
        raise _validation_error()
    normalized: list[str] = []
    for kind in kinds:
        if kind not in PHASE_ONE_COMPOSER_REF_KINDS:
            raise _validation_error()
        if kind not in normalized:
            normalized.append(kind)
    return normalized


def _normalize_query(query: str | None) -> str | None:
    if query is None:
        return None
    cleaned = query.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_DISCOVERY_QUERY_CHARS:
        raise _validation_error()
    return cleaned


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_ref_token(
    db: Session,
    *,
    owner: User,
    kind: str,
    target_id: str,
    domain_id: str | None,
    label: str,
    description: str | None,
) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(seconds=COMPOSER_REF_TOKEN_TTL_SECONDS)
    db.add(
        ComposerRefToken(
            token_hash=_token_hash(token),
            owner_user_id=owner.id,
            ref_kind=kind,
            target_id=target_id,
            domain_id=domain_id,
            safe_label=label,
            safe_description=description,
            expires_at=expires_at,
        )
    )
    return token, expires_at


def _safe_result(
    db: Session,
    *,
    owner: User,
    kind: str,
    target_id: str,
    domain_id: str | None,
    label: str,
    description: str | None,
) -> dict[str, Any]:
    token, expires_at = _issue_ref_token(
        db,
        owner=owner,
        kind=kind,
        target_id=target_id,
        domain_id=domain_id,
        label=label,
        description=description,
    )
    return {
        "token": token,
        "kind": kind,
        "label": label,
        "description": description,
        "expiresAt": expires_at,
    }


def _matches_query(*, query: str | None, values: tuple[str | None, ...]) -> bool:
    if query is None:
        return True
    needle = query.casefold()
    return any(needle in (value or "").casefold() for value in values)


def _discover_templates(
    db: Session,
    *,
    owner: User,
    query: str | None,
    remaining: int,
) -> list[dict[str, Any]]:
    if remaining <= 0:
        return []
    statement = (
        select(PromptTemplate)
        .where(PromptTemplate.state == PROMPT_TEMPLATE_STATE_APPROVED)
        .order_by(PromptTemplate.name, PromptTemplate.id)
    )
    if query is None:
        statement = statement.limit(remaining)
    templates = db.scalars(statement)
    refs: list[dict[str, Any]] = []
    for template in templates:
        safe = safe_prompt_template_ref(template)
        if not _matches_query(query=query, values=(safe["label"], safe.get("description"))):
            continue
        refs.append(
            _safe_result(
                db,
                owner=owner,
                kind=COMPOSER_REF_KIND_TEMPLATE,
                target_id=template.id,
                domain_id=None,
                label=safe["label"],
                description=safe.get("description"),
            )
        )
        if len(refs) >= remaining:
            break
    return refs


def _discover_sources(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    domain_id: str | None,
    query: str | None,
    remaining: int,
) -> list[dict[str, Any]]:
    if remaining <= 0 or domain_id is None:
        return []
    domain = db.get(Domain, domain_id)
    controller = controller_from_settings(settings)
    if domain is None or not domain_available(db, domain, controller):
        return []
    sources = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.domain_id == domain.id)
        .order_by(SourceDocument.created_at.desc(), SourceDocument.id)
    )
    refs: list[dict[str, Any]] = []
    for source in sources:
        if not source_is_query_eligible(db, source, domain, settings=settings, controller=controller):
            continue
        label = source.original_filename
        description = source.content_type
        if not _matches_query(query=query, values=(label, description)):
            continue
        refs.append(
            _safe_result(
                db,
                owner=owner,
                kind=COMPOSER_REF_KIND_SOURCE,
                target_id=source.id,
                domain_id=domain.id,
                label=label,
                description=description,
            )
        )
        if len(refs) >= remaining:
            break
    return refs


def _discover_evidence(
    db: Session,
    *,
    owner: User,
    conversation_id: str | None,
    domain_id: str | None,
    query: str | None,
    remaining: int,
) -> list[dict[str, Any]]:
    if remaining <= 0 or conversation_id is None or domain_id is None:
        return []
    statement = (
        select(ConversationTurnEvidenceRef)
        .join(ConversationTurn, ConversationTurnEvidenceRef.turn_id == ConversationTurn.id)
        .join(Conversation, ConversationTurn.conversation_id == Conversation.id)
        .where(
            Conversation.public_ref == conversation_id,
            Conversation.owner_user_id == owner.id,
            ConversationTurn.domain_id == domain_id,
            ConversationTurn.status == TURN_STATUS_COMPLETED,
            ConversationTurnEvidenceRef.redacted_at.is_(None),
        )
        .order_by(ConversationTurn.created_at.desc(), ConversationTurnEvidenceRef.evidence_order)
    )
    if query is None:
        statement = statement.limit(remaining)
    rows = db.scalars(statement)
    refs: list[dict[str, Any]] = []
    for evidence_ref in rows:
        label = evidence_ref.citation_label or evidence_ref.source_label or "Evidence"
        description = evidence_ref.source_label
        if not _matches_query(query=query, values=(label, description)):
            continue
        refs.append(
            _safe_result(
                db,
                owner=owner,
                kind=COMPOSER_REF_KIND_EVIDENCE,
                target_id=evidence_ref.id,
                domain_id=domain_id,
                label=label,
                description=description,
            )
        )
        if len(refs) >= remaining:
            break
    return refs


def discover_composer_refs(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    conversation_id: str | None = None,
    domain_id: str | None = None,
    kinds: list[str] | None = None,
    query: str | None = None,
    limit: int = MAX_COMPOSER_REFS,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > MAX_DISCOVERY_LIMIT:
        raise _validation_error()
    normalized_kinds = _normalize_kinds(kinds)
    cleaned_query = _normalize_query(query)
    refs: list[dict[str, Any]] = []
    for kind in normalized_kinds:
        remaining = limit - len(refs)
        if remaining <= 0:
            break
        if kind == COMPOSER_REF_KIND_TEMPLATE:
            refs.extend(_discover_templates(db, owner=owner, query=cleaned_query, remaining=remaining))
        elif kind == COMPOSER_REF_KIND_SOURCE:
            refs.extend(
                _discover_sources(
                    db,
                    settings=settings,
                    owner=owner,
                    domain_id=domain_id,
                    query=cleaned_query,
                    remaining=remaining,
                )
            )
        elif kind == COMPOSER_REF_KIND_EVIDENCE:
            refs.extend(
                _discover_evidence(
                    db,
                    owner=owner,
                    conversation_id=conversation_id,
                    domain_id=domain_id,
                    query=cleaned_query,
                    remaining=remaining,
                )
            )
    db.commit()
    return refs[:limit]



@dataclass(frozen=True)
class ValidatedComposerRef:
    order: int
    kind: str
    label: str | None
    description: str | None
    domain_id: str | None = None
    source_document_id: str | None = None
    source_block_id: str | None = None
    evidence_ref_id: str | None = None
    prompt_template_id: str | None = None


@dataclass(frozen=True)
class ComposerRefValidation:
    fingerprint: str
    refs: tuple[ValidatedComposerRef, ...]


def _composer_ref_unavailable() -> ComposerRefError:
    return ComposerRefError(409, "composer_ref_unavailable", "Composer reference is unavailable.")


def normalize_composer_ref_tokens(tokens: list[str] | None) -> tuple[str, ...]:
    if not tokens:
        return ()
    if len(tokens) > MAX_COMPOSER_REFS:
        raise _validation_error()
    normalized: list[str] = []
    for token in tokens:
        if not isinstance(token, str):
            raise _validation_error()
        cleaned = token.strip()
        if not cleaned or cleaned != token or len(cleaned) > 256:
            raise _validation_error()
        if any(ord(char) < 33 or ord(char) > 126 for char in cleaned):
            raise _validation_error()
        normalized.append(cleaned)
    if len(set(normalized)) != len(normalized):
        raise _validation_error()
    return tuple(normalized)


def composer_ref_fingerprint(tokens: tuple[str, ...]) -> str:
    if not tokens:
        from context_engine.models import EMPTY_COMPOSER_REF_FINGERPRINT

        return EMPTY_COMPOSER_REF_FINGERPRINT
    hashes = [_token_hash(token) for token in tokens]
    payload = "\n".join(hashes).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _enforce_ref_caps(tokens: tuple[str, ...], token_rows: list[ComposerRefToken]) -> None:
    if len(tokens) > MAX_COMPOSER_REFS:
        raise _validation_error()
    counts: dict[str, int] = {}
    for row in token_rows:
        counts[row.ref_kind] = counts.get(row.ref_kind, 0) + 1
        if counts[row.ref_kind] > MAX_COMPOSER_REFS_PER_KIND:
            raise _validation_error()


def _token_row_by_hash(db: Session, *, owner: User, token: str) -> ComposerRefToken:
    row = db.scalar(
        select(ComposerRefToken).where(
            ComposerRefToken.token_hash == _token_hash(token),
            ComposerRefToken.owner_user_id == owner.id,
        )
    )
    if row is None:
        raise _composer_ref_unavailable()
    if row.expires_at <= utc_now():
        raise _composer_ref_unavailable()
    if row.consumed_at is not None:
        raise _composer_ref_unavailable()
    return row


def consume_composer_ref_tokens(
    db: Session,
    *,
    owner: User,
    tokens: tuple[str, ...],
) -> None:
    """Mark validated tokens consumed under row locks. Call only on new-turn insert."""
    if not tokens:
        return
    hashes = [_token_hash(token) for token in tokens]
    rows = list(
        db.scalars(
            select(ComposerRefToken)
            .where(
                ComposerRefToken.token_hash.in_(hashes),
                ComposerRefToken.owner_user_id == owner.id,
            )
            .order_by(ComposerRefToken.token_hash)
            .with_for_update()
        )
    )
    by_hash = {row.token_hash: row for row in rows}
    now = utc_now()
    for token_hash in hashes:
        row = by_hash.get(token_hash)
        if row is None or row.expires_at <= now or row.consumed_at is not None:
            raise _composer_ref_unavailable()
        row.consumed_at = now


def _validate_template_ref(db: Session, row: ComposerRefToken, order: int) -> ValidatedComposerRef:
    template = db.get(PromptTemplate, row.target_id)
    if template is None or template.state != PROMPT_TEMPLATE_STATE_APPROVED:
        raise _composer_ref_unavailable()
    return ValidatedComposerRef(
        order=order,
        kind=COMPOSER_REF_KIND_TEMPLATE,
        label=row.safe_label,
        description=row.safe_description,
        prompt_template_id=template.id,
    )


def _validate_source_ref(
    db: Session,
    *,
    settings: Settings,
    row: ComposerRefToken,
    order: int,
    domain_id: str | None,
) -> ValidatedComposerRef:
    if domain_id is None or row.domain_id != domain_id:
        raise _composer_ref_unavailable()
    domain = db.get(Domain, domain_id)
    source = db.get(SourceDocument, row.target_id)
    controller = controller_from_settings(settings)
    if domain is None or source is None or source.domain_id != domain.id:
        raise _composer_ref_unavailable()
    if not source_is_query_eligible(db, source, domain, settings=settings, controller=controller):
        raise _composer_ref_unavailable()
    return ValidatedComposerRef(
        order=order,
        kind=COMPOSER_REF_KIND_SOURCE,
        label=row.safe_label,
        description=row.safe_description,
        domain_id=domain.id,
        source_document_id=source.id,
    )


def _validate_evidence_ref(
    db: Session,
    *,
    owner: User,
    row: ComposerRefToken,
    order: int,
    conversation_id: str,
    domain_id: str | None,
) -> ValidatedComposerRef:
    if domain_id is None or row.domain_id != domain_id:
        raise _composer_ref_unavailable()
    evidence_ref = db.scalar(
        select(ConversationTurnEvidenceRef)
        .join(ConversationTurn, ConversationTurnEvidenceRef.turn_id == ConversationTurn.id)
        .join(Conversation, ConversationTurn.conversation_id == Conversation.id)
        .where(
            ConversationTurnEvidenceRef.id == row.target_id,
            ConversationTurnEvidenceRef.redacted_at.is_(None),
            Conversation.id == conversation_id,
            Conversation.owner_user_id == owner.id,
            ConversationTurn.status == TURN_STATUS_COMPLETED,
            ConversationTurn.domain_id == domain_id,
        )
    )
    if evidence_ref is None:
        raise _composer_ref_unavailable()
    return ValidatedComposerRef(
        order=order,
        kind=COMPOSER_REF_KIND_EVIDENCE,
        label=row.safe_label,
        description=row.safe_description,
        domain_id=domain_id,
        evidence_ref_id=evidence_ref.id,
    )


def validate_composer_ref_tokens(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    conversation_id: str,
    domain_id: str | None,
    tokens: list[str] | None,
) -> ComposerRefValidation:
    normalized_tokens = normalize_composer_ref_tokens(tokens)
    fingerprint = composer_ref_fingerprint(normalized_tokens)
    if not normalized_tokens:
        return ComposerRefValidation(fingerprint=fingerprint, refs=())
    token_rows = [_token_row_by_hash(db, owner=owner, token=token) for token in normalized_tokens]
    _enforce_ref_caps(normalized_tokens, token_rows)
    refs: list[ValidatedComposerRef] = []
    for order, row in enumerate(token_rows, start=1):
        if row.ref_kind == COMPOSER_REF_KIND_TEMPLATE:
            refs.append(_validate_template_ref(db, row, order))
        elif row.ref_kind == COMPOSER_REF_KIND_SOURCE:
            refs.append(_validate_source_ref(db, settings=settings, row=row, order=order, domain_id=domain_id))
        elif row.ref_kind == COMPOSER_REF_KIND_EVIDENCE:
            refs.append(
                _validate_evidence_ref(
                    db,
                    owner=owner,
                    row=row,
                    order=order,
                    conversation_id=conversation_id,
                    domain_id=domain_id,
                )
            )
        else:
            raise _composer_ref_unavailable()
    return ComposerRefValidation(fingerprint=fingerprint, refs=tuple(refs))


def persist_accepted_composer_refs(
    db: Session,
    *,
    turn_id: str,
    refs: tuple[ValidatedComposerRef, ...],
) -> None:
    for ref in refs:
        db.add(
            ConversationTurnComposerRef(
                turn_id=turn_id,
                ref_order=ref.order,
                ref_kind=ref.kind,
                safe_label=ref.label,
                safe_description=ref.description,
                domain_id=ref.domain_id,
                source_document_id=ref.source_document_id,
                source_block_id=ref.source_block_id,
                evidence_ref_id=ref.evidence_ref_id,
                prompt_template_id=ref.prompt_template_id,
            )
        )
