from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_WIKI_CONTRIBUTION_BLOCKED,
    AUDIT_EVENT_WIKI_CONTRIBUTION_CREATED,
    AUDIT_EVENT_WIKI_CONTRIBUTION_PUBLISHED,
    AUDIT_EVENT_WIKI_CONTRIBUTION_REJECTED,
    AUDIT_EVENT_WIKI_CONTRIBUTION_SUBMITTED,
    AUDIT_EVENT_WIKI_CONTRIBUTION_UPDATED,
    AUDIT_EVENT_WIKI_PAGE_INVALIDATED,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_ACTIVE,
    WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_INVALIDATED,
    WIKI_CONTRIBUTION_STATE_BLOCKED,
    WIKI_CONTRIBUTION_STATE_DRAFT,
    WIKI_CONTRIBUTION_STATE_PUBLISHED,
    WIKI_CONTRIBUTION_STATE_REJECTED,
    WIKI_CONTRIBUTION_STATE_SUBMITTED,
    WIKI_PAGE_STATE_NEEDS_REVIEW,
    WIKI_PAGE_STATE_PUBLISHED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    User,
    WikiContribution,
    WikiContributionEvidenceRef,
    WikiPage,
    WikiRevision,
)
from context_engine.services.audit import AuditContext, AuditService
from context_engine.services.auth import iso_utc

MAX_WIKI_TITLE_CHARS = 160
MAX_WIKI_BODY_CHARS = 20000
MAX_WIKI_EVIDENCE_REFS = 50
MAX_REVIEWER_NOTE_CHARS = 500


class WikiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _validation_error() -> WikiError:
    return WikiError(422, "validation_error", "Request validation failed.")


def _contribution_not_found() -> WikiError:
    return WikiError(404, "wiki_contribution_not_found", "Wiki contribution not found.")


def _page_not_found() -> WikiError:
    return WikiError(404, "wiki_page_not_found", "Wiki page not found.")


def _state_conflict() -> WikiError:
    return WikiError(409, "wiki_contribution_state_conflict", "Wiki contribution is not in the required state.")


def _context_unavailable() -> WikiError:
    return WikiError(409, "wiki_contribution_context_unavailable", "Wiki contribution context is unavailable.")


def _normalize_text(value: str, *, max_chars: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_chars:
        raise _validation_error()
    if any(unicodedata.category(char)[0] == "C" for char in normalized):
        raise _validation_error()
    return normalized


def _optional_note(value: str | None) -> str | None:
    if value is None:
        return None
    note = value.strip()
    if not note:
        return None
    if len(note) > MAX_REVIEWER_NOTE_CHARS:
        raise _validation_error()
    if any(unicodedata.category(char)[0] == "C" for char in note):
        raise _validation_error()
    return note


def _normalize_evidence_ref_ids(evidence_ref_ids: list[str] | None) -> list[str]:
    if evidence_ref_ids is None:
        return []
    if len(evidence_ref_ids) > MAX_WIKI_EVIDENCE_REFS:
        raise _validation_error()
    cleaned = [value.strip() for value in evidence_ref_ids]
    if any(not value or len(value) > 36 for value in cleaned):
        raise _validation_error()
    if len(set(cleaned)) != len(cleaned):
        raise _validation_error()
    return cleaned


def _audit(
    db: Session,
    event_name: str,
    *,
    audit_context: AuditContext | None,
    target_kind: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_context is None:
        return
    AuditService(db).record(
        event_name,
        context=audit_context,
        target_kind=target_kind,
        target_id=target_id,
        metadata=metadata,
    )


def _safe_evidence_ref(ref: WikiContributionEvidenceRef) -> dict[str, Any]:
    # Invalidated refs must not expose labels as usable citations (DATA-001 redaction rules).
    invalidated = ref.state != WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_ACTIVE
    return {
        "id": ref.id,
        "evidenceRefId": ref.conversation_turn_evidence_ref_id,
        "citationLabel": None if invalidated else ref.citation_label,
        "sourceLabel": None if invalidated else ref.source_label,
        "state": ref.state,
    }


def safe_wiki_contribution(contribution: WikiContribution) -> dict[str, Any]:
    published_revision = contribution.published_revision
    return {
        "id": contribution.id,
        "targetPageId": contribution.target_wiki_page_id,
        "publishedPageId": published_revision.wiki_page_id if published_revision is not None else None,
        "publishedRevisionId": published_revision.id if published_revision is not None else None,
        "title": contribution.title,
        "body": contribution.body,
        "state": contribution.state,
        "reviewerNote": contribution.reviewer_note,
        "evidenceRefs": [_safe_evidence_ref(ref) for ref in contribution.evidence_refs],
        "submittedAt": iso_utc(contribution.submitted_at) if contribution.submitted_at is not None else None,
        "reviewedAt": iso_utc(contribution.reviewed_at) if contribution.reviewed_at is not None else None,
        "createdAt": iso_utc(contribution.created_at),
        "updatedAt": iso_utc(contribution.updated_at),
    }


def safe_wiki_page(page: WikiPage) -> dict[str, Any]:
    return {
        "id": page.id,
        "title": page.title,
        "state": page.state,
        "currentRevisionId": page.current_revision_id,
        "createdAt": iso_utc(page.created_at),
        "updatedAt": iso_utc(page.updated_at),
    }


def _revision_evidence_refs(revision: WikiRevision) -> list[WikiContributionEvidenceRef]:
    contribution = revision.published_from_contribution
    return list(contribution.evidence_refs) if contribution is not None else []


def safe_wiki_revision(revision: WikiRevision) -> dict[str, Any]:
    return {
        "id": revision.id,
        "wikiPageId": revision.wiki_page_id,
        "revisionNumber": revision.revision_number,
        "title": revision.title,
        "body": revision.body,
        "publishedFromContributionId": revision.published_from_contribution_id,
        "publishedAt": iso_utc(revision.published_at),
        "evidenceRefs": [_safe_evidence_ref(ref) for ref in _revision_evidence_refs(revision)],
        "createdAt": iso_utc(revision.created_at),
    }


def _get_member_page(db: Session, page_id: str) -> WikiPage:
    page = db.scalar(select(WikiPage).where(WikiPage.id == page_id, WikiPage.state == WIKI_PAGE_STATE_PUBLISHED))
    if page is None:
        raise _page_not_found()
    return page


def list_wiki_pages(db: Session) -> list[dict[str, Any]]:
    pages = db.scalars(
        select(WikiPage)
        .where(WikiPage.state == WIKI_PAGE_STATE_PUBLISHED)
        .order_by(WikiPage.updated_at.desc(), WikiPage.created_at.desc(), WikiPage.id)
    )
    return [safe_wiki_page(page) for page in pages]


def get_wiki_page_detail(db: Session, page_id: str) -> dict[str, Any]:
    page = _get_member_page(db, page_id)
    current_revision = db.get(WikiRevision, page.current_revision_id) if page.current_revision_id else None
    return {
        "page": safe_wiki_page(page),
        "currentRevision": safe_wiki_revision(current_revision) if current_revision is not None else None,
    }


def list_wiki_page_revisions(db: Session, page_id: str) -> list[dict[str, Any]]:
    page = _get_member_page(db, page_id)
    revisions = db.scalars(
        select(WikiRevision)
        .where(WikiRevision.wiki_page_id == page.id)
        .order_by(WikiRevision.revision_number.desc(), WikiRevision.created_at.desc())
    )
    return [safe_wiki_revision(revision) for revision in revisions]


def _target_page_or_none(db: Session, target_page_id: str | None) -> WikiPage | None:
    if target_page_id is None:
        return None
    page = db.scalar(select(WikiPage).where(WikiPage.id == target_page_id, WikiPage.state == WIKI_PAGE_STATE_PUBLISHED))
    if page is None:
        raise _page_not_found()
    return page


def _owned_contribution(db: Session, *, user: User, contribution_id: str) -> WikiContribution:
    contribution = db.scalar(
        select(WikiContribution).where(
            WikiContribution.id == contribution_id,
            WikiContribution.created_by_user_id == user.id,
        )
    )
    if contribution is None:
        raise _contribution_not_found()
    return contribution


def _admin_contribution(db: Session, contribution_id: str) -> WikiContribution:
    contribution = db.scalar(
        select(WikiContribution).where(
            WikiContribution.id == contribution_id,
            WikiContribution.state.in_(
                [
                    WIKI_CONTRIBUTION_STATE_SUBMITTED,
                    WIKI_CONTRIBUTION_STATE_PUBLISHED,
                    WIKI_CONTRIBUTION_STATE_REJECTED,
                    WIKI_CONTRIBUTION_STATE_BLOCKED,
                ]
            ),
        )
    )
    if contribution is None:
        raise _contribution_not_found()
    return contribution


def _validated_evidence_refs(
    db: Session,
    *,
    owner: User,
    evidence_ref_ids: list[str],
) -> list[ConversationTurnEvidenceRef]:
    if not evidence_ref_ids:
        return []
    refs = list(
        db.scalars(
            select(ConversationTurnEvidenceRef)
            .join(ConversationTurn)
            .join(Conversation)
            .where(
                ConversationTurnEvidenceRef.id.in_(evidence_ref_ids),
                Conversation.owner_user_id == owner.id,
                ConversationTurn.status == TURN_STATUS_COMPLETED,
                ConversationTurn.route == TURN_ROUTE_DOMAIN_RAG,
                ConversationTurnEvidenceRef.redacted_at.is_(None),
            )
        )
    )
    by_id = {ref.id: ref for ref in refs}
    ordered = [by_id.get(ref_id) for ref_id in evidence_ref_ids]
    if any(ref is None for ref in ordered):
        raise _context_unavailable()
    return [ref for ref in ordered if ref is not None]


def _replace_contribution_evidence_refs(
    db: Session,
    contribution: WikiContribution,
    refs: list[ConversationTurnEvidenceRef],
) -> None:
    contribution.evidence_refs.clear()
    db.flush()
    for index, ref in enumerate(refs, start=1):
        contribution.evidence_refs.append(
            WikiContributionEvidenceRef(
                conversation_turn_evidence_ref_id=ref.id,
                ref_order=index,
                citation_label=ref.citation_label,
                source_label=ref.source_label,
                state=WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_ACTIVE,
            )
        )


def _ensure_contribution_context_active(contribution: WikiContribution) -> None:
    if any(ref.state != WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_ACTIVE for ref in contribution.evidence_refs):
        raise _context_unavailable()
    for ref in contribution.evidence_refs:
        source_ref = ref.conversation_turn_evidence_ref
        if source_ref is None or source_ref.redacted_at is not None:
            raise _context_unavailable()


def list_wiki_contributions(db: Session, *, user: User) -> list[dict[str, Any]]:
    contributions = db.scalars(
        select(WikiContribution)
        .where(WikiContribution.created_by_user_id == user.id)
        .order_by(WikiContribution.updated_at.desc(), WikiContribution.created_at.desc(), WikiContribution.id)
    )
    return [safe_wiki_contribution(contribution) for contribution in contributions]


def create_wiki_contribution(
    db: Session,
    *,
    user: User,
    target_page_id: str | None,
    title: str,
    body: str,
    evidence_ref_ids: list[str] | None,
    audit_context: AuditContext | None = None,
) -> WikiContribution:
    page = _target_page_or_none(db, target_page_id)
    title = _normalize_text(title, max_chars=MAX_WIKI_TITLE_CHARS)
    body = _normalize_text(body, max_chars=MAX_WIKI_BODY_CHARS)
    refs = _validated_evidence_refs(db, owner=user, evidence_ref_ids=_normalize_evidence_ref_ids(evidence_ref_ids))
    now = utc_now()
    contribution = WikiContribution(
        target_wiki_page_id=page.id if page is not None else None,
        created_by_user_id=user.id,
        title=title,
        body=body,
        state=WIKI_CONTRIBUTION_STATE_DRAFT,
        created_at=now,
        updated_at=now,
    )
    db.add(contribution)
    db.flush()
    _replace_contribution_evidence_refs(db, contribution, refs)
    _audit(
        db,
        AUDIT_EVENT_WIKI_CONTRIBUTION_CREATED,
        audit_context=audit_context,
        target_kind="wiki_contribution",
        target_id=contribution.id,
        metadata={
            "wikiContributionState": contribution.state,
            "evidenceRefCount": len(refs),
        },
    )
    db.commit()
    db.refresh(contribution)
    return contribution


def get_wiki_contribution(db: Session, *, user: User, contribution_id: str) -> WikiContribution:
    return _owned_contribution(db, user=user, contribution_id=contribution_id)


def update_wiki_contribution(
    db: Session,
    *,
    user: User,
    contribution_id: str,
    title: str | None = None,
    body: str | None = None,
    evidence_ref_ids: list[str] | None = None,
    audit_context: AuditContext | None = None,
) -> WikiContribution:
    contribution = _owned_contribution(db, user=user, contribution_id=contribution_id)
    if contribution.state != WIKI_CONTRIBUTION_STATE_DRAFT:
        raise _state_conflict()
    if title is not None:
        contribution.title = _normalize_text(title, max_chars=MAX_WIKI_TITLE_CHARS)
    if body is not None:
        contribution.body = _normalize_text(body, max_chars=MAX_WIKI_BODY_CHARS)
    if evidence_ref_ids is not None:
        refs = _validated_evidence_refs(db, owner=user, evidence_ref_ids=_normalize_evidence_ref_ids(evidence_ref_ids))
        _replace_contribution_evidence_refs(db, contribution, refs)
    now = utc_now()
    contribution.updated_at = now
    _audit(
        db,
        AUDIT_EVENT_WIKI_CONTRIBUTION_UPDATED,
        audit_context=audit_context,
        target_kind="wiki_contribution",
        target_id=contribution.id,
        metadata={"wikiContributionState": contribution.state, "evidenceRefCount": len(contribution.evidence_refs)},
    )
    db.commit()
    db.refresh(contribution)
    return contribution


def submit_wiki_contribution(
    db: Session,
    *,
    user: User,
    contribution_id: str,
    audit_context: AuditContext | None = None,
) -> WikiContribution:
    contribution = _owned_contribution(db, user=user, contribution_id=contribution_id)
    if contribution.state != WIKI_CONTRIBUTION_STATE_DRAFT:
        raise _state_conflict()
    _ensure_contribution_context_active(contribution)
    now = utc_now()
    contribution.state = WIKI_CONTRIBUTION_STATE_SUBMITTED
    contribution.submitted_at = now
    contribution.updated_at = now
    _audit(
        db,
        AUDIT_EVENT_WIKI_CONTRIBUTION_SUBMITTED,
        audit_context=audit_context,
        target_kind="wiki_contribution",
        target_id=contribution.id,
        metadata={"wikiContributionState": contribution.state, "evidenceRefCount": len(contribution.evidence_refs)},
    )
    db.commit()
    db.refresh(contribution)
    return contribution


def admin_list_wiki_contributions(db: Session) -> list[dict[str, Any]]:
    contributions = db.scalars(
        select(WikiContribution)
        .where(
            WikiContribution.state.in_(
                [
                    WIKI_CONTRIBUTION_STATE_SUBMITTED,
                    WIKI_CONTRIBUTION_STATE_PUBLISHED,
                    WIKI_CONTRIBUTION_STATE_REJECTED,
                    WIKI_CONTRIBUTION_STATE_BLOCKED,
                ]
            )
        )
        .order_by(WikiContribution.updated_at.desc(), WikiContribution.created_at.desc(), WikiContribution.id)
    )
    return [safe_wiki_contribution(contribution) for contribution in contributions]


def admin_get_wiki_contribution(db: Session, *, contribution_id: str) -> WikiContribution:
    return _admin_contribution(db, contribution_id)


def _next_revision_number(db: Session, page_id: str) -> int:
    current = db.scalar(select(func.max(WikiRevision.revision_number)).where(WikiRevision.wiki_page_id == page_id))
    return int(current or 0) + 1


def publish_wiki_contribution(
    db: Session,
    *,
    admin: User,
    contribution_id: str,
    audit_context: AuditContext | None = None,
) -> tuple[WikiPage, WikiRevision, WikiContribution]:
    contribution = _admin_contribution(db, contribution_id)
    existing_revision = db.scalar(
        select(WikiRevision).where(WikiRevision.published_from_contribution_id == contribution.id)
    )
    if contribution.state == WIKI_CONTRIBUTION_STATE_PUBLISHED and existing_revision is not None:
        page = db.get(WikiPage, existing_revision.wiki_page_id)
        if page is None:
            raise _page_not_found()
        return page, existing_revision, contribution
    if contribution.state != WIKI_CONTRIBUTION_STATE_SUBMITTED:
        raise _state_conflict()
    _ensure_contribution_context_active(contribution)

    now = utc_now()
    page = db.get(WikiPage, contribution.target_wiki_page_id) if contribution.target_wiki_page_id else None
    if page is None:
        page = WikiPage(title=contribution.title, state=WIKI_PAGE_STATE_PUBLISHED, created_at=now, updated_at=now)
        db.add(page)
        db.flush()
    elif page.state != WIKI_PAGE_STATE_PUBLISHED:
        raise WikiError(409, "wiki_page_conflict", "Wiki page is not publishable.")

    revision = WikiRevision(
        wiki_page_id=page.id,
        revision_number=_next_revision_number(db, page.id),
        title=contribution.title,
        body=contribution.body,
        published_from_contribution_id=contribution.id,
        published_by_user_id=admin.id,
        published_at=now,
        created_at=now,
    )
    db.add(revision)
    db.flush()
    page.title = contribution.title
    page.state = WIKI_PAGE_STATE_PUBLISHED
    page.current_revision_id = revision.id
    page.updated_at = now
    contribution.state = WIKI_CONTRIBUTION_STATE_PUBLISHED
    contribution.reviewed_by_user_id = admin.id
    contribution.reviewed_at = now
    contribution.updated_at = now
    _audit(
        db,
        AUDIT_EVENT_WIKI_CONTRIBUTION_PUBLISHED,
        audit_context=audit_context,
        target_kind="wiki_contribution",
        target_id=contribution.id,
        metadata={
            "wikiContributionState": contribution.state,
            "wikiPageState": page.state,
            "revisionNumber": revision.revision_number,
            "evidenceRefCount": len(contribution.evidence_refs),
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise WikiError(409, "wiki_page_conflict", "Wiki page conflict.") from exc
    db.refresh(page)
    db.refresh(revision)
    db.refresh(contribution)
    return page, revision, contribution


def reject_wiki_contribution(
    db: Session,
    *,
    admin: User,
    contribution_id: str,
    reviewer_note: str | None = None,
    audit_context: AuditContext | None = None,
) -> WikiContribution:
    contribution = _admin_contribution(db, contribution_id)
    if contribution.state != WIKI_CONTRIBUTION_STATE_SUBMITTED:
        raise _state_conflict()
    now = utc_now()
    contribution.state = WIKI_CONTRIBUTION_STATE_REJECTED
    contribution.reviewed_by_user_id = admin.id
    contribution.reviewed_at = now
    contribution.reviewer_note = _optional_note(reviewer_note)
    contribution.updated_at = now
    _audit(
        db,
        AUDIT_EVENT_WIKI_CONTRIBUTION_REJECTED,
        audit_context=audit_context,
        target_kind="wiki_contribution",
        target_id=contribution.id,
        metadata={"wikiContributionState": contribution.state, "evidenceRefCount": len(contribution.evidence_refs)},
    )
    db.commit()
    db.refresh(contribution)
    return contribution


def invalidate_wiki_for_evidence_refs(
    db: Session,
    evidence_ref_ids: list[str],
    audit_context: AuditContext | None = None,
) -> int:
    if not evidence_ref_ids:
        return 0
    now = utc_now()
    contribution_refs = list(
        db.scalars(
            select(WikiContributionEvidenceRef).where(
                WikiContributionEvidenceRef.conversation_turn_evidence_ref_id.in_(evidence_ref_ids),
                WikiContributionEvidenceRef.state == WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_ACTIVE,
            )
        )
    )
    if not contribution_refs:
        return 0
    contribution_ids = {ref.wiki_contribution_id for ref in contribution_refs}
    for ref in contribution_refs:
        ref.state = WIKI_CONTRIBUTION_EVIDENCE_REF_STATE_INVALIDATED
        ref.invalidated_at = now

    changed = len(contribution_refs)
    contributions = list(
        db.scalars(select(WikiContribution).where(WikiContribution.id.in_(contribution_ids))).unique()
    )
    for contribution in contributions:
        if contribution.state in {WIKI_CONTRIBUTION_STATE_DRAFT, WIKI_CONTRIBUTION_STATE_SUBMITTED}:
            contribution.state = WIKI_CONTRIBUTION_STATE_BLOCKED
            contribution.updated_at = now
            changed += 1
            _audit(
                db,
                AUDIT_EVENT_WIKI_CONTRIBUTION_BLOCKED,
                audit_context=audit_context,
                target_kind="wiki_contribution",
                target_id=contribution.id,
                metadata={
                    "wikiContributionState": contribution.state,
                    "evidenceRefCount": len(contribution.evidence_refs),
                },
            )
        elif contribution.state == WIKI_CONTRIBUTION_STATE_PUBLISHED:
            revision = db.scalar(
                select(WikiRevision).where(WikiRevision.published_from_contribution_id == contribution.id)
            )
            if revision is None:
                continue
            page = db.scalar(
                select(WikiPage).where(
                    WikiPage.current_revision_id == revision.id,
                    WikiPage.state == WIKI_PAGE_STATE_PUBLISHED,
                )
            )
            if page is None:
                continue
            page.state = WIKI_PAGE_STATE_NEEDS_REVIEW
            page.updated_at = now
            changed += 1
            _audit(
                db,
                AUDIT_EVENT_WIKI_PAGE_INVALIDATED,
                audit_context=audit_context,
                target_kind="wiki_page",
                target_id=page.id,
                metadata={"wikiPageState": page.state, "revisionNumber": revision.revision_number},
            )
    return changed
