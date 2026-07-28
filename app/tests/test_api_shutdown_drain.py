"""P12-05 API stop-new-turns gate (unit altitude; no live Compose)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import AuthSession, Conversation, User


def _app_with_session() -> tuple[object, object, str]:
    database_path = Path(f".data/ce-drain-gate-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    owner = User(username=f"drain-{uuid4().hex[:8]}@example.test", password_hash="synthetic")
    conversation = Conversation(owner=owner, title="drain gate")
    now = utc_now()
    auth_session = AuthSession(
        user=owner,
        token_hash="b" * 64,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        last_used_at=now,
    )
    db.add_all([conversation, auth_session])
    db.commit()
    db.refresh(owner)
    db.refresh(conversation)
    db.refresh(auth_session)
    conversation_id = conversation.public_ref
    owner_id = owner.id
    auth_id = auth_session.id
    db.close()

    identity_db = app.state.session_factory()
    identity = identity_db.get(User, owner_id)
    identity_auth = identity_db.get(AuthSession, auth_id)
    assert identity is not None and identity_auth is not None
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(
        user=identity,
        auth_session=identity_auth,
    )
    return app, identity_db, conversation_id


def test_turns_stream_rejected_with_capacity_unavailable_when_not_accepting() -> None:
    app, identity_db, conversation_id = _app_with_session()
    try:
        # TestClient lifespan resets accepting_new_turns=True on enter — flip after enter.
        with TestClient(app) as client:
            client.app.state.accepting_new_turns = False
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_id}/turns:stream",
                json={
                    "clientRequestId": "drain-gate-probe",
                    "message": "should not start",
                    "composerRefTokens": [],
                },
            )
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "capacity_unavailable"
    finally:
        identity_db.close()
        app.dependency_overrides.clear()


def test_lifespan_sets_accepting_new_turns_true_then_false_on_exit() -> None:
    database_path = Path(f".data/ce-drain-life-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(database_url=f"sqlite+pysqlite:///{database_path}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    assert app.state.accepting_new_turns is True
    with TestClient(app) as client:
        assert client.app.state.accepting_new_turns is True
    assert app.state.accepting_new_turns is False
