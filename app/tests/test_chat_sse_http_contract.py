from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import context_engine.services.chat_turns as chat_turns_module
from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    Conversation,
    ConversationTurn,
    TURN_EVENT_ACCEPTED,
    TURN_EVENT_ROUTE_SELECTED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_RUNNING,
    User,
)
from context_engine.services.chat_turns import SynthesisStreamAdapter, _persist_event


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


def _http_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'chat-http.db'}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    owner = User(username="http-member@example.test", password_hash="synthetic-password-hash")
    conversation = Conversation(owner=owner, title="HTTP SSE proof")
    db.add(conversation)
    db.commit()
    db.refresh(owner)
    db.refresh(conversation)
    owner_id = owner.id
    conversation_id = conversation.id
    db.close()

    identity_db = app.state.session_factory()
    identity = identity_db.get(User, owner_id)
    assert identity is not None
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(  # type: ignore[arg-type]
        user=identity,
        auth_session=None,
    )
    app.state.synthesis_stream_adapter = DeterministicSynthesis()
    monkeypatch.setattr(
        chat_turns_module,
        "_resolve_synthesis",
        lambda _db, _settings: SimpleNamespace(provider_kind="synthetic"),
    )
    return app, identity_db, conversation_id


def test_m06_live_and_cursor_replay_use_canonical_sse_envelopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(tmp_path, monkeypatch)
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
    finally:
        identity_db.close()


def test_c01_cancel_http_state_and_replay_terminal_are_consistent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, identity_db, conversation_id = _http_context(tmp_path, monkeypatch)
    seed = app.state.session_factory()
    try:
        now = utc_now()
        turn = ConversationTurn(
            conversation_id=conversation_id,
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
            payload={"conversationId": conversation_id, "clientRequestId": turn.client_request_id, "replay": False},
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
        turn_id = turn.id

        with TestClient(app) as client:
            cancelled = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns/{turn_id}:cancel"
            )
            assert cancelled.status_code == 202
            assert cancelled.json()["turn"]["status"] == "cancelled"
            assert cancelled.json()["turn"]["stopReason"] == "cancelled"

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
                "replay": False,
            }
    finally:
        seed.close()
        identity_db.close()
