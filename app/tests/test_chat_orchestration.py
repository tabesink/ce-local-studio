"""P7-03 focused orchestration proofs (M-03 / M-07).

Service-level tests inject retrieval + synthesis ports. Sealed SSE
attach/replay/cancel ownership remains P7-04.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.adapters.synthesis import (
    OpenAISynthesisAdapter,
    RegistrySynthesisStreamAdapter,
    SynthesisRequest,
    default_synthesis_registry,
)
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    PROVIDER_BEDROCK,
    PROVIDER_OPENAI,
    TURN_EVENT_ANSWER_DELTA,
    TURN_EVENT_CANCELLED,
    TURN_EVENT_COMPLETED,
    TURN_EVENT_EVIDENCE_DELTA,
    TURN_EVENT_FAILED,
    TURN_EVENT_RETRIEVAL_COMPLETED,
    TURN_EVENT_RETRIEVAL_STARTED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_CANCELLED,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_FAILED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    TURN_STOP_REASON_EVIDENCE_ONLY,
    TURN_STOP_REASON_GROUNDED,
    TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
    TURN_STOP_REASON_PROVIDER_FAILURE,
    Conversation,
    ConversationTurn,
    ConversationTurnEvent,
    ConversationTurnEvidenceRef,
    SourceBlock,
    SourceDocument,
    User,
)
from context_engine.services.chat_turns import (
    SAFE_PROVIDER_FAILURE_MESSAGE,
    PublicEvidenceRef,
    SynthesisProviderError,
    SynthesisStreamAdapter,
    TurnOrchestrator,
    TurnStartResult,
    _cancel_running_turn,
    _complete_turn,
)
from context_engine.services.evidence import InternalMappedEvidence
from context_engine.services.runtime_config import TrustedModelRuntimeConfig

PRIVACY_SENTINEL = "SENTINEL-RAW-HIT-blk_private_99"
PRIVACY_URL = "https://provider.invalid/v1/secret"
PRIVACY_KEY = "sk-live-ORCH-SENTINEL"


class CountingRetrievalPort:
    def __init__(self, evidence: list[InternalMappedEvidence] | None = None) -> None:
        self.calls = 0
        self.evidence = evidence or []

    def retrieve(self, *_args: Any, **_kwargs: Any) -> list[InternalMappedEvidence]:
        self.calls += 1
        return list(self.evidence)


class ScriptedSynthesis(SynthesisStreamAdapter):
    def __init__(
        self,
        *,
        direct_tokens: tuple[str, ...] = ("Direct answer.",),
        grounded_tokens: tuple[str, ...] = ("Grounded answer.",),
        grounded_error: Exception | None = None,
        grounded_error_after: int = 0,
        direct_error: Exception | None = None,
    ) -> None:
        self.direct_tokens = direct_tokens
        self.grounded_tokens = grounded_tokens
        self.grounded_error = grounded_error
        self.grounded_error_after = grounded_error_after
        self.direct_error = direct_error
        self.direct_calls = 0
        self.grounded_calls = 0
        self.last_grounded_evidence: tuple[PublicEvidenceRef, ...] | None = None

    def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
        self.direct_calls += 1
        if self.direct_error is not None:
            raise self.direct_error
        return self.direct_tokens

    def stream_grounded(self, **kwargs: Any) -> Iterable[str]:
        self.grounded_calls += 1
        self.last_grounded_evidence = kwargs.get("evidence")
        yielded = 0
        for token in self.grounded_tokens:
            if yielded >= self.grounded_error_after and self.grounded_error is not None:
                raise self.grounded_error
            yielded += 1
            yield token
        if self.grounded_error is not None and yielded >= self.grounded_error_after:
            raise self.grounded_error


def _settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'orch.db'}", testing=True)


def _open_db(settings: Settings) -> Session:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def _synthesis(*, provider_kind: str = PROVIDER_OPENAI) -> TrustedModelRuntimeConfig:
    return TrustedModelRuntimeConfig(
        profile_id="openai-synthesis-default",
        provider_kind=provider_kind,
        model_name="gpt-4.1-mini",
        credential="sk-test-orchestration",
    )


def _mapped_evidence(*, excerpt: str = "Authorized policy excerpt.") -> InternalMappedEvidence:
    return InternalMappedEvidence(
        source_document_id="source-orch-1",
        source_block_id="block-orch-1",
        source_label="policy.pdf",
        excerpt=excerpt,
        kind="text",
        document_ref="document-orch-1",
        document_label="policy.pdf",
        anchor={"pageNumber": 1, "fallback": "page"},
        retrieval_order=1,
    )


def _seed_source(db: Session, *, domain_id: str = "domain-orch") -> None:
    source = SourceDocument(
        id="source-orch-1",
        public_ref="document-orch-1",
        domain_id=domain_id,
        original_filename="policy.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=256,
        original_object_key="source/orch-1",
        state="prepared",
        parser_kind="docling",
    )
    block = SourceBlock(
        id="block-orch-1",
        source_document_id=source.id,
        domain_id=domain_id,
        source_order=1,
        kind="text",
        canonical_markdown="Authorized policy excerpt.",
    )
    db.add_all([source, block])
    db.commit()


def _running_turn(
    db: Session,
    *,
    route: str,
    message: str,
    domain_id: str | None = None,
) -> ConversationTurn:
    owner = User(username="orch-member@example.test", password_hash="synthetic-password-hash")
    conversation = Conversation(owner=owner, title="Orchestration proof")
    now = utc_now()
    turn = ConversationTurn(
        conversation=conversation,
        client_request_id="orch-request-001",
        route=route,
        domain_id=domain_id,
        status=TURN_STATUS_RUNNING,
        user_message=message,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


def _start(turn: ConversationTurn, *, synthesis: TrustedModelRuntimeConfig | None = None) -> TurnStartResult:
    return TurnStartResult(
        turn=turn,
        replay=False,
        synthesis=synthesis if synthesis is not None else _synthesis(),
        prior_user_questions=(),
        request_id="req-orch-1",
    )


def _event_types(db: Session, turn: ConversationTurn) -> list[str]:
    rows = list(
        db.scalars(
            select(ConversationTurnEvent)
            .where(ConversationTurnEvent.turn_id == turn.id)
            .order_by(ConversationTurnEvent.sequence)
        )
    )
    return [row.event_type for row in rows]


def _completed_payload(db: Session, turn: ConversationTurn) -> dict[str, Any]:
    row = db.scalar(
        select(ConversationTurnEvent)
        .where(
            ConversationTurnEvent.turn_id == turn.id,
            ConversationTurnEvent.event_type == TURN_EVENT_COMPLETED,
        )
        .order_by(ConversationTurnEvent.sequence.desc())
    )
    assert row is not None
    payload = json.loads(row.payload_json)
    assert isinstance(payload, dict)
    return payload


def test_m03_ae1_domain_mapped_evidence_grounded_budget_one_shot(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence()])
        synthesis = ScriptedSynthesis(grounded_tokens=("Grounded ", "answer."))
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_RETRIEVAL_STARTED in types
        assert types.index(TURN_EVENT_EVIDENCE_DELTA) < types.index(TURN_EVENT_ANSWER_DELTA)
        assert turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_GROUNDED
        assert turn.assistant_answer == "Grounded answer."
        payload = _completed_payload(db, turn)
        assert payload["stopReason"] == TURN_STOP_REASON_GROUNDED
        assert payload["budget"] == {
            "planStepCount": 1,
            "retrievalOperationCount": 1,
            "repairAttemptCount": 0,
        }
        assert retrieval.calls == 1
        assert synthesis.grounded_calls == 1
        started = next(e for e in events if e.event_type == TURN_EVENT_RETRIEVAL_STARTED)
        assert started.payload == {"attempt": 1, "maxAttempts": 1}
    finally:
        db.close()


def test_m03_ae2_empty_corpus_completes_no_grounded_context(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([])
        synthesis = ScriptedSynthesis()
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_RETRIEVAL_STARTED in types
        assert TURN_EVENT_RETRIEVAL_COMPLETED in types
        assert TURN_EVENT_ANSWER_DELTA not in types
        assert TURN_EVENT_EVIDENCE_DELTA not in types
        assert turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_NO_GROUNDED_CONTEXT
        assert turn.assistant_answer is None
        assert turn.route == TURN_ROUTE_DOMAIN_RAG
        payload = _completed_payload(db, turn)
        assert payload["stopReason"] == TURN_STOP_REASON_NO_GROUNDED_CONTEXT
        assert payload["budget"] == {
            "planStepCount": 1,
            "retrievalOperationCount": 1,
            "repairAttemptCount": 0,
        }
        assert retrieval.calls == 1
        assert synthesis.grounded_calls == 0
        assert synthesis.direct_calls == 0
    finally:
        db.close()


def test_m03_ae3_synthesis_failure_before_answer_completes_evidence_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence()])
        synthesis = ScriptedSynthesis(grounded_error=SynthesisProviderError())
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_EVIDENCE_DELTA in types
        assert TURN_EVENT_ANSWER_DELTA not in types
        assert turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_EVIDENCE_ONLY
        assert turn.assistant_answer is None
        evidence_count = db.scalar(
            select(ConversationTurnEvidenceRef).where(ConversationTurnEvidenceRef.turn_id == turn.id)
        )
        assert evidence_count is not None
        payload = _completed_payload(db, turn)
        assert payload["budget"]["repairAttemptCount"] == 0
        assert retrieval.calls == 1
    finally:
        db.close()


def test_m03_ae4_answer_delta_then_provider_failure_fails_turn_not_evidence_only(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence()])
        synthesis = ScriptedSynthesis(
            grounded_tokens=("Partial ",),
            grounded_error=SynthesisProviderError(),
            grounded_error_after=1,
        )
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_ANSWER_DELTA in types
        assert TURN_EVENT_FAILED in types
        assert TURN_EVENT_COMPLETED not in types
        assert turn.status == TURN_STATUS_FAILED
        assert turn.stop_reason == TURN_STOP_REASON_PROVIDER_FAILURE
        assert turn.safe_error_code == "provider_failure"
        assert turn.safe_error_message == SAFE_PROVIDER_FAILURE_MESSAGE
        assert turn.stop_reason != TURN_STOP_REASON_EVIDENCE_ONLY
        assert retrieval.calls == 1
    finally:
        db.close()


def test_m07_ae5_direct_llm_zero_retrieval_budget(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DIRECT_LLM,
            message="Hello there.",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence()])
        synthesis = ScriptedSynthesis(direct_tokens=("Hello ", "back."))
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_RETRIEVAL_STARTED not in types
        assert TURN_EVENT_EVIDENCE_DELTA not in types
        assert turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_DIRECT_LLM
        assert turn.assistant_answer == "Hello back."
        payload = _completed_payload(db, turn)
        assert payload["budget"] == {
            "planStepCount": 0,
            "retrievalOperationCount": 0,
            "repairAttemptCount": 0,
        }
        assert retrieval.calls == 0
        assert synthesis.direct_calls == 1
    finally:
        db.close()


def test_m03_ae6_privacy_sentinels_absent_from_public_projection(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence(excerpt="Authorized policy excerpt.")])

        def transport(request: SynthesisRequest):
            # Private retrieval/provider material must not be required for synthesis.
            assert PRIVACY_SENTINEL not in request.message
            assert all(PRIVACY_SENTINEL not in item.excerpt for item in request.evidence)
            assert all(item.excerpt and "source_block_id" not in item.excerpt for item in request.evidence)
            yield "Safe public answer."
            raise RuntimeError(
                f"provider noise url={PRIVACY_URL} raw={PRIVACY_SENTINEL} key={PRIVACY_KEY}"
            )

        facade = RegistrySynthesisStreamAdapter(
            timeout_seconds=5,
            max_output_tokens=256,
            registry=default_synthesis_registry(transport=transport),
        )
        events = list(
            TurnOrchestrator(synthesis_adapter=facade, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        # One answer delta escaped before provider failure; terminal is failed, not evidence_only.
        assert turn.status == TURN_STATUS_FAILED
        assert turn.stop_reason == TURN_STOP_REASON_PROVIDER_FAILURE
        serialized = " ".join(
            [
                turn.assistant_answer or "",
                turn.safe_error_message or "",
                turn.safe_error_code or "",
                str([e.payload for e in events]),
            ]
        )
        assert PRIVACY_SENTINEL not in serialized
        assert PRIVACY_URL not in serialized
        assert PRIVACY_KEY not in serialized
        assert "block-orch-1" not in serialized
        assert "source-orch-1" not in serialized
    finally:
        db.close()


def test_m03_ae7_unsupported_provider_kind_fails_closed_without_stand_in(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DIRECT_LLM,
            message="Hello there.",
        )
        facade = RegistrySynthesisStreamAdapter(
            timeout_seconds=5,
            max_output_tokens=256,
            registry=default_synthesis_registry(),
        )
        events = list(
            TurnOrchestrator(synthesis_adapter=facade, retrieval_port=CountingRetrievalPort()).stream_turn(
                db,
                settings=settings,
                start=_start(turn, synthesis=_synthesis(provider_kind=PROVIDER_BEDROCK)),
            )
        )
        db.refresh(turn)
        assert turn.status == TURN_STATUS_FAILED
        assert turn.stop_reason == TURN_STOP_REASON_PROVIDER_FAILURE
        assert turn.assistant_answer is None
        text = " ".join([turn.assistant_answer or "", str([e.payload for e in events])])
        assert "I can help with that." not in text
        assert "supported by the current evidence" not in text
    finally:
        db.close()


def test_m03_ae7_domain_unsupported_provider_completes_evidence_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )
        facade = RegistrySynthesisStreamAdapter(
            timeout_seconds=5,
            max_output_tokens=256,
            registry=default_synthesis_registry(),
        )
        events = list(
            TurnOrchestrator(
                synthesis_adapter=facade,
                retrieval_port=CountingRetrievalPort([_mapped_evidence()]),
            ).stream_turn(
                db,
                settings=settings,
                start=_start(turn, synthesis=_synthesis(provider_kind=PROVIDER_BEDROCK)),
            )
        )
        db.refresh(turn)
        types = [event.event_type for event in events]
        assert TURN_EVENT_EVIDENCE_DELTA in types
        assert TURN_EVENT_ANSWER_DELTA not in types
        assert turn.status == TURN_STATUS_COMPLETED
        assert turn.stop_reason == TURN_STOP_REASON_EVIDENCE_ONLY
        assert turn.assistant_answer is None
        text = str([e.payload for e in events])
        assert "I can help with that." not in text
        assert "supported by the current evidence" not in text
        evidence = db.scalar(
            select(ConversationTurnEvidenceRef).where(ConversationTurnEvidenceRef.turn_id == turn.id)
        )
        assert evidence is not None
    finally:
        db.close()


def test_m03_ae8_single_shot_never_second_retrieval_or_repair(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="summarize the overview",
            domain_id="domain-orch",
        )
        retrieval = CountingRetrievalPort([_mapped_evidence()])
        synthesis = ScriptedSynthesis(grounded_tokens=("Overview.",))
        list(
            TurnOrchestrator(synthesis_adapter=synthesis, retrieval_port=retrieval).stream_turn(
                db, settings=settings, start=_start(turn)
            )
        )
        db.refresh(turn)
        assert retrieval.calls == 1
        assert turn.repair_attempt_count == 0
        payload = _completed_payload(db, turn)
        assert payload["budget"]["repairAttemptCount"] == 0
        assert payload["budget"]["retrievalOperationCount"] == 1
    finally:
        db.close()


def test_openai_empty_before_answer_is_evidence_only_for_domain(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        _seed_source(db)
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DOMAIN_RAG,
            message="What is the retention policy?",
            domain_id="domain-orch",
        )

        def empty(_request: SynthesisRequest):
            return iter(())

        facade = RegistrySynthesisStreamAdapter(
            timeout_seconds=5,
            max_output_tokens=256,
            registry={PROVIDER_OPENAI: OpenAISynthesisAdapter(transport=empty)},
        )
        list(
            TurnOrchestrator(
                synthesis_adapter=facade,
                retrieval_port=CountingRetrievalPort([_mapped_evidence()]),
            ).stream_turn(db, settings=settings, start=_start(turn))
        )
        db.refresh(turn)
        assert turn.stop_reason == TURN_STOP_REASON_EVIDENCE_ONLY
        assert turn.assistant_answer is None
    finally:
        db.close()


def test_c01_ae4_cancel_during_synthesis_stops_without_post_terminal_deltas(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DIRECT_LLM,
            message="Cancel mid answer.",
        )
        turn.execution_generation = 1
        db.commit()
        db.refresh(turn)

        class CancelAfterFirstToken(SynthesisStreamAdapter):
            def __init__(self) -> None:
                self.tokens_yielded = 0

            def stream_direct(self, **_kwargs: Any) -> Iterable[str]:
                self.tokens_yielded += 1
                yield "Hello "
                _cancel_running_turn(db, turn)
                self.tokens_yielded += 1
                yield "world"

            def stream_grounded(self, **_kwargs: Any) -> Iterable[str]:
                raise AssertionError("direct turn must not call grounded synthesis")

        synthesis = CancelAfterFirstToken()
        events = list(
            TurnOrchestrator(synthesis_adapter=synthesis).stream_turn(
                db,
                settings=settings,
                start=TurnStartResult(
                    turn=turn,
                    replay=False,
                    synthesis=_synthesis(),
                    prior_user_questions=(),
                    request_id="req-cancel-ae4",
                    execution_generation=1,
                ),
            )
        )
        db.refresh(turn)
        types = _event_types(db, turn)
        assert turn.status == TURN_STATUS_CANCELLED
        assert types.count(TURN_EVENT_ANSWER_DELTA) == 1
        assert types.count(TURN_EVENT_CANCELLED) == 1
        assert TURN_EVENT_COMPLETED not in types
        assert events[-1].event_type == TURN_EVENT_CANCELLED
        assert synthesis.tokens_yielded == 2
    finally:
        db.close()


def test_c01_cancel_vs_complete_race_keeps_single_terminal(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    db = _open_db(settings)
    try:
        turn = _running_turn(
            db,
            route=TURN_ROUTE_DIRECT_LLM,
            message="Race cancel and complete.",
        )
        turn.execution_generation = 2
        db.commit()
        db.refresh(turn)

        _cancel_running_turn(db, turn)
        late = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="Should not win.",
            execution_generation=2,
        )
        db.refresh(late)
        types = _event_types(db, late)
        assert late.status == TURN_STATUS_CANCELLED
        assert late.assistant_answer is None
        assert types.count(TURN_EVENT_CANCELLED) == 1
        assert TURN_EVENT_COMPLETED not in types
    finally:
        db.close()
