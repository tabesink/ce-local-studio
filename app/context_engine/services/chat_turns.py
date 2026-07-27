from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, load_only, selectinload

from context_engine.adapters.synthesis import (
    RegistrySynthesisStreamAdapter,
    SynthesisAdapterError,
)
from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_CHAT_TURN_REDACTED,
    TURN_EVENT_ACCEPTED,
    TURN_EVENT_ANSWER_DELTA,
    TURN_EVENT_CANCELLED,
    TURN_EVENT_COMPLETED,
    TURN_EVENT_EVIDENCE_DELTA,
    TURN_EVENT_FAILED,
    TURN_EVENT_REDACTED,
    TURN_EVENT_RETRIEVAL_COMPLETED,
    TURN_EVENT_RETRIEVAL_STARTED,
    TURN_EVENT_ROUTE_SELECTED,
    TURN_EVENT_SCHEMA_VERSION,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_ROUTES,
    TURN_STATUS_CANCELLED,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_FAILED,
    TURN_STATUS_REDACTED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_CANCELLED,
    TURN_STOP_REASON_DIRECT_LLM,
    TURN_STOP_REASON_EVIDENCE_ONLY,
    TURN_STOP_REASON_GROUNDED,
    TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
    TURN_STOP_REASON_PROVIDER_FAILURE,
    TURN_STOP_REASON_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    ConversationTurnEvent,
    ConversationTurnEvidenceRef,
    Domain,
    SourceBlock,
    SourceDocument,
    AuthSession,
    User,
)
from context_engine.services.audit import AuditContext, AuditService
from context_engine.services.auth import MutationAuthenticationError, iso_utc, revalidate_mutation_actor
from context_engine.services.chat_intent import requires_domain
from context_engine.services.composer_refs import (
    ComposerRefError,
    ValidatedComposerRef,
    composer_ref_fingerprint,
    normalize_composer_ref_tokens,
    persist_accepted_composer_refs,
    validate_composer_ref_tokens,
)
from context_engine.services.conversations import get_owned_conversation, lock_owned_conversation
from context_engine.services.domains import DOMAIN_ID_PATTERN, controller_from_settings, domain_available
from context_engine.services.evidence import (
    EvidenceRetrievalError,
    InternalMappedEvidence,
    ScopedRetrievalError,
    ScopedRetrievalPort,
    resolve_available_domain,
    retrieve_internal_scoped_evidence,
    safe_section_label,
)
from context_engine.services.prompt_assembly import (
    PromptAssemblyContext,
    PromptAssemblyService,
)
from context_engine.services.public_refs import generate_unique_public_ref
from context_engine.services.runtime_config import (
    RuntimeConfigError,
    SecretCrypto,
    TrustedModelRuntimeConfig,
    TrustedRuntimeResolver,
)
from context_engine.services.structured_logging import safe_log
from context_engine.services.sources import sanitize_original_filename
from context_engine.services.tracing import TraceMetadata, tracer_from_settings

logger = logging.getLogger(__name__)

CLIENT_REQUEST_ID_MIN_CHARS = 8
CLIENT_REQUEST_ID_MAX_CHARS = 80
TURN_MESSAGE_MAX_CHARS = 4000
MAX_PRIOR_USER_QUESTIONS = 4
_DOMAIN_ID_RE = re.compile(DOMAIN_ID_PATTERN)
SAFE_PROVIDER_FAILURE_MESSAGE = "The answer could not be completed."
SAFE_TURN_CANCELLED_MESSAGE = "The answer was cancelled."
RETRIEVAL_INTENTS = ("fact", "overview", "verbatim")
OPERATION_TO_INTENT = {
    "retrieve_fact": "fact",
    "retrieve_overview": "overview",
    "retrieve_verbatim": "verbatim",
}


class ChatTurnError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class TurnClaimResult:
    turn: ConversationTurn
    replay: bool


@dataclass(frozen=True)
class TurnStartResult:
    turn: ConversationTurn
    replay: bool
    synthesis: TrustedModelRuntimeConfig | None
    prior_user_questions: tuple[str, ...]
    request_id: str | None = None
    assembly_context: PromptAssemblyContext | None = None
    execution_generation: int | None = None


@dataclass(frozen=True)
class TurnStreamEvent:
    event_id: str
    turn_id: str
    sequence: int
    event_type: str
    occurred_at: Any
    payload: dict[str, Any]


@dataclass(frozen=True)
class PublicEvidenceRef:
    id: str
    citation_label: str
    source_label: str
    excerpt: str


class SynthesisProviderError(Exception):
    """Orchestrator-facing synthesis failure; never carries prompts or credentials."""

    def __init__(self, message: str = SAFE_PROVIDER_FAILURE_MESSAGE, *, code: str = "provider_failure") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class OrchestrationPolicyError(Exception):
    pass


class SynthesisStreamAdapter:
    """Orchestrator-facing synthesis port.

    Production default is the typed registry facade. Tests may subclass this
    type and inject via ``app.state.synthesis_stream_adapter``.
    """

    def stream_direct(
        self,
        *,
        synthesis: TrustedModelRuntimeConfig,
        message: str,
        prior_user_questions: tuple[str, ...],
        assembly_context: PromptAssemblyContext | None = None,
    ) -> Iterable[str]:
        raise SynthesisProviderError()

    def stream_grounded(
        self,
        *,
        synthesis: TrustedModelRuntimeConfig,
        message: str,
        evidence: tuple[PublicEvidenceRef, ...],
        prior_user_questions: tuple[str, ...],
        assembly_context: PromptAssemblyContext | None = None,
    ) -> Iterable[str]:
        raise SynthesisProviderError()


def default_synthesis_stream_adapter(settings: Settings) -> RegistrySynthesisStreamAdapter:
    return RegistrySynthesisStreamAdapter(
        timeout_seconds=float(settings.synthesis_timeout_seconds),
        max_output_tokens=int(settings.synthesis_max_output_tokens),
    )


class P6RetrievalPort:
    def __init__(
        self,
        *,
        client: ScopedRetrievalPort | None = None,
        controller=None,
    ) -> None:
        self._client = client
        self._controller = controller

    def retrieve(
        self,
        db: Session,
        *,
        settings: Settings,
        domain_id: str,
        question: str,
        intent: str,
    ) -> list[InternalMappedEvidence]:
        if intent not in RETRIEVAL_INTENTS:
            raise OrchestrationPolicyError("Retrieval operation is not allowed.")
        try:
            result = retrieve_internal_scoped_evidence(
                db,
                settings=settings,
                domain_id=domain_id,
                question=question,
                client=self._client,
                controller=self._controller,
            )
        except ScopedRetrievalError as exc:
            raise ChatTurnError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.") from exc
        except EvidenceRetrievalError as exc:
            if exc.code == "domain_runtime_dependency_unavailable":
                raise ChatTurnError(
                    502,
                    "domain_runtime_unavailable",
                    "Knowledge domain runtime is unavailable.",
                ) from exc
            raise ChatTurnError(exc.status_code, exc.code, exc.message) from exc
        if not result.had_eligible_sources:
            return []
        return list(result.evidence)


def _validation_error() -> ChatTurnError:
    return ChatTurnError(422, "validation_error", "Request validation failed.")


def normalize_client_request_id(value: str) -> str:
    if len(value) < CLIENT_REQUEST_ID_MIN_CHARS or len(value) > CLIENT_REQUEST_ID_MAX_CHARS:
        raise _validation_error()
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise _validation_error()
    return value


def normalize_turn_message(value: str) -> str:
    message = value.strip()
    if not message or len(message) > TURN_MESSAGE_MAX_CHARS:
        raise _validation_error()
    return message


def normalize_optional_domain_id(value: str | None) -> str | None:
    if value is None:
        return None
    domain_id = value.strip()
    if not domain_id or _DOMAIN_ID_RE.fullmatch(domain_id) is None:
        raise _validation_error()
    return domain_id


def classify_turn_route(*, message: str, domain_id: str | None) -> tuple[str, str | None]:
    if domain_id is not None:
        return TURN_ROUTE_DOMAIN_RAG, domain_id
    if requires_domain(message):
        raise ChatTurnError(422, "domain_required", "A knowledge domain is required.")
    return TURN_ROUTE_DIRECT_LLM, None


def _validate_effective_route(*, route: str, domain_id: str | None) -> None:
    if route not in TURN_ROUTES:
        raise _validation_error()
    if route == TURN_ROUTE_DOMAIN_RAG and not domain_id:
        raise ChatTurnError(422, "domain_required", "A knowledge domain is required.")
    if route == TURN_ROUTE_DIRECT_LLM and domain_id is not None:
        raise _validation_error()


def _running_turn(db: Session, conversation_id: str) -> ConversationTurn | None:
    return db.scalar(
        select(ConversationTurn).where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.status == TURN_STATUS_RUNNING,
        )
    )


def _lock_conversation_for_turn_insert(
    db: Session,
    *,
    owner: User,
    conversation: Conversation,
) -> Conversation:
    return lock_owned_conversation(
        db,
        owner=owner,
        conversation_id=conversation.public_ref,
    )


def _existing_request_turn(db: Session, *, conversation_id: str, client_request_id: str) -> ConversationTurn | None:
    return db.scalar(
        select(ConversationTurn).where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.client_request_id == client_request_id,
        )
    )


def _matching_existing_turn(
    db: Session,
    *,
    conversation_id: str,
    client_request_id: str,
    user_message: str,
    domain_id: str | None,
    route: str,
    composer_ref_fingerprint: str | None = None,
) -> ConversationTurn | None:
    existing = _existing_request_turn(
        db,
        conversation_id=conversation_id,
        client_request_id=client_request_id,
    )
    if existing is None:
        return None
    if (
        existing.user_message != user_message
        or existing.domain_id != domain_id
        or existing.route != route
        or (
            composer_ref_fingerprint is not None
            and existing.composer_ref_fingerprint != composer_ref_fingerprint
        )
    ):
        raise ChatTurnError(409, "client_request_conflict", "Client request conflicts with an existing turn.")
    return existing


def _turn_start_replay(
    existing: ConversationTurn,
    *,
    request_id: str | None,
) -> TurnStartResult:
    safe_log(
        logger,
        "chat.turn_replayed",
        request_id=request_id,
        trace_id=existing.trace_id,
        domain_id=existing.domain_id,
        conversation_turn_id=existing.id,
        client_request_id=existing.client_request_id,
        outcome=existing.status,
        replay=True,
    )
    return TurnStartResult(
        turn=existing,
        replay=True,
        synthesis=None,
        prior_user_questions=(),
        request_id=request_id,
    )


def get_owned_turn(
    db: Session,
    *,
    owner: User,
    conversation_id: str,
    turn_id: str,
) -> ConversationTurn:
    conversation = get_owned_conversation(db, owner=owner, conversation_id=conversation_id)
    turn = db.scalar(
        select(ConversationTurn).where(
            ConversationTurn.public_ref == turn_id,
            ConversationTurn.conversation_id == conversation.id,
        )
    )
    if turn is None:
        raise ChatTurnError(404, "not_found", "Conversation turn not found.")
    return turn


def _prior_user_questions(db: Session, conversation_id: str) -> tuple[str, ...]:
    rows = list(
        db.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation_id)
            .order_by(ConversationTurn.created_at.desc(), ConversationTurn.id.desc())
            .limit(MAX_PRIOR_USER_QUESTIONS)
        )
    )
    return tuple(turn.user_message for turn in reversed(rows))


def _resolve_synthesis(db: Session, settings: Settings) -> TrustedModelRuntimeConfig:
    try:
        return TrustedRuntimeResolver(db, SecretCrypto.from_settings(settings)).resolve().synthesis
    except RuntimeConfigError as exc:
        raise ChatTurnError(409, "synthesis_profile_not_ready", "Synthesis profile is not ready.") from exc


def new_trace_id() -> str:
    return str(uuid.uuid4())


def _validate_domain_for_new_turn(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    retrieval_port: P6RetrievalPort | None = None,
) -> None:
    controller = retrieval_port._controller if retrieval_port is not None else None
    try:
        resolve_available_domain(db, settings=settings, domain_id=domain_id, controller=controller)
    except EvidenceRetrievalError as exc:
        raise ChatTurnError(exc.status_code, exc.code, exc.message) from exc


def start_or_replay_turn(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    auth_session: AuthSession,
    conversation_id: str,
    client_request_id: str,
    message: str,
    domain_id: str | None,
    composer_ref_tokens: list[str] | None = None,
    retrieval_port: P6RetrievalPort | None = None,
    request_id: str | None = None,
) -> TurnStartResult:
    conversation = get_owned_conversation(db, owner=owner, conversation_id=conversation_id)
    normalized_request_id = normalize_client_request_id(client_request_id)
    normalized_message = normalize_turn_message(message)
    normalized_domain_id = normalize_optional_domain_id(domain_id)
    route, effective_domain_id = classify_turn_route(message=normalized_message, domain_id=normalized_domain_id)
    _validate_effective_route(route=route, domain_id=effective_domain_id)
    try:
        normalized_ref_tokens = normalize_composer_ref_tokens(composer_ref_tokens)
        composer_ref_request_fingerprint = composer_ref_fingerprint(normalized_ref_tokens)
    except ComposerRefError as exc:
        raise ChatTurnError(exc.status_code, exc.code, exc.message) from exc

    existing = _matching_existing_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        user_message=normalized_message,
        domain_id=effective_domain_id,
        route=route,
        composer_ref_fingerprint=composer_ref_request_fingerprint,
    )
    if existing is not None:
        return _turn_start_replay(existing, request_id=request_id)

    if _running_turn(db, conversation.id) is not None:
        raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")

    if route == TURN_ROUTE_DOMAIN_RAG and effective_domain_id is not None:
        _validate_domain_for_new_turn(
            db,
            settings=settings,
            domain_id=effective_domain_id,
            retrieval_port=retrieval_port,
        )
    try:
        composer_validation = validate_composer_ref_tokens(
            db,
            settings=settings,
            owner=owner,
            conversation_id=conversation.id,
            domain_id=effective_domain_id,
            tokens=list(normalized_ref_tokens),
        )
    except ComposerRefError as exc:
        raise ChatTurnError(exc.status_code, exc.code, exc.message) from exc
    try:
        owner = revalidate_mutation_actor(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
        )
    except MutationAuthenticationError:
        raise ChatTurnError(401, "unauthenticated", "Authentication required.") from None
    conversation = _lock_conversation_for_turn_insert(
        db,
        owner=owner,
        conversation=conversation,
    )
    existing = _matching_existing_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        user_message=normalized_message,
        domain_id=effective_domain_id,
        route=route,
        composer_ref_fingerprint=composer_ref_request_fingerprint,
    )
    if existing is not None:
        return _turn_start_replay(existing, request_id=request_id)
    if _running_turn(db, conversation.id) is not None:
        raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")
    now = utc_now()
    turn = ConversationTurn(
        public_ref=generate_unique_public_ref(
            db,
            prefix="turn",
            column=ConversationTurn.public_ref,
        ),
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        domain_id=effective_domain_id,
        route=route,
        status=TURN_STATUS_RUNNING,
        user_message=normalized_message,
        composer_ref_fingerprint=composer_validation.fingerprint,
        trace_id=new_trace_id(),
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    conversation.updated_at = now
    conversation.version += 1
    db.add(turn)
    db.flush()
    if composer_validation.refs:
        persist_accepted_composer_refs(db, turn_id=turn.id, refs=composer_validation.refs)
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_ACCEPTED,
        payload={
            "conversationId": conversation.public_ref,
            "clientRequestId": turn.client_request_id,
            "replay": False,
        },
        commit=False,
    )
    domain = db.get(Domain, turn.domain_id) if turn.domain_id else None
    route_payload: dict[str, Any] = {"route": turn.route}
    if domain is not None:
        route_payload["domain"] = {"id": domain.id, "displayName": domain.display_name}
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_ROUTE_SELECTED,
        payload=route_payload,
        commit=False,
    )
    # Accepted refs and the accepted/route prefix are durable before a worker
    # can claim this turn.
    turn.claimable_at = now
    db.commit()
    db.refresh(turn)
    safe_log(
        logger,
        "chat.turn_claimed",
        request_id=request_id,
        trace_id=turn.trace_id,
        domain_id=turn.domain_id,
        conversation_turn_id=turn.id,
        client_request_id=turn.client_request_id,
        outcome="running",
        replay=False,
    )
    return TurnStartResult(
        turn=turn,
        replay=False,
        synthesis=None,
        prior_user_questions=(),
        request_id=request_id,
    )


def claim_turn(
    db: Session,
    *,
    owner: User,
    conversation_id: str,
    client_request_id: str,
    message: str,
    route: str,
    domain_id: str | None,
) -> TurnClaimResult:
    conversation = get_owned_conversation(db, owner=owner, conversation_id=conversation_id)
    normalized_request_id = normalize_client_request_id(client_request_id)
    normalized_message = normalize_turn_message(message)
    _validate_effective_route(route=route, domain_id=domain_id)

    existing = _matching_existing_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        user_message=normalized_message,
        domain_id=domain_id,
        route=route,
    )
    if existing is not None:
        return TurnClaimResult(turn=existing, replay=True)

    if _running_turn(db, conversation.id) is not None:
        raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")

    conversation = _lock_conversation_for_turn_insert(
        db,
        owner=owner,
        conversation=conversation,
    )
    existing = _matching_existing_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        user_message=normalized_message,
        domain_id=domain_id,
        route=route,
    )
    if existing is not None:
        return TurnClaimResult(turn=existing, replay=True)
    if _running_turn(db, conversation.id) is not None:
        raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")
    now = utc_now()
    turn = ConversationTurn(
        public_ref=generate_unique_public_ref(
            db,
            prefix="turn",
            column=ConversationTurn.public_ref,
        ),
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
        domain_id=domain_id,
        route=route,
        status=TURN_STATUS_RUNNING,
        user_message=normalized_message,
        trace_id=new_trace_id(),
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    conversation.updated_at = now
    conversation.version += 1
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return TurnClaimResult(turn=turn, replay=False)


def _optional_iso(value) -> str | None:
    if value is None:
        return None
    return iso_utc(value)


def _public_evidence_refs(turn: ConversationTurn) -> list[ConversationTurnEvidenceRef]:
    if turn.status == TURN_STATUS_REDACTED:
        return []
    return sorted(
        [ref for ref in turn.evidence_refs if ref.redacted_at is None],
        key=lambda ref: (ref.evidence_order, ref.id),
    )


def _public_composer_refs(turn: ConversationTurn) -> list[ConversationTurnComposerRef]:
    if turn.status == TURN_STATUS_REDACTED:
        return []
    return sorted(
        [ref for ref in turn.composer_refs if ref.redacted_at is None],
        key=lambda ref: (ref.ref_order, ref.id),
    )


def _public_assistant_answer(turn: ConversationTurn) -> str | None:
    if turn.status in {TURN_STATUS_RUNNING, TURN_STATUS_FAILED, TURN_STATUS_REDACTED}:
        return None
    if turn.stop_reason in {TURN_STOP_REASON_NO_GROUNDED_CONTEXT, TURN_STOP_REASON_EVIDENCE_ONLY}:
        return None
    return turn.assistant_answer


def safe_turn_summary(turn: ConversationTurn) -> dict[str, Any]:
    evidence_refs = _public_evidence_refs(turn)
    composer_refs = _public_composer_refs(turn)
    safe_error = None
    if turn.safe_error_code or turn.safe_error_message:
        safe_error = {
            "code": turn.safe_error_code,
            "message": turn.safe_error_message,
        }
    return {
        "id": turn.public_ref,
        "clientRequestId": turn.client_request_id,
        "domainId": turn.domain_id,
        "route": turn.route,
        "status": turn.status,
        "stopReason": turn.stop_reason,
        "userMessage": turn.user_message,
        "assistantAnswer": _public_assistant_answer(turn),
        "safeError": safe_error,
        "acceptedRefs": [
            {
                "id": ref.public_ref,
                "kind": ref.ref_kind,
                "order": ref.ref_order,
                "label": ref.safe_label,
                "description": ref.safe_description,
            }
            for ref in composer_refs
        ],
        "evidence": [
            {
                "id": ref.public_ref,
                "citationLabel": ref.citation_label,
                "sourceLabel": ref.source_label,
                "excerpt": ref.excerpt,
            }
            for ref in evidence_refs
        ],
        "citations": [
            {"evidenceRefId": ref.public_ref, "citationLabel": ref.citation_label}
            for ref in evidence_refs
            if ref.citation_label is not None
        ],
        "budget": {
            "planStepCount": turn.plan_step_count,
            "retrievalOperationCount": turn.retrieval_operation_count,
            "repairAttemptCount": turn.repair_attempt_count,
        },
        "createdAt": iso_utc(turn.created_at),
        "startedAt": _optional_iso(turn.started_at),
        "completedAt": _optional_iso(turn.completed_at),
        "updatedAt": iso_utc(turn.updated_at),
    }


def _turn_evidence_items(
    turn: ConversationTurn,
    *,
    sources: dict[str, SourceDocument],
    blocks: dict[str, SourceBlock],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ref in _public_evidence_refs(turn):
        source = sources.get(ref.source_document_id)
        block = blocks.get(ref.source_block_id)
        if (
            source is None
            or block is None
            or block.source_document_id != source.id
            or block.page_start is None
            or ref.citation_label is None
            or ref.source_label is None
            or ref.excerpt is None
        ):
            continue
        section_label = safe_section_label(block.section_path)
        items.append(
            {
                "id": ref.public_ref,
                "citationLabel": ref.citation_label,
                "sourceLabel": ref.source_label,
                "excerpt": ref.excerpt,
                "kind": block.kind,
                "documentRef": source.public_ref,
                "documentLabel": sanitize_original_filename(source.original_filename),
                "anchor": {
                    "pageNumber": block.page_start,
                    "region": None,
                    "sectionLabel": section_label,
                    "fallback": "section" if section_label else "page",
                },
            }
        )
    return items


def _turn_accepted_refs(turn: ConversationTurn) -> list[dict[str, Any]]:
    return [
        {
            "id": ref.public_ref,
            "kind": ref.ref_kind,
            "order": ref.ref_order,
            "label": ref.safe_label,
            "description": ref.safe_description,
        }
        for ref in _public_composer_refs(turn)
        if ref.safe_label is not None
    ]


def _turn_safe_error(turn: ConversationTurn) -> dict[str, Any] | None:
    if not turn.safe_error_code or not turn.safe_error_message:
        return None
    return {
        "code": turn.safe_error_code,
        "message": turn.safe_error_message,
        "retryable": False,
    }


def _turn_domain(
    turn: ConversationTurn,
    domains: dict[str, Domain],
    domain_eligibility: dict[str, bool],
) -> dict[str, Any] | None:
    domain = domains.get(turn.domain_id) if turn.domain_id else None
    if domain is None:
        return None
    return {
        "id": domain.id,
        "displayName": domain.display_name,
        "state": domain.state,
        "queryEligible": domain_eligibility.get(domain.id, False),
    }


def _project_turn_dto(
    turn: ConversationTurn,
    *,
    sources: dict[str, SourceDocument],
    blocks: dict[str, SourceBlock],
    domains: dict[str, Domain],
    domain_eligibility: dict[str, bool],
) -> dict[str, Any]:
    redacted = turn.status == TURN_STATUS_REDACTED
    return {
        "id": turn.public_ref,
        "clientRequestId": turn.client_request_id,
        "route": turn.route,
        "status": turn.status,
        "domain": _turn_domain(turn, domains, domain_eligibility),
        "userMessage": turn.user_message,
        "assistantAnswer": _public_assistant_answer(turn),
        "evidence": [] if redacted else _turn_evidence_items(turn, sources=sources, blocks=blocks),
        "acceptedRefs": [] if redacted else _turn_accepted_refs(turn),
        "error": None if redacted else _turn_safe_error(turn),
        "createdAt": iso_utc(turn.created_at),
        "completedAt": _optional_iso(turn.completed_at),
    }


def _turn_projection_lookups(
    db: Session,
    settings: Settings,
    turns: list[ConversationTurn],
) -> tuple[
    dict[str, SourceDocument],
    dict[str, SourceBlock],
    dict[str, Domain],
    dict[str, bool],
]:
    active_turns = [turn for turn in turns if turn.status != TURN_STATUS_REDACTED]
    source_ids = {
        ref.source_document_id
        for turn in active_turns
        for ref in _public_evidence_refs(turn)
    }
    block_ids = {
        ref.source_block_id
        for turn in active_turns
        for ref in _public_evidence_refs(turn)
    }
    domain_ids = {turn.domain_id for turn in turns if turn.domain_id is not None}
    source_rows = (
        db.scalars(
            select(SourceDocument)
            .options(
                load_only(
                    SourceDocument.id,
                    SourceDocument.public_ref,
                    SourceDocument.original_filename,
                )
            )
            .where(SourceDocument.id.in_(source_ids))
        )
        if source_ids
        else ()
    )
    block_rows = (
        db.scalars(
            select(SourceBlock)
            .options(
                load_only(
                    SourceBlock.id,
                    SourceBlock.kind,
                    SourceBlock.page_start,
                    SourceBlock.section_path,
                )
            )
            .where(SourceBlock.id.in_(block_ids))
        )
        if block_ids
        else ()
    )
    domain_rows = (
        db.scalars(
            select(Domain)
            .options(load_only(Domain.id, Domain.display_name, Domain.state))
            .where(Domain.id.in_(domain_ids))
        )
        if domain_ids
        else ()
    )
    domains = {row.id: row for row in domain_rows}
    controller = controller_from_settings(settings)
    return (
        {row.id: row for row in source_rows},
        {row.id: row for row in block_rows},
        domains,
        {domain_id: domain_available(db, domain, controller) for domain_id, domain in domains.items()},
    )


def safe_turn_dto(db: Session, settings: Settings, turn: ConversationTurn) -> dict[str, Any]:
    sources, blocks, domains, domain_eligibility = _turn_projection_lookups(db, settings, [turn])
    return _project_turn_dto(
        turn,
        sources=sources,
        blocks=blocks,
        domains=domains,
        domain_eligibility=domain_eligibility,
    )


def conversation_turn_summaries(
    db: Session,
    settings: Settings,
    conversation: Conversation,
) -> list[dict[str, Any]]:
    turns = list(
        db.scalars(
            select(ConversationTurn)
            .options(
                selectinload(ConversationTurn.evidence_refs),
                selectinload(ConversationTurn.composer_refs),
            )
            .where(ConversationTurn.conversation_id == conversation.id)
            .order_by(ConversationTurn.created_at, ConversationTurn.id)
        )
    )
    sources, blocks, domains, domain_eligibility = _turn_projection_lookups(db, settings, turns)
    return [
        _project_turn_dto(
            turn,
            sources=sources,
            blocks=blocks,
            domains=domains,
            domain_eligibility=domain_eligibility,
        )
        for turn in turns
    ]


def encode_sse_event(event: TurnStreamEvent) -> str:
    envelope = {
        "schemaVersion": TURN_EVENT_SCHEMA_VERSION,
        "eventId": event.event_id,
        "turnId": event.turn_id,
        "sequence": event.sequence,
        "type": event.event_type,
        "occurredAt": iso_utc(event.occurred_at),
        "payload": event.payload,
    }
    data = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data}\n\n"


def _event_from_row(row: ConversationTurnEvent, turn: ConversationTurn) -> TurnStreamEvent:
    payload = json.loads(row.payload_json)
    if (
        row.event_type == TURN_EVENT_ACCEPTED
        and payload.get("conversationId") == turn.conversation_id
    ):
        payload = {**payload, "conversationId": turn.conversation.public_ref}
    return TurnStreamEvent(
        event_id=row.id,
        turn_id=turn.public_ref,
        sequence=row.sequence,
        event_type=row.event_type,
        occurred_at=row.occurred_at,
        payload=payload,
    )


def _persist_event(
    db: Session,
    *,
    turn: ConversationTurn,
    event_type: str,
    payload: dict[str, Any],
    commit: bool = True,
    execution_generation: int | None = None,
) -> TurnStreamEvent:
    db.refresh(turn)
    if turn.status != TURN_STATUS_RUNNING and event_type not in {
        TURN_EVENT_COMPLETED,
        TURN_EVENT_FAILED,
        TURN_EVENT_CANCELLED,
        TURN_EVENT_REDACTED,
    }:
        raise RuntimeError("Cannot append an event to a terminal turn.")
    if execution_generation is not None and turn.execution_generation != execution_generation:
        raise RuntimeError("Turn execution lease was lost.")
    sequence = (
        db.scalar(
            select(func.coalesce(func.max(ConversationTurnEvent.sequence), 0)).where(
                ConversationTurnEvent.turn_id == turn.id
            )
        )
        or 0
    ) + 1
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    row = ConversationTurnEvent(
        id=f"evt_{uuid.uuid4().hex}",
        turn_id=turn.id,
        sequence=sequence,
        schema_version=TURN_EVENT_SCHEMA_VERSION,
        event_type=event_type,
        payload_json=payload_json,
        payload_digest=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        occurred_at=utc_now(),
    )
    db.add(row)
    db.flush()
    event = _event_from_row(row, turn)
    if commit:
        db.commit()
    return event


def _stored_events(db: Session, turn: ConversationTurn, *, after: int = 0) -> Iterator[TurnStreamEvent]:
    rows = db.scalars(
        select(ConversationTurnEvent)
        .where(
            ConversationTurnEvent.turn_id == turn.id,
            ConversationTurnEvent.sequence > after,
        )
        .order_by(ConversationTurnEvent.sequence)
    )
    for row in rows:
        yield _event_from_row(row, turn)


def _latest_event(db: Session, turn: ConversationTurn) -> TurnStreamEvent:
    row = db.scalar(
        select(ConversationTurnEvent)
        .where(ConversationTurnEvent.turn_id == turn.id)
        .order_by(ConversationTurnEvent.sequence.desc())
        .limit(1)
    )
    if row is None:
        raise RuntimeError("Turn terminal event was not persisted.")
    return _event_from_row(row, turn)


def _completed_payload(turn: ConversationTurn, *, replay: bool) -> dict[str, Any]:
    summary = safe_turn_summary(turn)
    return {
        "route": turn.route,
        "status": TURN_STATUS_COMPLETED,
        "stopReason": turn.stop_reason,
        "citations": summary["citations"],
        "acceptedRefs": summary["acceptedRefs"],
        "budget": summary["budget"],
        "replay": replay,
    }


def _public_evidence_items(db: Session, turn: ConversationTurn) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ref in _public_evidence_refs(turn):
        source = db.get(SourceDocument, ref.source_document_id)
        block = db.get(SourceBlock, ref.source_block_id)
        if source is None or block is None:
            continue
        anchor: dict[str, Any] = {
            "pageNumber": block.page_start or 1,
            "fallback": "section" if block.section_path else "page",
        }
        if block.section_path:
            anchor["sectionLabel"] = block.section_path[:160]
        items.append(
            {
                "id": ref.public_ref,
                "citationLabel": ref.citation_label,
                "sourceLabel": ref.source_label,
                "excerpt": ref.excerpt,
                "kind": block.kind,
                "documentRef": source.public_ref,
                "documentLabel": source.original_filename,
                "anchor": anchor,
            }
        )
    return items


def _public_evidence_event(
    db: Session,
    turn: ConversationTurn,
    *,
    execution_generation: int | None = None,
) -> TurnStreamEvent:
    return _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_EVIDENCE_DELTA,
        payload={"items": _public_evidence_items(db, turn)},
        execution_generation=execution_generation,
    )

def _public_evidence_refs_for_adapter(turn: ConversationTurn) -> tuple[PublicEvidenceRef, ...]:
    return tuple(
        PublicEvidenceRef(
            id=ref.public_ref,
            citation_label=ref.citation_label or "",
            source_label=ref.source_label or "",
            excerpt=ref.excerpt or "",
        )
        for ref in _public_evidence_refs(turn)
    )


def _lock_conversation_for_detail_change(
    db: Session,
    turn: ConversationTurn,
) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .where(Conversation.id == turn.conversation_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )


def _mark_conversation_changed(conversation: Conversation | None, now) -> None:
    if conversation is None:
        return
    conversation.updated_at = now
    conversation.version += 1


def _refresh_turn(db: Session, turn: ConversationTurn) -> ConversationTurn:
    db.refresh(turn)
    return turn


def _persist_evidence_refs(
    db: Session,
    *,
    turn: ConversationTurn,
    evidence: list[InternalMappedEvidence],
    execution_generation: int | None = None,
) -> ConversationTurn:
    db.refresh(turn)
    if turn.status != TURN_STATUS_RUNNING or (
        execution_generation is not None and turn.execution_generation != execution_generation
    ):
        return turn
    conversation = _lock_conversation_for_detail_change(db, turn)
    for index, item in enumerate(evidence, start=1):
        db.add(
            ConversationTurnEvidenceRef(
                turn_id=turn.id,
                evidence_order=index,
                source_document_id=item.source_document_id,
                source_block_id=item.source_block_id,
                citation_label=f"[{index}]",
                source_label=item.source_label,
                excerpt=item.excerpt,
            )
        )
    now = utc_now()
    turn.retrieval_operation_count = max(turn.retrieval_operation_count, 1)
    turn.updated_at = now
    _mark_conversation_changed(conversation, now)
    db.commit()
    return _refresh_turn(db, turn)


def _finalize_turn_if_running(
    db: Session,
    turn: ConversationTurn,
    values: dict[str, Any],
    execution_generation: int | None = None,
) -> bool:
    """Compare-and-set finalize: only a still-running turn may be finalized.

    A concurrent redaction (source/domain delete) may already have moved the turn
    to `redacted`; in that case the late stream result must not overwrite it.
    """
    conversation = _lock_conversation_for_detail_change(db, turn)
    result = db.execute(
        update(ConversationTurn)
        .where(
            ConversationTurn.id == turn.id,
            ConversationTurn.status == TURN_STATUS_RUNNING,
            *(
                [ConversationTurn.execution_generation == execution_generation]
                if execution_generation is not None
                else []
            ),
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        db.refresh(turn)
        return False
    _mark_conversation_changed(conversation, values["updated_at"])
    return True


def _complete_turn(
    db: Session,
    *,
    turn: ConversationTurn,
    stop_reason: str,
    assistant_answer: str | None,
    plan_step_count: int | None = None,
    retrieval_operation_count: int | None = None,
    repair_attempt_count: int | None = None,
    execution_generation: int | None = None,
) -> ConversationTurn:
    now = utc_now()
    values: dict[str, Any] = {
        "status": TURN_STATUS_COMPLETED,
        "stop_reason": stop_reason,
        "assistant_answer": assistant_answer,
        "safe_error_code": None,
        "safe_error_message": None,
        "completed_at": now,
        "updated_at": now,
    }
    if plan_step_count is not None:
        values["plan_step_count"] = plan_step_count
    if retrieval_operation_count is not None:
        values["retrieval_operation_count"] = retrieval_operation_count
    if repair_attempt_count is not None:
        values["repair_attempt_count"] = repair_attempt_count
    if not _finalize_turn_if_running(db, turn, values, execution_generation):
        return turn
    db.flush()
    db.refresh(turn)
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_COMPLETED,
        payload=_completed_payload(turn, replay=False),
        commit=False,
        execution_generation=execution_generation,
    )
    db.commit()
    turn = _refresh_turn(db, turn)
    safe_log(
        logger,
        "chat.turn_persisted",
        trace_id=turn.trace_id,
        domain_id=turn.domain_id,
        conversation_turn_id=turn.id,
        client_request_id=turn.client_request_id,
        outcome=turn.stop_reason,
        replay=False,
    )
    return turn


def _fail_turn(
    db: Session,
    *,
    turn: ConversationTurn,
    code: str,
    message: str,
    stop_reason: str,
    execution_generation: int | None = None,
) -> ConversationTurn:
    now = utc_now()
    values: dict[str, Any] = {
        "status": TURN_STATUS_FAILED,
        "stop_reason": stop_reason,
        "assistant_answer": None,
        "safe_error_code": code,
        "safe_error_message": message,
        "completed_at": now,
        "updated_at": now,
    }
    if not _finalize_turn_if_running(db, turn, values, execution_generation):
        return turn
    db.flush()
    db.refresh(turn)
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_FAILED,
        payload={"code": code, "message": message, "retryable": False, "replay": False},
        commit=False,
        execution_generation=execution_generation,
    )
    db.commit()
    turn = _refresh_turn(db, turn)
    safe_log(
        logger,
        "chat.turn_failed",
        trace_id=turn.trace_id,
        domain_id=turn.domain_id,
        conversation_turn_id=turn.id,
        client_request_id=turn.client_request_id,
        safe_error_code=code,
        outcome="failed",
    )
    return turn


def _record_turn_trace(
    settings: Settings,
    turn: ConversationTurn,
    *,
    request_id: str | None,
    mapped_evidence_count: int = 0,
    citation_count: int = 0,
) -> None:
    tracer_from_settings(settings).record_turn(
        TraceMetadata(
            {
                "trace_id": turn.trace_id,
                "request_id": request_id,
                "conversation_turn_id": turn.id,
                "domain_id": turn.domain_id,
                "route": turn.route,
                "stop_reason": turn.stop_reason,
                "plan_step_count": turn.plan_step_count,
                "retrieval_operation_count": turn.retrieval_operation_count,
                "repair_attempt_count": turn.repair_attempt_count,
                "mapped_evidence_count": mapped_evidence_count,
                "citation_count": citation_count,
            }
        )
    )


def _cancel_running_turn(db: Session, turn: ConversationTurn) -> None:
    current = db.get(ConversationTurn, turn.id)
    if current is None or current.status != TURN_STATUS_RUNNING:
        return
    now = utc_now()
    if not _finalize_turn_if_running(
        db,
        turn=current,
        values={
            "status": TURN_STATUS_CANCELLED,
            "stop_reason": TURN_STOP_REASON_CANCELLED,
            "assistant_answer": None,
            "safe_error_code": "turn_cancelled",
            "safe_error_message": SAFE_TURN_CANCELLED_MESSAGE,
            "completed_at": now,
            "updated_at": now,
        },
    ):
        return
    db.flush()
    db.refresh(current)
    _persist_event(
        db,
        turn=current,
        event_type=TURN_EVENT_CANCELLED,
        payload={"code": "turn_cancelled", "message": SAFE_TURN_CANCELLED_MESSAGE, "replay": False},
        commit=False,
    )
    db.commit()

def intent_for_operation(operation: str) -> str:
    try:
        return OPERATION_TO_INTENT[operation]
    except KeyError as exc:
        raise OrchestrationPolicyError("Retrieval operation is not allowed.") from exc


def operation_for_message(message: str) -> str:
    lowered = message.lower()
    if any(word in lowered for word in ("quote", "exact", "verbatim")):
        return "retrieve_verbatim"
    if any(word in lowered for word in ("summarize", "overview", "brief")):
        return "retrieve_overview"
    return "retrieve_fact"


class TurnOrchestrator:
    def __init__(
        self,
        *,
        synthesis_adapter: SynthesisStreamAdapter | RegistrySynthesisStreamAdapter | None = None,
        retrieval_port: P6RetrievalPort | None = None,
    ) -> None:
        self._synthesis_adapter = synthesis_adapter
        self._retrieval_port = retrieval_port or P6RetrievalPort()

    def _synthesis(self, settings: Settings) -> SynthesisStreamAdapter | RegistrySynthesisStreamAdapter:
        return self._synthesis_adapter or default_synthesis_stream_adapter(settings)

    def stream_turn(
        self,
        db: Session,
        *,
        settings: Settings,
        start: TurnStartResult,
    ) -> Iterator[TurnStreamEvent]:
        if start.replay:
            yield from _stored_events(db, start.turn)
            return
        yield from _stored_events(db, start.turn)
        if start.synthesis is None:
            raise ChatTurnError(409, "synthesis_profile_not_ready", "Synthesis profile is not ready.")
        if start.turn.route == TURN_ROUTE_DIRECT_LLM:
            yield from self._stream_direct(db, settings=settings, start=start)
            return
        yield from self._stream_domain_rag(db, settings=settings, start=start)

    def _stream_direct(self, db: Session, *, settings: Settings, start: TurnStartResult) -> Iterator[TurnStreamEvent]:
        turn = start.turn
        generation = start.execution_generation
        tokens: list[str] = []
        assert start.synthesis is not None
        try:
            kwargs: dict[str, Any] = {
                "synthesis": start.synthesis,
                "message": turn.user_message,
                "prior_user_questions": start.prior_user_questions,
            }
            if start.assembly_context is not None:
                kwargs["assembly_context"] = start.assembly_context
            for token in self._synthesis(settings).stream_direct(**kwargs):
                if token:
                    tokens.append(token)
                    yield _persist_event(
                        db,
                        turn=turn,
                        event_type=TURN_EVENT_ANSWER_DELTA,
                        payload={"text": token},
                        execution_generation=generation,
                    )
        except (SynthesisAdapterError, SynthesisProviderError, Exception):
            turn = _fail_turn(
                db,
                turn=turn,
                code="provider_failure",
                message=SAFE_PROVIDER_FAILURE_MESSAGE,
                stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                execution_generation=generation,
            )
            _record_turn_trace(settings, turn, request_id=start.request_id)
            yield _latest_event(db, turn)
            return
        answer = "".join(tokens).strip()
        if not answer:
            turn = _fail_turn(
                db,
                turn=turn,
                code="provider_failure",
                message=SAFE_PROVIDER_FAILURE_MESSAGE,
                stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                execution_generation=generation,
            )
            _record_turn_trace(settings, turn, request_id=start.request_id)
            yield _latest_event(db, turn)
            return
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer=answer,
            plan_step_count=0,
            retrieval_operation_count=0,
            repair_attempt_count=0,
            execution_generation=generation,
        )
        _record_turn_trace(settings, turn, request_id=start.request_id)
        yield _latest_event(db, turn)

    def _stream_domain_rag(
        self,
        db: Session,
        *,
        settings: Settings,
        start: TurnStartResult,
    ) -> Iterator[TurnStreamEvent]:
        turn = start.turn
        generation = start.execution_generation
        operation = operation_for_message(turn.user_message)
        intent = intent_for_operation(operation)
        yield _persist_event(
            db,
            turn=turn,
            event_type=TURN_EVENT_RETRIEVAL_STARTED,
            payload={"attempt": 1, "maxAttempts": 1},
            execution_generation=generation,
        )
        try:
            evidence = self._retrieval_port.retrieve(
                db,
                settings=settings,
                domain_id=turn.domain_id or "",
                question=turn.user_message,
                intent=intent,
            )
        except ChatTurnError as exc:
            turn = _fail_turn(
                db,
                turn=turn,
                code=exc.code,
                message=exc.message,
                stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                execution_generation=generation,
            )
            _record_turn_trace(settings, turn, request_id=start.request_id)
            yield _latest_event(db, turn)
            return
        if not evidence:
            yield _persist_event(
                db,
                turn=turn,
                event_type=TURN_EVENT_RETRIEVAL_COMPLETED,
                payload={"result": "no_grounded_context", "evidenceCount": 0},
                execution_generation=generation,
            )
            turn = _complete_turn(
                db,
                turn=turn,
                stop_reason=TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
                assistant_answer=None,
                plan_step_count=1,
                retrieval_operation_count=1,
                repair_attempt_count=0,
                execution_generation=generation,
            )
            _record_turn_trace(settings, turn, request_id=start.request_id)
            yield _latest_event(db, turn)
            return
        turn = _persist_evidence_refs(db, turn=turn, evidence=evidence, execution_generation=generation)
        yield _public_evidence_event(db, turn, execution_generation=generation)
        yield _persist_event(
            db,
            turn=turn,
            event_type=TURN_EVENT_RETRIEVAL_COMPLETED,
            payload={"result": "evidence_found", "evidenceCount": len(_public_evidence_refs(turn))},
            execution_generation=generation,
        )
        public_evidence = _public_evidence_refs_for_adapter(turn)
        tokens: list[str] = []
        answer_delta_persisted = False
        assert start.synthesis is not None
        try:
            kwargs: dict[str, Any] = {
                "synthesis": start.synthesis,
                "message": turn.user_message,
                "evidence": public_evidence,
                "prior_user_questions": start.prior_user_questions,
            }
            if start.assembly_context is not None:
                kwargs["assembly_context"] = start.assembly_context
            # Provider I/O runs after Evidence persistence commits; each answer
            # delta commits independently so we never hold a product write txn
            # across unbounded synthesis streaming (KTD7).
            for token in self._synthesis(settings).stream_grounded(**kwargs):
                if token:
                    tokens.append(token)
                    yield _persist_event(
                        db,
                        turn=turn,
                        event_type=TURN_EVENT_ANSWER_DELTA,
                        payload={"text": token},
                        execution_generation=generation,
                    )
                    answer_delta_persisted = True
        except (SynthesisAdapterError, SynthesisProviderError, Exception):
            if answer_delta_persisted:
                turn = _fail_turn(
                    db,
                    turn=turn,
                    code="provider_failure",
                    message=SAFE_PROVIDER_FAILURE_MESSAGE,
                    stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                    execution_generation=generation,
                )
            else:
                turn = _complete_turn(
                    db,
                    turn=turn,
                    stop_reason=TURN_STOP_REASON_EVIDENCE_ONLY,
                    assistant_answer=None,
                    plan_step_count=1,
                    retrieval_operation_count=1,
                    repair_attempt_count=0,
                    execution_generation=generation,
                )
            _record_turn_trace(
                settings,
                turn,
                request_id=start.request_id,
                mapped_evidence_count=len(evidence),
                citation_count=len(_public_evidence_refs(turn)),
            )
            yield _latest_event(db, turn)
            return
        answer = "".join(tokens).strip()
        if not answer:
            if answer_delta_persisted:
                turn = _fail_turn(
                    db,
                    turn=turn,
                    code="provider_failure",
                    message=SAFE_PROVIDER_FAILURE_MESSAGE,
                    stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                    execution_generation=generation,
                )
            else:
                turn = _complete_turn(
                    db,
                    turn=turn,
                    stop_reason=TURN_STOP_REASON_EVIDENCE_ONLY,
                    assistant_answer=None,
                    plan_step_count=1,
                    retrieval_operation_count=1,
                    repair_attempt_count=0,
                    execution_generation=generation,
                )
            _record_turn_trace(
                settings,
                turn,
                request_id=start.request_id,
                mapped_evidence_count=len(evidence),
                citation_count=len(_public_evidence_refs(turn)),
            )
            yield _latest_event(db, turn)
            return
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_GROUNDED,
            assistant_answer=answer,
            plan_step_count=1,
            retrieval_operation_count=1,
            repair_attempt_count=0,
            execution_generation=generation,
        )
        _record_turn_trace(
            settings,
            turn,
            request_id=start.request_id,
            mapped_evidence_count=len(evidence),
            citation_count=len(_public_evidence_refs(turn)),
        )
        yield _latest_event(db, turn)


def _accepted_refs_for_worker(turn: ConversationTurn) -> tuple[ValidatedComposerRef, ...]:
    return tuple(
        ValidatedComposerRef(
            order=ref.ref_order,
            kind=ref.ref_kind,
            label=ref.safe_label,
            description=ref.safe_description,
            domain_id=ref.domain_id,
            source_document_id=ref.source_document_id,
            source_block_id=ref.source_block_id,
            evidence_ref_id=ref.evidence_ref_id,
            prompt_template_id=ref.prompt_template_id,
        )
        for ref in sorted(turn.composer_refs, key=lambda ref: (ref.ref_order, ref.id))
        if ref.redacted_at is None
    )


def _has_answer_delta(db: Session, turn: ConversationTurn) -> bool:
    return (
        db.scalar(
            select(ConversationTurnEvent.id)
            .where(
                ConversationTurnEvent.turn_id == turn.id,
                ConversationTurnEvent.event_type == TURN_EVENT_ANSWER_DELTA,
            )
            .limit(1)
        )
        is not None
    )


class ConversationTurnWorker:
    """Claims accepted turns and owns all retrieval/synthesis execution."""

    def __init__(
        self,
        settings: Settings,
        *,
        synthesis_adapter: SynthesisStreamAdapter | RegistrySynthesisStreamAdapter | None = None,
        retrieval_port: P6RetrievalPort | None = None,
    ) -> None:
        self._settings = settings
        self._synthesis_adapter = synthesis_adapter
        self._retrieval_port = retrieval_port

    def run_once(self, db: Session) -> bool:
        turn = self._claim_next_turn(db)
        if turn is None:
            return False
        generation = turn.execution_generation
        if _has_answer_delta(db, turn):
            _fail_turn(
                db,
                turn=turn,
                code="provider_failure",
                message=SAFE_PROVIDER_FAILURE_MESSAGE,
                stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                execution_generation=generation,
            )
            return True
        try:
            synthesis = _resolve_synthesis(db, self._settings)
            assembly = PromptAssemblyService(db).assemble(_accepted_refs_for_worker(turn))
            start = TurnStartResult(
                turn=turn,
                replay=False,
                synthesis=synthesis,
                prior_user_questions=_prior_user_questions(db, turn.conversation_id),
                assembly_context=None if assembly.is_empty else assembly,
                execution_generation=generation,
            )
            # Event persistence is the worker's durable side effect. The
            # iterator is intentionally exhausted here, never by HTTP.
            list(
                TurnOrchestrator(
                    synthesis_adapter=self._synthesis_adapter,
                    retrieval_port=self._retrieval_port,
                ).stream_turn(db, settings=self._settings, start=start)
            )
        except ChatTurnError as exc:
            _fail_turn(
                db,
                turn=turn,
                code=exc.code,
                message=exc.message,
                stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                execution_generation=generation,
            )
        except RuntimeError:
            # A lease/status fence intentionally rejects stale execution.
            db.rollback()
        return True

    def _claim_next_turn(self, db: Session) -> ConversationTurn | None:
        now = utc_now()
        lease_expired = ConversationTurn.lease_expires_at.is_not(None) & (
            ConversationTurn.lease_expires_at < now
        )
        turn = db.scalar(
            select(ConversationTurn)
            .options(selectinload(ConversationTurn.composer_refs))
            .where(
                ConversationTurn.status == TURN_STATUS_RUNNING,
                ConversationTurn.claimable_at.is_not(None),
                ConversationTurn.claimable_at <= now,
                or_(ConversationTurn.lease_expires_at.is_(None), lease_expired),
            )
            .order_by(ConversationTurn.claimable_at, ConversationTurn.created_at, ConversationTurn.id)
            .with_for_update(skip_locked=True)
        )
        if turn is None:
            return None
        turn.lease_owner = self._settings.turn_worker_id
        turn.lease_expires_at = now + timedelta(seconds=self._settings.turn_lease_seconds)
        turn.execution_generation += 1
        turn.updated_at = now
        db.commit()
        db.refresh(turn)
        return turn


def run_turn_workers_until_idle(
    db: Session,
    settings: Settings,
    *,
    synthesis_adapter: SynthesisStreamAdapter | RegistrySynthesisStreamAdapter | None = None,
    retrieval_port: P6RetrievalPort | None = None,
) -> None:
    """Deterministic test helper; production workers use ``run_once``."""
    worker = ConversationTurnWorker(
        settings,
        synthesis_adapter=synthesis_adapter,
        retrieval_port=retrieval_port,
    )
    while worker.run_once(db):
        pass


def _tail_turn_events(
    db: Session,
    turn: ConversationTurn,
    *,
    after: int = 0,
    settings: Settings,
) -> Iterator[TurnStreamEvent]:
    cursor = after
    # Tests already run the worker to completion before tailing; keep the idle
    # bound short so suites do not wait on production reconnect windows.
    idle_seconds = 0.5 if settings.testing else float(settings.turn_tail_idle_seconds)
    poll_seconds = 0.01 if settings.testing else settings.turn_tail_poll_milliseconds / 1000
    idle_deadline = time.monotonic() + idle_seconds
    while True:
        db.expire_all()
        current = db.get(ConversationTurn, turn.id)
        if current is None:
            return
        rows = list(_stored_events(db, current, after=cursor))
        for event in rows:
            cursor = event.sequence
            yield event
        if current.status != TURN_STATUS_RUNNING:
            return
        if time.monotonic() >= idle_deadline:
            return
        time.sleep(poll_seconds)


def stream_turn_events(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    auth_session: AuthSession,
    conversation_id: str,
    client_request_id: str,
    message: str,
    domain_id: str | None,
    composer_ref_tokens: list[str] | None = None,
    request_id: str | None = None,
    synthesis_adapter: SynthesisStreamAdapter | None = None,
    retrieval_port: P6RetrievalPort | None = None,
) -> Iterator[TurnStreamEvent]:
    start = start_or_replay_turn(
        db,
        settings=settings,
        owner=owner,
        auth_session=auth_session,
        conversation_id=conversation_id,
        client_request_id=client_request_id,
        message=message,
        domain_id=domain_id,
        composer_ref_tokens=composer_ref_tokens,
        retrieval_port=retrieval_port,
        request_id=request_id,
    )
    if settings.testing:
        run_turn_workers_until_idle(
            db,
            settings,
            synthesis_adapter=synthesis_adapter,
            retrieval_port=retrieval_port,
        )
    yield from _tail_turn_events(db, start.turn, settings=settings)


def stream_turn_events_by_turn(
    db: Session,
    *,
    owner: User,
    conversation_id: str,
    turn_id: str,
    after: int = 0,
    settings: Settings | None = None,
) -> Iterator[TurnStreamEvent]:
    if after < 0:
        raise _validation_error()
    turn = get_owned_turn(db, owner=owner, conversation_id=conversation_id, turn_id=turn_id)
    if settings is None:
        return _stored_events(db, turn, after=after)
    return _tail_turn_events(db, turn, after=after, settings=settings)



def cancel_turn(
    db: Session,
    *,
    settings: Settings,
    owner: User,
    auth_session: AuthSession,
    conversation_id: str,
    turn_id: str,
) -> ConversationTurn:
    try:
        owner = revalidate_mutation_actor(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
        )
    except MutationAuthenticationError:
        raise ChatTurnError(401, "unauthenticated", "Authentication required.") from None
    turn = get_owned_turn(db, owner=owner, conversation_id=conversation_id, turn_id=turn_id)
    _cancel_running_turn(db, turn=turn)
    return _refresh_turn(db, turn)


def _sanitize_turn_events_for_redaction(db: Session, turn: ConversationTurn) -> None:
    rows = db.scalars(
        select(ConversationTurnEvent)
        .where(ConversationTurnEvent.turn_id == turn.id)
        .order_by(ConversationTurnEvent.sequence)
    )
    for row in rows:
        payload = json.loads(row.payload_json)
        if row.event_type == TURN_EVENT_ANSWER_DELTA:
            payload = {"text": ""}
        elif row.event_type == TURN_EVENT_EVIDENCE_DELTA:
            payload = {"items": []}
        elif row.event_type == TURN_EVENT_COMPLETED:
            payload["citations"] = []
            payload["acceptedRefs"] = []
        else:
            continue
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        row.payload_json = payload_json
        row.payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _redact_turns(
    db: Session,
    turns: list[ConversationTurn],
    audit_context: AuditContext | None = None,
    *,
    commit: bool = True,
) -> int:
    now = utc_now()
    changed = 0
    for turn in turns:
        if turn.status == TURN_STATUS_REDACTED:
            continue
        conversation = _lock_conversation_for_detail_change(db, turn)
        turn.status = TURN_STATUS_REDACTED
        turn.stop_reason = TURN_STOP_REASON_REDACTED
        turn.assistant_answer = None
        turn.safe_error_code = None
        turn.safe_error_message = None
        turn.completed_at = turn.completed_at or now
        turn.updated_at = now
        _mark_conversation_changed(conversation, now)
        for ref in turn.evidence_refs:
            ref.redacted_at = ref.redacted_at or now
            ref.citation_label = None
            ref.source_label = None
            ref.excerpt = None
        for ref in turn.composer_refs:
            ref.redacted_at = ref.redacted_at or now
            ref.safe_label = None
            ref.safe_description = None
        AuditService(db).record(
            AUDIT_EVENT_CHAT_TURN_REDACTED,
            context=audit_context,
            target_kind="conversation_turn",
            target_id=turn.public_ref,
            trace_id=turn.trace_id,
            metadata={"turnStatus": TURN_STATUS_REDACTED, "stopReason": TURN_STOP_REASON_REDACTED},
        )
        _sanitize_turn_events_for_redaction(db, turn)
        _persist_event(
            db,
            turn=turn,
            event_type=TURN_EVENT_REDACTED,
            payload={
                "code": "turn_redacted",
                "message": "This turn was redacted.",
                "redactedAt": iso_utc(now),
            },
            commit=False,
        )
        changed += 1
    if changed and commit:
        db.commit()
    return changed


def redact_turns_for_source(
    db: Session,
    source_document_id: str,
    audit_context: AuditContext | None = None,
    *,
    commit: bool = True,
) -> int:
    turns_by_id = {
        turn.id: turn
        for turn in db.scalars(
            select(ConversationTurn)
            .join(ConversationTurnEvidenceRef)
            .where(ConversationTurnEvidenceRef.source_document_id == source_document_id)
            .order_by(ConversationTurn.created_at, ConversationTurn.id)
        ).unique()
    }
    for turn in db.scalars(
        select(ConversationTurn)
        .join(ConversationTurnComposerRef)
        .where(ConversationTurnComposerRef.source_document_id == source_document_id)
        .order_by(ConversationTurn.created_at, ConversationTurn.id)
    ).unique():
        turns_by_id[turn.id] = turn
    return _redact_turns(db, list(turns_by_id.values()), audit_context, commit=commit)


def redact_turns_for_domain(db: Session, domain_id: str, audit_context: AuditContext | None = None) -> int:
    turns = list(
        db.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.domain_id == domain_id,
                ConversationTurn.route == TURN_ROUTE_DOMAIN_RAG,
            )
            .order_by(ConversationTurn.created_at, ConversationTurn.id)
        )
    )
    return _redact_turns(db, turns, audit_context)
