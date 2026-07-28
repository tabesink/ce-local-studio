"""P11-02 / M-09 — one-use consume and denial matrix for composer refs."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.dev.seed_composer_refs import (
    CONV_MINA_PUBLIC_REF,
    DOMAIN_MANUALS_ID,
    RESERVED_CONSUMED_TOKEN_KEY,
    SEED_CLOCK,
    TOKEN_HASHES,
    USER_MINA_ID,
    USER_NOAH_ID,
    fixture_token_hash,
    seed_composer_ref_fixtures,
)
from context_engine.dev.seed_prompt_templates import TEMPLATE_SAFETY_SUMMARY_ID
from context_engine.models import (
    COMPOSER_REF_KIND_TEMPLATE,
    TURN_STATUS_COMPLETED,
    ComposerRefToken,
    Conversation,
    ConversationTurnComposerRef,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session
from context_engine.services.chat_turns import ChatTurnError, start_or_replay_turn
from context_engine.services.composer_refs import (
    ComposerRefError,
    _token_hash,
    consume_composer_ref_tokens,
    validate_composer_ref_tokens,
)
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'composer-consume.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _raw_token_for_fixture(fixture_key: str) -> str:
    # Seed stores only hashes; tests reconstruct the deterministic preimage.
    return f"ce-p11-01:{fixture_key}"


def test_validate_rejects_already_consumed_seed(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        owner = db.get(User, USER_MINA_ID)
        assert owner is not None
        conversation = db.scalar(select(Conversation).where(Conversation.owner_user_id == USER_MINA_ID))
        assert conversation is not None

        with pytest.raises(ComposerRefError) as error:
            validate_composer_ref_tokens(
                db,
                settings=SimpleNamespace(),
                owner=owner,
                conversation_id=conversation.id,
                domain_id=DOMAIN_MANUALS_ID,
                tokens=[_raw_token_for_fixture(RESERVED_CONSUMED_TOKEN_KEY)],
            )
        assert error.value.code == "composer_ref_unavailable"
        assert fixture_token_hash(RESERVED_CONSUMED_TOKEN_KEY) == TOKEN_HASHES[RESERVED_CONSUMED_TOKEN_KEY]
    finally:
        db.close()


def test_consume_marks_token_and_blocks_reuse(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        owner = db.get(User, USER_MINA_ID)
        assert owner is not None
        raw = "ephemeral-one-use-token"
        now = utc_now()
        db.add(
            ComposerRefToken(
                id=str(uuid4()),
                token_hash=_token_hash(raw),
                owner_user_id=USER_MINA_ID,
                ref_kind=COMPOSER_REF_KIND_TEMPLATE,
                target_id=TEMPLATE_SAFETY_SUMMARY_ID,
                domain_id=None,
                safe_label="Ephemeral template",
                safe_description=None,
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        db.commit()

        conversation = db.scalar(select(Conversation).where(Conversation.owner_user_id == USER_MINA_ID))
        assert conversation is not None
        validated = validate_composer_ref_tokens(
            db,
            settings=SimpleNamespace(testing=True),
            owner=owner,
            conversation_id=conversation.id,
            domain_id=None,
            tokens=[raw],
        )
        assert len(validated.refs) == 1
        consume_composer_ref_tokens(db, owner=owner, tokens=(raw,))
        db.commit()

        row = db.scalar(select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw)))
        assert row is not None
        assert row.consumed_at is not None

        with pytest.raises(ComposerRefError) as error:
            validate_composer_ref_tokens(
                db,
                settings=SimpleNamespace(testing=True),
                owner=owner,
                conversation_id=conversation.id,
                domain_id=None,
                tokens=[raw],
            )
        assert error.value.code == "composer_ref_unavailable"

        with pytest.raises(ComposerRefError) as reuse:
            consume_composer_ref_tokens(db, owner=owner, tokens=(raw,))
        assert reuse.value.code == "composer_ref_unavailable"
    finally:
        db.close()


@pytest.mark.parametrize(
    ("fixture_key", "domain_id"),
    [
        ("token_mina_expired", DOMAIN_MANUALS_ID),
        ("token_mina_deleted_target", DOMAIN_MANUALS_ID),
        ("token_mina_disabled_template", None),
        (RESERVED_CONSUMED_TOKEN_KEY, DOMAIN_MANUALS_ID),
        ("token_mina_wrong_domain", DOMAIN_MANUALS_ID),
        ("token_noah_wrong_owner", DOMAIN_MANUALS_ID),
    ],
)
def test_seeded_denial_keys_are_unavailable(
    tmp_path: Path,
    fixture_key: str,
    domain_id: str | None,
) -> None:
    db = _session(tmp_path)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        owner = db.get(User, USER_MINA_ID)
        assert owner is not None
        conversation = db.scalar(select(Conversation).where(Conversation.owner_user_id == USER_MINA_ID))
        assert conversation is not None
        with pytest.raises(ComposerRefError) as error:
            validate_composer_ref_tokens(
                db,
                settings=SimpleNamespace(testing=True),
                owner=owner,
                conversation_id=conversation.id,
                domain_id=domain_id,
                tokens=[_raw_token_for_fixture(fixture_key)],
            )
        assert error.value.code == "composer_ref_unavailable"
        if fixture_key == "token_noah_wrong_owner":
            noah_row = db.scalar(
                select(ComposerRefToken).where(
                    ComposerRefToken.safe_description == "token_noah_wrong_owner"
                )
            )
            assert noah_row is not None
            assert noah_row.owner_user_id == USER_NOAH_ID
    finally:
        db.close()


def test_normalize_rejects_more_than_max_refs() -> None:
    from context_engine.services.composer_refs import MAX_COMPOSER_REFS, normalize_composer_ref_tokens

    tokens = [f"token-{index}" for index in range(MAX_COMPOSER_REFS + 1)]
    with pytest.raises(ComposerRefError) as error:
        normalize_composer_ref_tokens(tokens)
    assert error.value.code == "validation_error"


def _settings(database_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        session_cookie_secure=False,
    )


def test_m09_start_or_replay_turn_consumes_and_blocks_reuse(tmp_path: Path) -> None:
    database_path = tmp_path / "composer-turn-consume.db"
    settings = _settings(database_path)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=utc_now(),
        )
        owner = db.get(User, USER_MINA_ID)
        assert owner is not None
        _, auth_session = create_auth_session(db, owner, settings)
        raw = _raw_token_for_fixture("token_mina_template_valid")

        first = start_or_replay_turn(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
            conversation_id=CONV_MINA_PUBLIC_REF,
            client_request_id="composer-consume-first",
            message="What is 2+2?",
            domain_id=None,
            composer_ref_tokens=[raw],
        )
        assert first.replay is False
        token_row = db.scalar(select(ComposerRefToken).where(ComposerRefToken.token_hash == _token_hash(raw)))
        assert token_row is not None
        assert token_row.consumed_at is not None
        accepted = list(
            db.scalars(
                select(ConversationTurnComposerRef).where(
                    ConversationTurnComposerRef.turn_id == first.turn.id
                )
            )
        )
        assert len(accepted) == 1
        assert accepted[0].ref_kind == COMPOSER_REF_KIND_TEMPLATE
        consumed_at = token_row.consumed_at

        # Free the conversation for a second new-turn attempt (running fence is unrelated).
        first.turn.status = TURN_STATUS_COMPLETED
        first.turn.completed_at = utc_now()
        db.commit()

        with pytest.raises(ChatTurnError) as reuse:
            start_or_replay_turn(
                db,
                settings=settings,
                owner=owner,
                auth_session=auth_session,
                conversation_id=CONV_MINA_PUBLIC_REF,
                client_request_id="composer-consume-reuse",
                message="What is 3+3?",
                domain_id=None,
                composer_ref_tokens=[raw],
            )
        assert reuse.value.code == "composer_ref_unavailable"

        replay = start_or_replay_turn(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
            conversation_id=CONV_MINA_PUBLIC_REF,
            client_request_id="composer-consume-first",
            message="What is 2+2?",
            domain_id=None,
            composer_ref_tokens=[raw],
        )
        assert replay.replay is True
        assert replay.turn.id == first.turn.id
        db.refresh(token_row)
        assert token_row.consumed_at == consumed_at
    finally:
        db.close()
        engine.dispose()


def _http_security(settings: Settings, token: str, bucket: str) -> tuple[dict[str, str], dict[str, str]]:
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


def test_m09_turn_stream_maps_consumed_token_to_operation_conflict(tmp_path: Path) -> None:
    from context_engine.dev.seed_prompt_templates import seed_prompt_template_fixtures
    from context_engine.services.auth import create_user

    database_path = tmp_path / "composer-turn-http.db"
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
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    try:
        seed_prompt_template_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
        )
        owner = create_user(db, "composer-http@example.test", "Password123!")
        session_token, auth_session = create_auth_session(db, owner, settings)
        conversation = Conversation(owner_user_id=owner.id, title="Composer HTTP consume")
        db.add(conversation)
        raw = f"ce-p11-02-http-{uuid4().hex}"
        now = utc_now()
        db.add(
            ComposerRefToken(
                id=str(uuid4()),
                token_hash=_token_hash(raw),
                owner_user_id=owner.id,
                ref_kind=COMPOSER_REF_KIND_TEMPLATE,
                target_id=TEMPLATE_SAFETY_SUMMARY_ID,
                domain_id=None,
                safe_label="HTTP consume template",
                safe_description=None,
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        db.commit()
        db.refresh(conversation)
        conversation_ref = conversation.public_ref
        owner_id = owner.id
        first = start_or_replay_turn(
            db,
            settings=settings,
            owner=owner,
            auth_session=auth_session,
            conversation_id=conversation_ref,
            client_request_id="composer-http-consume",
            message="What is 2+2?",
            domain_id=None,
            composer_ref_tokens=[raw],
        )
        first.turn.status = TURN_STATUS_COMPLETED
        first.turn.completed_at = utc_now()
        db.commit()
    finally:
        db.close()

    headers, cookies = _http_security(settings, session_token, "mina-bucket")
    try:
        with TestClient(app) as client:
            response = client.post(
                f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}/turns:stream",
                json={
                    "clientRequestId": "composer-http-reuse",
                    "message": "What is 4+4?",
                    "composerRefTokens": [raw],
                },
                headers=headers,
                cookies=cookies,
            )
        body = response.json()
        assert response.status_code == 409
        assert body["error"]["code"] == "operation_conflict"
        assert body["error"]["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
        assert body["error"]["fields"] == {}
        assert TEMPLATE_SAFETY_SUMMARY_ID not in response.text
        assert owner_id not in response.text
        assert raw not in response.text
    finally:
        app.state.engine.dispose()
