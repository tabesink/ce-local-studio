from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import context_engine.services.chat_turns as chat_turns_module
from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
)
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_RUNNING,
    AuthSession,
    Conversation,
    ConversationTurn,
    Domain,
    ModelProfile,
    ProviderConfig,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.chat_turns import SynthesisStreamAdapter, start_or_replay_turn
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)

_DOMAIN_REQUIRED_MESSAGE = "According to the manual, where is the valve?"
_GENERAL_MESSAGE = "What is 2+2?"
_EVIDENCE_DOMAIN_UNAVAILABLE = "This knowledge domain is not currently available for queries."


class DeterministicSynthesis(SynthesisStreamAdapter):
    def stream_direct(self, **_kwargs: object) -> tuple[str, ...]:
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


def _seed_domain(db, *, domain_id: str, state: str) -> Domain:
    provider = db.get(ProviderConfig, "openai")
    if provider is None:
        provider = ProviderConfig(
            provider_kind="openai",
            display_name="OpenAI",
            requires_credentials=False,
        )
        db.add(provider)
        db.flush()
    profile = ModelProfile(
        name=f"Embedding {domain_id}",
        profile_kind="embedding",
        provider_kind="openai",
        model_name="synthetic-embedding",
        vector_dimensions=1536,
    )
    domain = Domain(
        id=domain_id,
        display_name=domain_id,
        state=state,
        embedding_profile=profile,
    )
    db.add_all([profile, domain])
    db.commit()
    db.refresh(domain)
    return domain


def _http_context(monkeypatch: pytest.MonkeyPatch):
    database_path = Path(f".data/ce-turn-route-http-{uuid4().hex}.db").resolve()
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
    db = app.state.session_factory()
    try:
        owner = create_user(db, "turn-owner@example.test", "Password123!")
        other = create_user(db, "turn-other@example.test", "Password123!")
        owner_token, owner_session = create_auth_session(db, owner, settings)
        other_token, _ = create_auth_session(db, other, settings)
        conversation = Conversation(owner_user_id=owner.id, title="Turn route proof")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conversation_ref = conversation.public_ref
        owner_id = owner.id
        owner_session_id = owner_session.id
    finally:
        db.close()

    app.state.synthesis_stream_adapter = DeterministicSynthesis()
    monkeypatch.setattr(
        chat_turns_module,
        "_resolve_synthesis",
        lambda _db, _settings: SimpleNamespace(provider_kind="synthetic"),
    )
    return app, settings, owner_token, other_token, conversation_ref, owner_id, owner_session_id


def _turn_count(app, conversation_ref: str) -> int:
    with app.state.session_factory() as db:
        conversation = db.scalar(select(Conversation).where(Conversation.public_ref == conversation_ref))
        assert conversation is not None
        return db.scalar(
            select(func.count()).select_from(ConversationTurn).where(
                ConversationTurn.conversation_id == conversation.id
            )
        ) or 0


def _assert_private_error(
    response,
    *,
    status_code: int,
    code: str,
    message: str | None = None,
    fields: dict[str, str] | None = None,
) -> None:
    body = response.json()
    assert response.status_code == status_code
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert body["error"]["code"] == code
    assert body["error"]["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
    assert body["error"]["fields"] == ({} if fields is None else fields)
    if message is not None:
        assert body["error"]["message"] == message


def test_m07_ae2_domain_seeking_without_domain_returns_domain_required_and_no_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, _, _ = _http_context(monkeypatch)
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-domain-required",
                    "message": _DOMAIN_REQUIRED_MESSAGE,
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=422,
                code="domain_required",
                message="A knowledge domain is required.",
            )
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m07_ae1_general_message_creates_direct_llm_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, owner_id, owner_session_id = _http_context(
        monkeypatch
    )
    try:
        with app.state.session_factory() as db:
            owner = db.get(User, owner_id)
            auth_session = db.get(AuthSession, owner_session_id)
            assert owner is not None and auth_session is not None
            result = start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=conversation_ref,
                client_request_id="route-svc-direct-llm",
                message=_GENERAL_MESSAGE,
                domain_id=None,
            )
            assert result.replay is False
            assert result.turn.route == TURN_ROUTE_DIRECT_LLM
            assert result.turn.domain_id is None
            assert result.turn.status == TURN_STATUS_RUNNING
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m07_ae3_eligible_domain_creates_domain_rag_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, owner_id, owner_session_id = _http_context(
        monkeypatch
    )
    monkeypatch.setattr(chat_turns_module, "_validate_domain_for_new_turn", lambda *_a, **_k: None)
    try:
        with app.state.session_factory() as db:
            _seed_domain(db, domain_id="ops-manual", state=DOMAIN_STATE_RUNNING)
            owner = db.get(User, owner_id)
            auth_session = db.get(AuthSession, owner_session_id)
            assert owner is not None and auth_session is not None
            result = start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=conversation_ref,
                client_request_id="route-svc-domain-rag",
                message=_GENERAL_MESSAGE,
                domain_id="ops-manual",
            )
            assert result.turn.route == TURN_ROUTE_DOMAIN_RAG
            assert result.turn.domain_id == "ops-manual"
            assert result.turn.status == TURN_STATUS_RUNNING
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m02_ae4_stopped_domain_returns_domain_not_query_eligible_and_no_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, _, _ = _http_context(monkeypatch)
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with app.state.session_factory() as db:
            _seed_domain(db, domain_id="stopped-domain", state=DOMAIN_STATE_STOPPED)
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-stopped-domain",
                    "message": _GENERAL_MESSAGE,
                    "domainId": "stopped-domain",
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=409,
                code="domain_not_query_eligible",
                message=_EVIDENCE_DOMAIN_UNAVAILABLE,
            )
            assert _turn_count(app, conversation_ref) == before
            assert response.json()["error"]["code"] != "domain_required"
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m02_ae7_domain_seeking_plus_stopped_domain_is_not_domain_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, _, _ = _http_context(monkeypatch)
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with app.state.session_factory() as db:
            _seed_domain(db, domain_id="stopped-domain", state=DOMAIN_STATE_STOPPED)
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-seeking-stopped",
                    "message": _DOMAIN_REQUIRED_MESSAGE,
                    "domainId": "stopped-domain",
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=409,
                code="domain_not_query_eligible",
                message=_EVIDENCE_DOMAIN_UNAVAILABLE,
            )
            assert response.json()["error"]["code"] != "domain_required"
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m07_unknown_domain_returns_ownership_safe_not_found_and_no_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, _, _ = _http_context(monkeypatch)
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-unknown-domain",
                    "message": _GENERAL_MESSAGE,
                    "domainId": "missing-domain",
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=404,
                code="not_found",
                message="Domain not found.",
            )
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m07_ae8_cross_owner_conversation_returns_not_found_without_turn_disclosure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, other_token, conversation_ref, _, _ = _http_context(monkeypatch)
    other_headers, other_cookies = _security(settings, other_token, "other-bucket")
    try:
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-cross-owner",
                    "message": _GENERAL_MESSAGE,
                    "composerRefTokens": [],
                },
                headers=other_headers,
                cookies=other_cookies,
            )
            _assert_private_error(
                response,
                status_code=404,
                code="not_found",
                message="Conversation not found.",
            )
            assert "turn" not in response.text.lower() or "Conversation turn" not in response.text
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m07_ae5_unknown_route_field_fails_closed_with_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, _, _ = _http_context(monkeypatch)
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-unknown-field",
                    "message": _GENERAL_MESSAGE,
                    "route": "direct_llm",
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=422,
                code="validation_error",
                fields={"route": "Invalid value."},
            )
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)


def test_m10_fingerprint_conflict_projects_idempotency_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, settings, owner_token, _, conversation_ref, owner_id, owner_session_id = _http_context(
        monkeypatch
    )
    headers, cookies = _security(settings, owner_token, "owner-bucket")
    try:
        with app.state.session_factory() as db:
            owner = db.get(User, owner_id)
            auth_session = db.get(AuthSession, owner_session_id)
            assert owner is not None and auth_session is not None
            start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=conversation_ref,
                client_request_id="route-http-idempotent",
                message=_GENERAL_MESSAGE,
                domain_id=None,
            )

        with TestClient(app) as client:
            before = _turn_count(app, conversation_ref)
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "route-http-idempotent",
                    "message": "Explain recursion in plain language.",
                    "composerRefTokens": [],
                },
                headers=headers,
                cookies=cookies,
            )
            _assert_private_error(
                response,
                status_code=409,
                code="idempotency_conflict",
                message="Client request conflicts with an existing turn.",
            )
            assert _turn_count(app, conversation_ref) == before
    finally:
        app.state.engine.dispose()
        _remove_test_database(app.state.test_database_path)
