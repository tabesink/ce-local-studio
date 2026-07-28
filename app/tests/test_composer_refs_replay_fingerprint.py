"""P11-03 U3 / DRIFT-26 — replay-without-reconsume + refs-changed conflict (M-09 / M-10)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import context_engine.services.chat_turns as chat_turns_module
from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.dev.seed_prompt_templates import TEMPLATE_SAFETY_SUMMARY_ID, seed_prompt_template_fixtures
from context_engine.models import (
    COMPOSER_REF_KIND_TEMPLATE,
    TURN_STATUS_COMPLETED,
    ComposerRefToken,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.chat_turns import SynthesisStreamAdapter, start_or_replay_turn
from context_engine.services.composer_refs import _token_hash
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


class CountingSynthesis(SynthesisStreamAdapter):
    def __init__(self) -> None:
        self.direct_calls = 0

    def stream_direct(self, **_kwargs: object) -> tuple[str, ...]:
        self.direct_calls += 1
        return ("Direct ", "answer.")


def _remove_test_database(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


def _security(settings: Settings, token: str, bucket: str) -> tuple[dict[str, str], dict[str, str]]:
    csrf = issue_csrf_token(settings, binding=hash_session_token(token))
    headers = {
        "Origin": "http://ce.example.test",
        PUBLIC_HOST_HEADER: "ce.example.test",
        PUBLIC_PROTO_HEADER: "http",
        CLIENT_BUCKET_HEADER: bucket,
        CSRF_HEADER: csrf,
    }
    cookies = {
        settings.session_cookie_name: token,
        settings.csrf_cookie_name: csrf,
    }
    return headers, cookies


def _app_context(monkeypatch: pytest.MonkeyPatch):
    database_path = Path(f".data/ce-composer-replay-{uuid4().hex}.db").resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key=TEST_CSRF_SIGNING_KEY,
        session_cookie_secure=False,
    )
    app = create_app(settings)
    app.state.test_database_path = database_path
    Base.metadata.create_all(app.state.engine)
    synthesis = CountingSynthesis()
    app.state.synthesis_stream_adapter = synthesis
    monkeypatch.setattr(
        chat_turns_module,
        "_resolve_synthesis",
        lambda _db, _settings: SimpleNamespace(provider_kind="synthetic"),
    )
    db = app.state.session_factory()
    try:
        seed_prompt_template_fixtures(db, environment="test", allow_test_seed="true")
        owner = create_user(db, "replay-owner@example.test", "Password123!")
        session_token, auth_session = create_auth_session(db, owner, settings)
        conversation = Conversation(owner_user_id=owner.id, title="Composer replay proof")
        db.add(conversation)
        raw_a = f"ce-p11-03-replay-a-{uuid4().hex}"
        raw_b = f"ce-p11-03-replay-b-{uuid4().hex}"
        now = utc_now()
        for raw in (raw_a, raw_b):
            db.add(
                ComposerRefToken(
                    id=str(uuid4()),
                    token_hash=_token_hash(raw),
                    owner_user_id=owner.id,
                    ref_kind=COMPOSER_REF_KIND_TEMPLATE,
                    target_id=TEMPLATE_SAFETY_SUMMARY_ID,
                    domain_id=None,
                    safe_label="Replay template",
                    safe_description=None,
                    expires_at=now + timedelta(hours=1),
                    created_at=now,
                )
            )
        db.commit()
        db.refresh(conversation)
        conversation_ref = conversation.public_ref
        owner_id = owner.id
        auth_session_id = auth_session.id
    finally:
        db.close()
    return app, settings, session_token, conversation_ref, owner_id, auth_session_id, raw_a, raw_b, synthesis


def _turn_count(app, conversation_ref: str) -> int:
    with app.state.session_factory() as db:
        conversation = db.scalar(select(Conversation).where(Conversation.public_ref == conversation_ref))
        assert conversation is not None
        return int(
            db.scalar(
                select(func.count())
                .select_from(ConversationTurn)
                .where(ConversationTurn.conversation_id == conversation.id)
            )
            or 0
        )


def test_m09_drift26_identical_http_stream_attaches_without_reconsume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, token, conversation_ref, owner_id, auth_session_id, raw_a, _raw_b, synthesis = _app_context(
        monkeypatch
    )
    headers, cookies = _security(settings, token, "replay-bucket")
    client_request_id = "composer-replay-identical-001"
    message = "What is 2+2?"
    try:
        with TestClient(app) as client:
            first = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": client_request_id,
                    "message": message,
                    "composerRefTokens": [raw_a],
                },
                headers=headers,
                cookies=cookies,
            )
            assert first.status_code == 200, first.text
            assert synthesis.direct_calls == 1

            with app.state.session_factory() as db:
                token_row = db.scalar(
                    select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw_a))
                )
                assert token_row is not None
                assert token_row.consumed_at is not None
                consumed_at = token_row.consumed_at
                turns_before = _turn_count(app, conversation_ref)

            second = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": client_request_id,
                    "message": message,
                    "composerRefTokens": [raw_a],
                },
                headers=headers,
                cookies=cookies,
            )
            assert second.status_code == 200, second.text
            assert synthesis.direct_calls == 1
            assert _turn_count(app, conversation_ref) == turns_before
            assert raw_a not in second.text
            assert _token_hash(raw_a) not in second.text

            with app.state.session_factory() as db:
                token_row = db.scalar(
                    select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw_a))
                )
                assert token_row is not None
                assert token_row.consumed_at == consumed_at
                accepted = db.scalar(
                    select(func.count()).select_from(ConversationTurnComposerRef)
                )
                assert accepted == 1
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


@pytest.mark.parametrize(
    ("label", "tokens_factory"),
    [
        ("refs_changed", lambda a, b: [b]),
        ("refs_reordered", lambda a, b: [b, a]),
        ("omit_tokens", lambda a, b: []),
    ],
)
def test_m10_refs_fingerprint_conflict_projects_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    tokens_factory,
) -> None:
    app, settings, token, conversation_ref, owner_id, auth_session_id, raw_a, raw_b, synthesis = _app_context(
        monkeypatch
    )
    headers, cookies = _security(settings, token, "conflict-bucket")
    client_request_id = f"composer-conflict-{label}"
    message = "What is 2+2?"
    try:
        with app.state.session_factory() as db:
            owner = db.get(User, owner_id)
            from context_engine.models import AuthSession

            auth_session = db.get(AuthSession, auth_session_id)
            assert owner is not None and auth_session is not None
            first_tokens = [raw_a] if label != "refs_reordered" else [raw_a, raw_b]
            result = start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=conversation_ref,
                client_request_id=client_request_id,
                message=message,
                domain_id=None,
                composer_ref_tokens=first_tokens,
            )
            assert result.replay is False
            result.turn.status = TURN_STATUS_COMPLETED
            result.turn.completed_at = utc_now()
            db.commit()
            consumed_before = {
                row.token_hash: row.consumed_at
                for row in db.scalars(select(ComposerRefToken))
                if row.consumed_at is not None
            }

        before = _turn_count(app, conversation_ref)
        conflict_tokens = tokens_factory(raw_a, raw_b)
        with TestClient(app) as client:
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": client_request_id,
                    "message": message,
                    "composerRefTokens": conflict_tokens,
                },
                headers=headers,
                cookies=cookies,
            )
        body = response.json()
        assert response.status_code == 409
        assert body["error"]["code"] == "idempotency_conflict"
        assert body["error"]["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
        assert body["error"]["fields"] == {}
        assert _turn_count(app, conversation_ref) == before
        assert synthesis.direct_calls == 0
        assert raw_a not in response.text
        assert raw_b not in response.text
        assert _token_hash(raw_a) not in response.text

        with app.state.session_factory() as db:
            consumed_after = {
                row.token_hash: row.consumed_at
                for row in db.scalars(select(ComposerRefToken))
                if row.consumed_at is not None
            }
            assert consumed_after == consumed_before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m10_empty_ref_identical_retry_still_attaches(monkeypatch: pytest.MonkeyPatch) -> None:
    app, settings, token, conversation_ref, owner_id, auth_session_id, _raw_a, _raw_b, synthesis = _app_context(
        monkeypatch
    )
    headers, cookies = _security(settings, token, "empty-ref-bucket")
    client_request_id = "composer-empty-ref-identical"
    message = "What is 2+2?"
    try:
        with TestClient(app) as client:
            first = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": client_request_id,
                    "message": message,
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            assert first.status_code == 200, first.text
            assert synthesis.direct_calls == 1
            before = _turn_count(app, conversation_ref)
            second = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": client_request_id,
                    "message": message,
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            assert second.status_code == 200, second.text
            assert synthesis.direct_calls == 1
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)
