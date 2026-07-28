from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from context_engine.db import Base
from context_engine.dev.seed_composer_refs import (
    ACCEPTED_EVIDENCE_PUBLIC_REF,
    ACCEPTED_REDACTED_PUBLIC_REF,
    ACCEPTED_SOURCE_PUBLIC_REF,
    ACCEPTED_TEMPLATE_PUBLIC_REF,
    DOMAIN_POLICIES_ID,
    RESERVED_CONSUMED_TOKEN_KEY,
    SEED_CLOCK,
    TOKEN_HASHES,
    TURN_FIGURE_ID,
    TURN_REDACTED_ID,
    USER_NOAH_ID,
    list_seeded_token_fixture_keys,
    public_accepted_ref_projection,
    seed_composer_ref_fixtures,
)
from context_engine.dev.seed_gate import SeedGateError
from context_engine.dev.seed_prompt_templates import TEMPLATE_DISABLED_ID, TEMPLATE_SAFETY_SUMMARY_ID
from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_TEMPLATE,
    ComposerRefToken,
    ConversationTurnComposerRef,
    PromptTemplate,
)


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'composer-seed-refs.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_gated_composer_seed_covers_kinds_denials_and_accepted_refs(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        keys = list_seeded_token_fixture_keys(db)
        assert keys == set(TOKEN_HASHES)
        assert RESERVED_CONSUMED_TOKEN_KEY in keys

        tokens = list(db.scalars(select(ComposerRefToken)))
        assert all(len(token.token_hash) == 64 for token in tokens)
        assert all(getattr(token, "token", None) is None for token in tokens)

        expired = next(token for token in tokens if token.safe_description == "token_mina_expired")
        assert expired.expires_at < SEED_CLOCK
        valid = next(token for token in tokens if token.safe_description == "token_mina_source_valid")
        assert valid.expires_at > SEED_CLOCK
        assert valid.consumed_at is None

        consumed = next(token for token in tokens if token.safe_description == RESERVED_CONSUMED_TOKEN_KEY)
        assert consumed.consumed_at is not None
        assert consumed.consumed_at < SEED_CLOCK
        assert consumed.expires_at > SEED_CLOCK
        assert consumed.owner_user_id == valid.owner_user_id
        assert consumed.ref_kind == COMPOSER_REF_KIND_SOURCE

        noah = next(token for token in tokens if token.safe_description == "token_noah_wrong_owner")
        assert noah.owner_user_id == USER_NOAH_ID

        wrong_domain = next(token for token in tokens if token.safe_description == "token_mina_wrong_domain")
        assert wrong_domain.domain_id == DOMAIN_POLICIES_ID

        deleted = next(token for token in tokens if token.safe_description == "token_mina_deleted_target")
        assert deleted.target_id == "missing-source-target-0001"

        disabled = next(token for token in tokens if token.safe_description == "token_mina_disabled_template")
        assert disabled.target_id == TEMPLATE_DISABLED_ID
        assert db.get(PromptTemplate, TEMPLATE_DISABLED_ID) is not None
        assert db.get(PromptTemplate, TEMPLATE_SAFETY_SUMMARY_ID) is not None

        accepted = {
            ref.public_ref: ref
            for ref in db.scalars(select(ConversationTurnComposerRef))
        }
        assert set(accepted) >= {
            ACCEPTED_SOURCE_PUBLIC_REF,
            ACCEPTED_EVIDENCE_PUBLIC_REF,
            ACCEPTED_TEMPLATE_PUBLIC_REF,
            ACCEPTED_REDACTED_PUBLIC_REF,
        }
        assert accepted[ACCEPTED_SOURCE_PUBLIC_REF].ref_kind == COMPOSER_REF_KIND_SOURCE
        assert accepted[ACCEPTED_EVIDENCE_PUBLIC_REF].ref_kind == COMPOSER_REF_KIND_EVIDENCE
        assert accepted[ACCEPTED_TEMPLATE_PUBLIC_REF].ref_kind == COMPOSER_REF_KIND_TEMPLATE

        figure_projection = [
            public_accepted_ref_projection(ref)
            for ref in sorted(
                (accepted[ACCEPTED_SOURCE_PUBLIC_REF], accepted[ACCEPTED_EVIDENCE_PUBLIC_REF], accepted[ACCEPTED_TEMPLATE_PUBLIC_REF]),
                key=lambda item: item.ref_order,
            )
        ]
        assert figure_projection == [
            {
                "id": ACCEPTED_SOURCE_PUBLIC_REF,
                "kind": COMPOSER_REF_KIND_SOURCE,
                "order": 1,
                "label": "Pump manual",
                "description": "Equipment manuals source",
            },
            {
                "id": ACCEPTED_EVIDENCE_PUBLIC_REF,
                "kind": COMPOSER_REF_KIND_EVIDENCE,
                "order": 2,
                "label": "Relief valve figure",
                "description": "Figure evidence",
            },
            {
                "id": ACCEPTED_TEMPLATE_PUBLIC_REF,
                "kind": COMPOSER_REF_KIND_TEMPLATE,
                "order": 3,
                "label": "Safety summary",
                "description": "Approved template",
            },
        ]
        for item in figure_projection:
            assert set(item) == {"id", "kind", "order", "label", "description"}

        redacted = accepted[ACCEPTED_REDACTED_PUBLIC_REF]
        assert redacted.turn_id == TURN_REDACTED_ID
        assert redacted.redacted_at is not None
        assert redacted.safe_label is None
        assert redacted.safe_description is None

        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        assert db.scalar(select(func.count()).select_from(ComposerRefToken)) == len(TOKEN_HASHES)
        assert db.scalar(select(func.count()).select_from(ConversationTurnComposerRef)) == 4
    finally:
        db.close()


def test_composer_seed_fails_closed_without_dual_gate(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        with pytest.raises(SeedGateError):
            seed_composer_ref_fixtures(db, environment="test", allow_test_seed="false")
        with pytest.raises(SeedGateError):
            seed_composer_ref_fixtures(db, environment="production", allow_test_seed="true")
        assert db.scalar(select(func.count()).select_from(ComposerRefToken)) == 0
        assert db.scalar(select(func.count()).select_from(ConversationTurnComposerRef)) == 0
    finally:
        db.close()


def test_accepted_ref_kind_target_check_rejects_malformed_row(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        seed_composer_ref_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
            now=SEED_CLOCK,
        )
        db.add(
            ConversationTurnComposerRef(
                id=str(uuid4()),
                public_ref=f"accepted_{uuid4().hex}",
                turn_id=TURN_FIGURE_ID,
                ref_order=99,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                safe_label="bad",
                source_document_id=None,
                evidence_ref_id=str(uuid4()),
                prompt_template_id=None,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
