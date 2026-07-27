from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.db import Base, utc_now
from context_engine.models import (
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    ConversationTurnEvent,
    SourceBlock,
    SourceDocument,
    TURN_EVENT_ACCEPTED,
    TURN_EVENT_ANSWER_DELTA,
    TURN_EVENT_CANCELLED,
    TURN_EVENT_COMPLETED,
    TURN_EVENT_EVIDENCE_DELTA,
    TURN_EVENT_REDACTED,
    TURN_EVENT_ROUTE_SELECTED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_CANCELLED,
    TURN_STATUS_REDACTED,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_DIRECT_LLM,
    User,
)
from context_engine.services.chat_turns import (
    ChatTurnError,
    P6RetrievalPort,
    _cancel_running_turn,
    _complete_turn,
    _persist_evidence_refs,
    _persist_event,
    _redact_turns,
    _stored_events,
)
from context_engine.services.evidence import (
    InternalMappedEvidence,
    ScopedRetrievalError,
)
import context_engine.services.chat_turns as chat_turns_service
from context_engine.config import Settings


def _database(tmp_path: Path) -> tuple[Session, ConversationTurn]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'turn-events.db'}")
    Base.metadata.create_all(engine)
    db = Session(engine)
    owner = User(username="member@example.test", password_hash="synthetic-password-hash")
    conversation = Conversation(owner=owner, title="Canonical SSE proof")
    now = utc_now()
    turn = ConversationTurn(
        conversation=conversation,
        client_request_id="canonical-request-001",
        route=TURN_ROUTE_DIRECT_LLM,
        status=TURN_STATUS_RUNNING,
        user_message="Give a direct answer.",
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return db, turn


def _prefix(db: Session, turn: ConversationTurn) -> None:
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_ACCEPTED,
        payload={"conversationId": turn.conversation_id, "clientRequestId": turn.client_request_id, "replay": False},
        commit=False,
    )
    _persist_event(
        db,
        turn=turn,
        event_type=TURN_EVENT_ROUTE_SELECTED,
        payload={"route": TURN_ROUTE_DIRECT_LLM},
        commit=False,
    )
    db.commit()


def test_m06_events_are_ordered_durable_and_replayed_after_applied_cursor(tmp_path: Path) -> None:
    db, turn = _database(tmp_path)
    try:
        _prefix(db, turn)
        _persist_event(db, turn=turn, event_type=TURN_EVENT_ANSWER_DELTA, payload={"text": "Answer."})
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="Answer.",
        )
        db.refresh(turn.conversation)
        assert turn.conversation.version == 2

        events = list(_stored_events(db, turn))
        assert [event.sequence for event in events] == [1, 2, 3, 4]
        assert [event.event_type for event in events] == [
            TURN_EVENT_ACCEPTED,
            TURN_EVENT_ROUTE_SELECTED,
            TURN_EVENT_ANSWER_DELTA,
            TURN_EVENT_COMPLETED,
        ]
        assert [event.sequence for event in _stored_events(db, turn, after=2)] == [3, 4]

        rows = list(
            db.scalars(
                select(ConversationTurnEvent)
                .where(ConversationTurnEvent.turn_id == turn.id)
                .order_by(ConversationTurnEvent.sequence)
            )
        )
        assert all(
            row.payload_digest == hashlib.sha256(row.payload_json.encode("utf-8")).hexdigest()
            for row in rows
        )
    finally:
        db.close()


def test_terminal_state_and_event_roll_back_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, turn = _database(tmp_path)
    try:
        _prefix(db, turn)

        def reject_commit() -> None:
            raise RuntimeError("synthetic commit failure")

        monkeypatch.setattr(db, "commit", reject_commit)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            _complete_turn(
                db,
                turn=turn,
                stop_reason=TURN_STOP_REASON_DIRECT_LLM,
                assistant_answer="Must roll back.",
            )
        db.rollback()
        db.expire_all()

        persisted = db.get(ConversationTurn, turn.id)
        assert persisted is not None
        assert persisted.status == TURN_STATUS_RUNNING
        db.refresh(persisted.conversation)
        assert persisted.conversation.version == 1
        assert [event.event_type for event in _stored_events(db, persisted)] == [
            TURN_EVENT_ACCEPTED,
            TURN_EVENT_ROUTE_SELECTED,
        ]
    finally:
        db.close()


def test_c01_cancel_persists_cancelled_state_and_one_terminal_event(tmp_path: Path) -> None:
    db, turn = _database(tmp_path)
    try:
        _prefix(db, turn)
        _cancel_running_turn(db, turn)
        db.refresh(turn)
        db.refresh(turn.conversation)

        events = list(_stored_events(db, turn))
        assert turn.conversation.version == 2
        assert turn.status == TURN_STATUS_CANCELLED
        assert turn.stop_reason == "cancelled"
        assert turn.safe_error_code == "turn_cancelled"
        assert [event.sequence for event in events] == [1, 2, 3]
        assert [event.event_type for event in events] == [
            TURN_EVENT_ACCEPTED,
            TURN_EVENT_ROUTE_SELECTED,
            TURN_EVENT_CANCELLED,
        ]
        assert events[-1].payload == {
            "code": "turn_cancelled",
            "message": "The answer was cancelled.",
            "replay": False,
        }
    finally:
        db.close()


def test_m11_redaction_sanitizes_ledger_without_changing_existing_sequences(tmp_path: Path) -> None:
    db, turn = _database(tmp_path)
    try:
        _prefix(db, turn)
        _persist_event(db, turn=turn, event_type=TURN_EVENT_ANSWER_DELTA, payload={"text": "Sensitive answer."})
        _persist_event(
            db,
            turn=turn,
            event_type=TURN_EVENT_EVIDENCE_DELTA,
            payload={"items": [{"id": "ev_sensitive", "excerpt": "Sensitive evidence."}]},
        )
        turn = _complete_turn(
            db,
            turn=turn,
            stop_reason=TURN_STOP_REASON_DIRECT_LLM,
            assistant_answer="Sensitive answer.",
        )

        assert _redact_turns(db, [turn]) == 1
        db.refresh(turn)
        db.refresh(turn.conversation)
        events = list(_stored_events(db, turn))

        assert turn.status == TURN_STATUS_REDACTED
        assert turn.conversation.version == 3
        assert turn.assistant_answer is None
        assert [event.sequence for event in events] == [1, 2, 3, 4, 5, 6]
        assert [event.event_type for event in events] == [
            TURN_EVENT_ACCEPTED,
            TURN_EVENT_ROUTE_SELECTED,
            TURN_EVENT_ANSWER_DELTA,
            TURN_EVENT_EVIDENCE_DELTA,
            TURN_EVENT_COMPLETED,
            TURN_EVENT_REDACTED,
        ]
        assert events[2].payload == {"text": ""}
        assert events[3].payload == {"items": []}
        assert events[4].payload["citations"] == []
        assert events[4].payload["acceptedRefs"] == []
        assert events[5].payload["code"] == "turn_redacted"
        serialized = json.dumps([event.payload for event in events])
        assert "Sensitive answer." not in serialized
        assert "Sensitive evidence." not in serialized
        assert "ev_sensitive" not in serialized
    finally:
        db.close()


def test_m02_p6_shared_retrieval_keeps_turn_evidence_durable_and_errors_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, turn = _database(tmp_path)
    try:
        source = SourceDocument(
            id="source-chat-p6",
            public_ref="document-chat-p6",
            domain_id="domain-chat-p6",
            original_filename="manual.pdf",
            content_type="application/pdf",
            original_sha256="a" * 64,
            original_size_bytes=128,
            original_object_key="source/chat-p6",
            state="prepared",
            parser_kind="docling",
        )
        block = SourceBlock(
            id="block-chat-p6",
            source_document_id=source.id,
            domain_id=source.domain_id,
            source_order=1,
            kind="text",
            canonical_markdown="Canonical durable evidence.",
        )
        db.add_all([source, block])
        db.commit()

        mapped = InternalMappedEvidence(
            source_document_id=source.id,
            source_block_id=block.id,
            source_label="manual.pdf",
            excerpt="Canonical durable evidence.",
            kind="text",
            document_ref=source.public_ref,
            document_label=source.original_filename,
            anchor=None,
            retrieval_order=1,
        )
        _persist_evidence_refs(db, turn=turn, evidence=[mapped])

        persisted = db.scalar(
            select(ConversationTurnEvidenceRef).where(
                ConversationTurnEvidenceRef.turn_id == turn.id
            )
        )
        assert persisted is not None
        assert persisted.source_document_id == source.id
        assert persisted.source_block_id == block.id
        assert persisted.citation_label == "[1]"
        assert persisted.excerpt == "Canonical durable evidence."

        private_failure = "SENTINEL-PRIVATE-RETRIEVAL-FAILURE"

        def fail_retrieval(*_args, **_kwargs):
            raise ScopedRetrievalError(
                "retrieval_unavailable",
                private_failure,
            )

        monkeypatch.setattr(
            chat_turns_service,
            "retrieve_internal_scoped_evidence",
            fail_retrieval,
        )
        settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            testing=True,
        )

        with pytest.raises(ChatTurnError) as failure:
            P6RetrievalPort().retrieve(
                db,
                settings=settings,
                domain_id=source.domain_id,
                question="Where is the valve?",
                intent="fact",
            )

        assert failure.value.status_code == 502
        assert failure.value.code == "domain_runtime_unavailable"
        assert private_failure not in failure.value.message
    finally:
        db.close()
