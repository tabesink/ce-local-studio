"""P11-02 / M-09 — one-use consume and denial matrix for composer refs."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from context_engine.db import Base, utc_now
from context_engine.dev.seed_composer_refs import (
    DOMAIN_MANUALS_ID,
    RESERVED_CONSUMED_TOKEN_KEY,
    SEED_CLOCK,
    TOKEN_HASHES,
    USER_MINA_ID,
    fixture_token_hash,
    seed_composer_ref_fixtures,
)
from context_engine.dev.seed_prompt_templates import TEMPLATE_SAFETY_SUMMARY_ID
from context_engine.models import (
    COMPOSER_REF_KIND_TEMPLATE,
    ComposerRefToken,
    Conversation,
    User,
)
from context_engine.services.composer_refs import (
    ComposerRefError,
    _token_hash,
    consume_composer_ref_tokens,
    validate_composer_ref_tokens,
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
    "fixture_key",
    [
        "token_mina_expired",
        "token_mina_deleted_target",
        "token_mina_disabled_template",
        RESERVED_CONSUMED_TOKEN_KEY,
    ],
)
def test_seeded_denial_keys_are_unavailable(tmp_path: Path, fixture_key: str) -> None:
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
        domain_id = None if fixture_key == "token_mina_disabled_template" else DOMAIN_MANUALS_ID
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
    finally:
        db.close()


def test_normalize_rejects_more_than_max_refs() -> None:
    from context_engine.services.composer_refs import MAX_COMPOSER_REFS, normalize_composer_ref_tokens

    tokens = [f"token-{index}" for index in range(MAX_COMPOSER_REFS + 1)]
    with pytest.raises(ComposerRefError) as error:
        normalize_composer_ref_tokens(tokens)
    assert error.value.code == "validation_error"
