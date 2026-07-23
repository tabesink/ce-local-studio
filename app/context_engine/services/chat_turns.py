from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_CHAT_TURN_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    ConversationTurnEvidenceRef,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_ROUTES,
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
    User,
)
from context_engine.services.audit import AuditContext, AuditService
from context_engine.services.auth import iso_utc
from context_engine.services.chat_intent import requires_domain
from context_engine.services.composer_refs import (
    ComposerRefError,
    composer_ref_fingerprint,
    normalize_composer_ref_tokens,
    persist_accepted_composer_refs,
    validate_composer_ref_tokens,
)
from context_engine.services.conversations import get_owned_conversation
from context_engine.services.evidence import (
    EvidenceRetrievalError,
    InternalMappedEvidence,
    RetrievalClient,
    eligible_sources_for_domain,
    map_retrieval_hits_to_internal_evidence,
    resolve_available_domain,
)
from context_engine.services.indexing import SourceIndexError, index_client_from_settings
from context_engine.services.prompt_assembly import PromptAssemblyContext, PromptAssemblyService
from context_engine.services.runtime_config import (
    RuntimeConfigError,
    SecretCrypto,
    TrustedModelRuntimeConfig,
    TrustedRuntimeResolver,
)
from context_engine.services.structured_logging import safe_log
from context_engine.services.tracing import TraceMetadata, tracer_from_settings

logger = logging.getLogger(__name__)

CLIENT_REQUEST_ID_MIN_CHARS = 8
CLIENT_REQUEST_ID_MAX_CHARS = 80
TURN_MESSAGE_MAX_CHARS = 4000
MAX_PRIOR_USER_QUESTIONS = 4
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


@dataclass(frozen=True)
class TurnStreamEvent:
    event: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PublicEvidenceRef:
    id: str
    citation_label: str
    source_label: str
    excerpt: str


class SynthesisProviderError(Exception):
    pass


class OrchestrationPolicyError(Exception):
    pass


class SynthesisStreamAdapter:
    def stream_direct(
        self,
        *,
        synthesis: TrustedModelRuntimeConfig,
        message: str,
        prior_user_questions: tuple[str, ...],
        assembly_context: PromptAssemblyContext | None = None,
    ) -> Iterable[str]:
        return ("I can help with that.",)

    def stream_grounded(
        self,
        *,
        synthesis: TrustedModelRuntimeConfig,
        message: str,
        evidence: tuple[PublicEvidenceRef, ...],
        prior_user_questions: tuple[str, ...],
        assembly_context: PromptAssemblyContext | None = None,
    ) -> Iterable[str]:
        return ("The answer is supported by the current evidence.",)


class P6RetrievalPort:
    def __init__(
        self,
        *,
        client: RetrievalClient | None = None,
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
            domain, controller = resolve_available_domain(
                db,
                settings=settings,
                domain_id=domain_id,
                controller=self._controller,
            )
            if not eligible_sources_for_domain(db, settings=settings, domain=domain, controller=controller):
                return []
            db.commit()
            client = self._client or index_client_from_settings(settings, controller)
            hits = client.retrieve(domain, question=question)
        except SourceIndexError as exc:
            raise ChatTurnError(502, "domain_runtime_unavailable", "Knowledge domain runtime is unavailable.") from exc
        except EvidenceRetrievalError as exc:
            raise ChatTurnError(exc.status_code, exc.code, exc.message) from exc
        return map_retrieval_hits_to_internal_evidence(
            db,
            settings=settings,
            domain=domain,
            hits=hits,
            controller=controller,
        )


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
    if not domain_id or len(domain_id) > 64:
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


def _existing_request_turn(db: Session, *, conversation_id: str, client_request_id: str) -> ConversationTurn | None:
    return db.scalar(
        select(ConversationTurn).where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.client_request_id == client_request_id,
        )
    )


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

    existing = _existing_request_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
    )
    if existing is not None:
        if (
            existing.user_message != normalized_message
            or existing.domain_id != effective_domain_id
            or existing.route != route
            or existing.composer_ref_fingerprint != composer_ref_request_fingerprint
        ):
            raise ChatTurnError(409, "client_request_conflict", "Client request conflicts with an existing turn.")
        if existing.status == TURN_STATUS_RUNNING:
            raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")
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
        return TurnStartResult(turn=existing, replay=True, synthesis=None, prior_user_questions=(), request_id=request_id)

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
    assembly_context = PromptAssemblyService(db).assemble(composer_validation.refs)
    synthesis = _resolve_synthesis(db, settings)
    prior_questions = _prior_user_questions(db, conversation.id)

    now = utc_now()
    turn = ConversationTurn(
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
    db.add(turn)
    db.commit()
    db.refresh(turn)
    if composer_validation.refs:
        persist_accepted_composer_refs(db, turn_id=turn.id, refs=composer_validation.refs)
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
        synthesis=synthesis,
        prior_user_questions=prior_questions,
        request_id=request_id,
        assembly_context=None if assembly_context.is_empty else assembly_context,
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

    existing = _existing_request_turn(
        db,
        conversation_id=conversation.id,
        client_request_id=normalized_request_id,
    )
    if existing is not None:
        if existing.user_message != normalized_message or existing.domain_id != domain_id or existing.route != route:
            raise ChatTurnError(409, "client_request_conflict", "Client request conflicts with an existing turn.")
        if existing.status == TURN_STATUS_RUNNING:
            raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")
        return TurnClaimResult(turn=existing, replay=True)

    if _running_turn(db, conversation.id) is not None:
        raise ChatTurnError(409, "conversation_turn_in_progress", "A conversation turn is already running.")

    now = utc_now()
    turn = ConversationTurn(
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
        "id": turn.id,
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
                "id": ref.id,
                "kind": ref.ref_kind,
                "order": ref.ref_order,
                "label": ref.safe_label,
                "description": ref.safe_description,
            }
            for ref in composer_refs
        ],
        "evidence": [
            {
                "id": ref.id,
                "citationLabel": ref.citation_label,
                "sourceLabel": ref.source_label,
                "excerpt": ref.excerpt,
            }
            for ref in evidence_refs
        ],
        "citations": [
            {"evidenceRefId": ref.id, "citationLabel": ref.citation_label}
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


def conversation_turn_summaries(db: Session, conversation: Conversation) -> list[dict[str, Any]]:
    turns = db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.conversation_id == conversation.id)
        .order_by(ConversationTurn.created_at, ConversationTurn.id)
    )
    return [safe_turn_summary(turn) for turn in turns]


def encode_sse_event(event: TurnStreamEvent) -> str:
    data = json.dumps(event.payload, separators=(",", ":"), sort_keys=True)
    return f"event: {event.event}\ndata: {data}\n\n"


def _stage(turn: ConversationTurn, stage: str) -> TurnStreamEvent:
    return TurnStreamEvent("stage", {"turnId": turn.id, "stage": stage})


def _token(turn: ConversationTurn, text: str) -> TurnStreamEvent:
    return TurnStreamEvent("token", {"turnId": turn.id, "text": text})


def _error(turn: ConversationTurn, *, code: str, message: str, replay: bool) -> TurnStreamEvent:
    return TurnStreamEvent("error", {"turnId": turn.id, "code": code, "message": message, "replay": replay})


def _done(turn: ConversationTurn, *, replay: bool) -> TurnStreamEvent:
    summary = safe_turn_summary(turn)
    return TurnStreamEvent(
        "done",
        {
            "turnId": turn.id,
            "route": turn.route,
            "status": turn.status,
            "stopReason": turn.stop_reason,
            "citations": summary["citations"],
            "acceptedRefs": summary["acceptedRefs"],
            "budget": summary["budget"],
            "replay": replay,
        },
    )


def _public_evidence_event(turn: ConversationTurn) -> TurnStreamEvent:
    return TurnStreamEvent("evidence", {"turnId": turn.id, "evidence": safe_turn_summary(turn)["evidence"]})


def _public_evidence_refs_for_adapter(turn: ConversationTurn) -> tuple[PublicEvidenceRef, ...]:
    return tuple(
        PublicEvidenceRef(
            id=ref.id,
            citation_label=ref.citation_label or "",
            source_label=ref.source_label or "",
            excerpt=ref.excerpt or "",
        )
        for ref in _public_evidence_refs(turn)
    )


def _set_conversation_updated(db: Session, turn: ConversationTurn, now) -> None:
    conversation = db.get(Conversation, turn.conversation_id)
    if conversation is not None:
        conversation.updated_at = now


def _refresh_turn(db: Session, turn: ConversationTurn) -> ConversationTurn:
    db.refresh(turn)
    return turn


def _persist_evidence_refs(
    db: Session,
    *,
    turn: ConversationTurn,
    evidence: list[InternalMappedEvidence],
) -> ConversationTurn:
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
    _set_conversation_updated(db, turn, now)
    db.commit()
    return _refresh_turn(db, turn)


def _finalize_turn_if_running(db: Session, turn: ConversationTurn, values: dict[str, Any]) -> bool:
    """Compare-and-set finalize: only a still-running turn may be finalized.

    A concurrent redaction (source/domain delete) may already have moved the turn
    to `redacted`; in that case the late stream result must not overwrite it.
    """
    result = db.execute(
        update(ConversationTurn)
        .where(ConversationTurn.id == turn.id, ConversationTurn.status == TURN_STATUS_RUNNING)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        db.refresh(turn)
        return False
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
    if not _finalize_turn_if_running(db, turn, values):
        return turn
    _set_conversation_updated(db, turn, now)
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


def _fail_turn(db: Session, *, turn: ConversationTurn, code: str, message: str, stop_reason: str) -> ConversationTurn:
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
    if not _finalize_turn_if_running(db, turn, values):
        return turn
    _set_conversation_updated(db, turn, now)
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
    _fail_turn(
        db,
        turn=current,
        code="turn_cancelled",
        message=SAFE_TURN_CANCELLED_MESSAGE,
        stop_reason=TURN_STOP_REASON_CANCELLED,
    )


def _replay_events(turn: ConversationTurn) -> Iterator[TurnStreamEvent]:
    summary = safe_turn_summary(turn)
    if turn.status == TURN_STATUS_FAILED:
        safe_error = summary["safeError"] or {
            "code": "provider_failure",
            "message": SAFE_PROVIDER_FAILURE_MESSAGE,
        }
        yield _error(turn, code=safe_error["code"], message=safe_error["message"], replay=True)
        return
    if summary["evidence"]:
        yield _public_evidence_event(turn)
    if summary["assistantAnswer"]:
        yield _token(turn, summary["assistantAnswer"])
    yield _done(turn, replay=True)


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
        synthesis_adapter: SynthesisStreamAdapter | None = None,
        retrieval_port: P6RetrievalPort | None = None,
    ) -> None:
        self._synthesis_adapter = synthesis_adapter or SynthesisStreamAdapter()
        self._retrieval_port = retrieval_port or P6RetrievalPort()

    def stream_turn(
        self,
        db: Session,
        *,
        settings: Settings,
        start: TurnStartResult,
    ) -> Iterator[TurnStreamEvent]:
        if start.replay:
            yield from _replay_events(start.turn)
            return
        if start.synthesis is None:
            raise ChatTurnError(409, "synthesis_profile_not_ready", "Synthesis profile is not ready.")
        if start.turn.route == TURN_ROUTE_DIRECT_LLM:
            yield from self._stream_direct(db, settings=settings, start=start)
            return
        yield from self._stream_domain_rag(db, settings=settings, start=start)

    def _stream_direct(self, db: Session, *, settings: Settings, start: TurnStartResult) -> Iterator[TurnStreamEvent]:
        turn = start.turn
        completed = False
        try:
            yield _stage(turn, "direct_answering")
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
                for token in self._synthesis_adapter.stream_direct(**kwargs):
                    if token:
                        tokens.append(token)
                        yield _token(turn, token)
            except SynthesisProviderError:
                turn = _fail_turn(
                    db,
                    turn=turn,
                    code="provider_failure",
                    message=SAFE_PROVIDER_FAILURE_MESSAGE,
                    stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                )
                completed = True
                _record_turn_trace(settings, turn, request_id=start.request_id)
                yield _error(turn, code="provider_failure", message=SAFE_PROVIDER_FAILURE_MESSAGE, replay=False)
                return
            answer = "".join(tokens).strip()
            if not answer:
                turn = _fail_turn(
                    db,
                    turn=turn,
                    code="provider_failure",
                    message=SAFE_PROVIDER_FAILURE_MESSAGE,
                    stop_reason=TURN_STOP_REASON_PROVIDER_FAILURE,
                )
                completed = True
                _record_turn_trace(settings, turn, request_id=start.request_id)
                yield _error(turn, code="provider_failure", message=SAFE_PROVIDER_FAILURE_MESSAGE, replay=False)
                return
            turn = _complete_turn(
                db,
                turn=turn,
                stop_reason=TURN_STOP_REASON_DIRECT_LLM,
                assistant_answer=answer,
                plan_step_count=0,
                retrieval_operation_count=0,
                repair_attempt_count=0,
            )
            completed = True
            _record_turn_trace(settings, turn, request_id=start.request_id)
            yield _done(turn, replay=False)
        finally:
            if not completed:
                _cancel_running_turn(db, turn)

    def _stream_domain_rag(
        self,
        db: Session,
        *,
        settings: Settings,
        start: TurnStartResult,
    ) -> Iterator[TurnStreamEvent]:
        turn = start.turn
        completed = False
        try:
            yield _stage(turn, "planning")
            operation = operation_for_message(turn.user_message)
            intent = intent_for_operation(operation)
            yield _stage(turn, "retrieving")
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
                )
                completed = True
                _record_turn_trace(settings, turn, request_id=start.request_id)
                yield _error(turn, code=exc.code, message=exc.message, replay=False)
                return
            if not evidence:
                turn = _complete_turn(
                    db,
                    turn=turn,
                    stop_reason=TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
                    assistant_answer=None,
                    plan_step_count=1,
                    retrieval_operation_count=1,
                    repair_attempt_count=0,
                )
                completed = True
                _record_turn_trace(settings, turn, request_id=start.request_id)
                yield _public_evidence_event(turn)
                yield _done(turn, replay=False)
                return
            turn = _persist_evidence_refs(db, turn=turn, evidence=evidence)
            yield _stage(turn, "verifying")
            yield _public_evidence_event(turn)
            yield _stage(turn, "answering")
            public_evidence = _public_evidence_refs_for_adapter(turn)
            tokens: list[str] = []
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
                for token in self._synthesis_adapter.stream_grounded(**kwargs):
                    if token:
                        tokens.append(token)
                        yield _token(turn, token)
            except SynthesisProviderError:
                turn = _complete_turn(
                    db,
                    turn=turn,
                    stop_reason=TURN_STOP_REASON_EVIDENCE_ONLY,
                    assistant_answer=None,
                    plan_step_count=1,
                    retrieval_operation_count=1,
                    repair_attempt_count=0,
                )
                completed = True
                _record_turn_trace(
                    settings,
                    turn,
                    request_id=start.request_id,
                    mapped_evidence_count=len(evidence),
                    citation_count=len(_public_evidence_refs(turn)),
                )
                yield _done(turn, replay=False)
                return
            answer = "".join(tokens).strip()
            if not answer:
                turn = _complete_turn(
                    db,
                    turn=turn,
                    stop_reason=TURN_STOP_REASON_EVIDENCE_ONLY,
                    assistant_answer=None,
                    plan_step_count=1,
                    retrieval_operation_count=1,
                    repair_attempt_count=0,
                )
                completed = True
                _record_turn_trace(
                    settings,
                    turn,
                    request_id=start.request_id,
                    mapped_evidence_count=len(evidence),
                    citation_count=len(_public_evidence_refs(turn)),
                )
                yield _done(turn, replay=False)
                return
            turn = _complete_turn(
                db,
                turn=turn,
                stop_reason=TURN_STOP_REASON_GROUNDED,
                assistant_answer=answer,
                plan_step_count=1,
                retrieval_operation_count=1,
                repair_attempt_count=0,
            )
            completed = True
            _record_turn_trace(
                settings,
                turn,
                request_id=start.request_id,
                mapped_evidence_count=len(evidence),
                citation_count=len(_public_evidence_refs(turn)),
            )
            yield _done(turn, replay=False)
        finally:
            if not completed:
                _cancel_running_turn(db, turn)


def stream_turn_events(
    db: Session,
    *,
    settings: Settings,
    owner: User,
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
        conversation_id=conversation_id,
        client_request_id=client_request_id,
        message=message,
        domain_id=domain_id,
        composer_ref_tokens=composer_ref_tokens,
        retrieval_port=retrieval_port,
        request_id=request_id,
    )
    orchestrator = TurnOrchestrator(synthesis_adapter=synthesis_adapter, retrieval_port=retrieval_port)
    yield from orchestrator.stream_turn(db, settings=settings, start=start)


def _redact_turns(db: Session, turns: list[ConversationTurn], audit_context: AuditContext | None = None) -> int:
    now = utc_now()
    changed = 0
    for turn in turns:
        if turn.status == TURN_STATUS_REDACTED:
            continue
        turn.status = TURN_STATUS_REDACTED
        turn.stop_reason = TURN_STOP_REASON_REDACTED
        turn.assistant_answer = None
        turn.safe_error_code = None
        turn.safe_error_message = None
        turn.completed_at = turn.completed_at or now
        turn.updated_at = now
        _set_conversation_updated(db, turn, now)
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
            target_id=turn.id,
            trace_id=turn.trace_id,
            metadata={"turnStatus": TURN_STATUS_REDACTED, "stopReason": TURN_STOP_REASON_REDACTED},
        )
        changed += 1
    if changed:
        db.commit()
    return changed


def redact_turns_for_source(
    db: Session,
    source_document_id: str,
    audit_context: AuditContext | None = None,
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
    return _redact_turns(db, list(turns_by_id.values()), audit_context)


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
