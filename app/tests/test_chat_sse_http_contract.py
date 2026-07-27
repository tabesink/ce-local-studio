from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import context_engine.services.chat_turns as chat_turns_module
from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    AuthSession,
    Conversation,
    ConversationTurn,
    TURN_EVENT_ACCEPTED,
    TURN_EVENT_ROUTE_SELECTED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_RUNNING,
    TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
    User,
)
from context_engine.services.chat_turns import SynthesisStreamAdapter, _complete_turn, _persist_event


class DeterministicSynthesis(SynthesisStreamAdapter):
    def stream_direct(self, **_kwargs: object) -> tuple[str, ...]:
        return ("Canonical ", "answer.")


def _parse_frames(text: str) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        event_id = next(line.removeprefix("id: ") for line in lines if line.startswith("id: "))
        event_type = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        envelope = json.loads(next(line.removeprefix("data: ") for line in lines if line.startswith("data: ")))
        assert envelope["eventId"] == event_id
        assert envelope["type"] == event_type
        frames.append(envelope)
    return frames


def _remove_test_database(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        # Windows can retain a streaming-response handle until process exit.
        pass


def _http_context(monkeypatch: pytest.MonkeyPatch):
    database_path = Path(f".data/ce-chat-http-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path}", testing=True)
    app = create_app(settings)
    app.state.test_database_path = database_path
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    owner = User(username="http-member@example.test", password_hash="synthetic-password-hash")
    conversation = Conversation(owner=owner, title="HTTP SSE proof")
    now = utc_now()
    auth_session = AuthSession(
        user=owner,
        token_hash="a" * 64,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        last_used_at=now,
    )
    db.add_all([conversation, auth_session])
    db.commit()
    db.refresh(owner)
    db.refresh(conversation)
    owner_id = owner.id
    auth_session_id = auth_session.id
    conversation_id = conversation.public_ref
    db.close()

    identity_db = app.state.session_factory()
    identity = identity_db.get(User, owner_id)
    identity_auth_session = identity_db.get(AuthSession, auth_session_id)
    assert identity is not None and identity_auth_session is not None
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(
        user=identity,
        auth_session=identity_auth_session,
    )
    app.state.synthesis_stream_adapter = DeterministicSynthesis()
    monkeypatch.setattr(
        chat_turns_module,
        "_resolve_synthesis",
        lambda _db, _settings: SimpleNamespace(provider_kind="synthetic"),
    )
    return app, identity_db, conversation_id


def test_m06_live_and_cursor_replay_use_canonical_sse_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(monkeypatch)
    try:
        with TestClient(app) as client:
            live = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns:stream",
                json={
                    "clientRequestId": "http-live-request-001",
                    "message": "Give a direct response.",
                    "composerRefTokens": [],
                },
            )
            assert live.status_code == 200
            assert live.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert live.headers["cache-control"] == "private, no-store, no-transform"
            assert live.headers["x-accel-buffering"] == "no"
            live_events = _parse_frames(live.text)
            assert [event["sequence"] for event in live_events] == [1, 2, 3, 4, 5]
            assert [event["type"] for event in live_events] == [
                "turn.accepted",
                "route.selected",
                "answer.delta",
                "answer.delta",
                "turn.completed",
            ]
            assert live_events[-1]["payload"]["replay"] is False
            assert all(event["schemaVersion"] == "1.0" for event in live_events)
            turn_id = str(live_events[0]["turnId"])

            replay = client.get(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}/events",
                params={"after": 2},
            )
            assert replay.status_code == 200
            replay_events = _parse_frames(replay.text)
            assert [event["sequence"] for event in replay_events] == [3, 4, 5]
            assert [event["eventId"] for event in replay_events] == [
                event["eventId"] for event in live_events[2:]
            ]
            assert replay_events[-1]["type"] == "turn.completed"
            assert replay_events[-1]["payload"]["replay"] is True
            assert replay_events[-1]["payload"]["stopReason"] == "direct_llm"
    finally:
        identity_db.close()
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_c01_cancel_http_state_and_replay_terminal_are_consistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(monkeypatch)
    seed = app.state.session_factory()
    try:
        now = utc_now()
        conversation = seed.scalar(
            select(Conversation).where(Conversation.public_ref == conversation_id)
        )
        assert conversation is not None
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id="http-cancel-request-001",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            user_message="Cancel this response.",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        seed.add(turn)
        seed.commit()
        seed.refresh(turn)
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ACCEPTED,
            payload={
                "conversationId": conversation.id,
                "clientRequestId": turn.client_request_id,
                "replay": False,
            },
            commit=False,
        )
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ROUTE_SELECTED,
            payload={"route": TURN_ROUTE_DIRECT_LLM},
            commit=False,
        )
        seed.commit()
        turn_id = turn.public_ref

        with TestClient(app) as client:
            cancelled = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}:cancel"
            )
            assert cancelled.status_code == 202
            assert cancelled.json()["turn"]["status"] == "cancelled"
            assert cancelled.json()["turn"]["id"] == turn_id

            replay = client.get(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}/events",
                params={"after": 2},
            )
            events = _parse_frames(replay.text)
            assert len(events) == 1
            assert events[0]["sequence"] == 3
            assert events[0]["type"] == "turn.cancelled"
            assert events[0]["payload"] == {
                "code": "turn_cancelled",
                "message": "The answer was cancelled.",
                "replay": True,
            }

            again = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}:cancel"
            )
            assert again.status_code == 202
            assert again.json()["turn"]["status"] == "cancelled"
            replay_again = client.get(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}/events",
                params={"after": 0},
            )
            again_events = _parse_frames(replay_again.text)
            assert [event["type"] for event in again_events].count("turn.cancelled") == 1
    finally:
        seed.close()
        identity_db.close()
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_ae5_terminal_get_marks_replay_true_without_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(monkeypatch)
    seed = app.state.session_factory()
    calls = {"direct": 0}

    class CountingSynthesis(SynthesisStreamAdapter):
        def stream_direct(self, **_kwargs: object) -> tuple[str, ...]:
            calls["direct"] += 1
            return ("Should not run.",)

    app.state.synthesis_stream_adapter = CountingSynthesis()
    try:
        now = utc_now()
        conversation = seed.scalar(
            select(Conversation).where(Conversation.public_ref == conversation_id)
        )
        assert conversation is not None
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id="http-terminal-replay-001",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            user_message="Already finished.",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        seed.add(turn)
        seed.commit()
        seed.refresh(turn)
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ACCEPTED,
            payload={
                "conversationId": conversation.id,
                "clientRequestId": turn.client_request_id,
                "replay": False,
            },
            commit=False,
        )
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ROUTE_SELECTED,
            payload={"route": TURN_ROUTE_DIRECT_LLM},
            commit=False,
        )
        seed.commit()
        turn = _complete_turn(
            seed,
            turn=turn,
            stop_reason=TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
            assistant_answer=None,
            plan_step_count=1,
            retrieval_operation_count=1,
            repair_attempt_count=0,
        )
        turn_id = turn.public_ref

        with TestClient(app) as client:
            replay = client.get(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}/events",
                params={"after": 0},
            )
            assert replay.status_code == 200
            events = _parse_frames(replay.text)
            assert [event["type"] for event in events][-1] == "turn.completed"
            assert events[-1]["payload"]["replay"] is True
            assert events[-1]["payload"]["stopReason"] == "no_grounded_context"
            assert calls["direct"] == 0
    finally:
        seed.close()
        identity_db.close()
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_ae6_unreconstructable_after_returns_cursor_expired_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(monkeypatch)
    seed = app.state.session_factory()
    try:
        now = utc_now()
        conversation = seed.scalar(
            select(Conversation).where(Conversation.public_ref == conversation_id)
        )
        assert conversation is not None
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id="http-cursor-expired-001",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            user_message="Cursor expired proof.",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        seed.add(turn)
        seed.commit()
        seed.refresh(turn)
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ACCEPTED,
            payload={
                "conversationId": conversation.id,
                "clientRequestId": turn.client_request_id,
                "replay": False,
            },
            commit=False,
        )
        _persist_event(
            seed,
            turn=turn,
            event_type=TURN_EVENT_ROUTE_SELECTED,
            payload={"route": TURN_ROUTE_DIRECT_LLM},
            commit=False,
        )
        seed.commit()
        turn = _complete_turn(
            seed,
            turn=turn,
            stop_reason=TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
            assistant_answer=None,
            plan_step_count=1,
            retrieval_operation_count=1,
            repair_attempt_count=0,
        )
        turn.events_retained_after = 2
        seed.commit()
        seed.refresh(turn)
        turn_id = turn.public_ref

        with TestClient(app) as client:
            expired = client.get(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}/events",
                params={"after": 0},
            )
            assert expired.status_code == 410
            body = expired.json()
            assert body["error"]["code"] == "cursor_expired"
            assert body["error"]["message"] == "The event cursor is no longer available."
            assert body["terminalSnapshot"] == {
                "turnId": turn_id,
                "status": "completed",
                "answer": None,
                "evidence": [],
                "citations": [],
            }
            assert expired.headers["cache-control"] == "private, no-store, no-transform"
    finally:
        seed.close()
        identity_db.close()
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_c01_cancel_cross_owner_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    app, identity_db, conversation_id = _http_context(monkeypatch)
    seed = app.state.session_factory()
    try:
        other = User(username="other-member@example.test", password_hash="synthetic-password-hash")
        foreign = Conversation(owner=other, title="Foreign conversation")
        now = utc_now()
        foreign_turn = ConversationTurn(
            conversation=foreign,
            client_request_id="foreign-cancel-001",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_RUNNING,
            user_message="Do not cancel me from another owner.",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        seed.add_all([other, foreign, foreign_turn])
        seed.commit()
        seed.refresh(foreign_turn)
        foreign_turn_id = foreign_turn.public_ref
        foreign_conversation_id = foreign.public_ref

        with TestClient(app) as client:
            denied = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{foreign_conversation_id}/turns/{foreign_turn_id}:cancel"
            )
            assert denied.status_code == 404

        seed.refresh(foreign_turn)
        assert foreign_turn.status == TURN_STATUS_RUNNING
    finally:
        seed.close()
        identity_db.close()
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)
