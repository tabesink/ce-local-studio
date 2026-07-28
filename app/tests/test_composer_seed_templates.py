from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.dev.seed_gate import SeedGateError
from context_engine.dev.seed_prompt_templates import (
    FIXTURE_TEMPLATE_IDS,
    PROMPT_TEMPLATE_FIXTURES,
    TEMPLATE_DISABLED_ID,
    TEMPLATE_SAFETY_SUMMARY_ID,
    seed_prompt_template_fixtures,
)
from context_engine.models import (
    PROMPT_TEMPLATE_STATE_APPROVED,
    PROMPT_TEMPLATE_STATE_DISABLED,
    PromptTemplate,
)
from context_engine.services.prompt_templates import safe_prompt_template_ref


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'composer-seed-templates.db'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_gated_seed_upserts_approved_and_disabled_fixtures(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        seed_prompt_template_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
        )
        rows = list(db.scalars(select(PromptTemplate).order_by(PromptTemplate.id)))
        assert {row.id for row in rows} == FIXTURE_TEMPLATE_IDS
        by_id = {row.id: row for row in rows}
        assert by_id[TEMPLATE_SAFETY_SUMMARY_ID].state == PROMPT_TEMPLATE_STATE_APPROVED
        assert by_id[TEMPLATE_DISABLED_ID].state == PROMPT_TEMPLATE_STATE_DISABLED

        seed_prompt_template_fixtures(
            db,
            environment="test",
            allow_test_seed="true",
        )
        count = db.scalar(select(func.count()).select_from(PromptTemplate))
        assert count == 2
        assert db.get(PromptTemplate, TEMPLATE_DISABLED_ID).state == PROMPT_TEMPLATE_STATE_DISABLED
    finally:
        db.close()


def test_gated_seed_reset_removes_non_fixture_templates(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        db.add(
            PromptTemplate(
                id="11111111-1111-4111-8111-111111111111",
                name="Concise synthesis",
                description="legacy",
                body="legacy body",
                state=PROMPT_TEMPLATE_STATE_APPROVED,
            )
        )
        db.commit()
        seed_prompt_template_fixtures(
            db,
            reset=True,
            environment="test",
            allow_test_seed="1",
        )
        ids = {row.id for row in db.scalars(select(PromptTemplate))}
        assert ids == FIXTURE_TEMPLATE_IDS
    finally:
        db.close()


def test_gated_seed_reset_denied_outside_test_environment(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        db.add(
            PromptTemplate(
                id="11111111-1111-4111-8111-111111111111",
                name="Concise synthesis",
                description="legacy",
                body="legacy body",
                state=PROMPT_TEMPLATE_STATE_APPROVED,
            )
        )
        db.commit()
        with pytest.raises(SeedGateError, match="CE_ENVIRONMENT=test"):
            seed_prompt_template_fixtures(
                db,
                reset=True,
                environment="development",
                allow_test_seed="true",
            )
        ids = {row.id for row in db.scalars(select(PromptTemplate))}
        assert ids == {"11111111-1111-4111-8111-111111111111"}
    finally:
        db.close()


def test_seed_gate_fails_closed_without_dual_allowlist(tmp_path: Path) -> None:
    db = _session(tmp_path)
    try:
        with pytest.raises(SeedGateError):
            seed_prompt_template_fixtures(
                db,
                environment="test",
                allow_test_seed="false",
            )
        with pytest.raises(SeedGateError):
            seed_prompt_template_fixtures(
                db,
                environment="production",
                allow_test_seed="true",
            )
        assert db.scalar(select(func.count()).select_from(PromptTemplate)) == 0
    finally:
        db.close()


def test_api_lifespan_does_not_install_demo_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CE_ALLOW_TEST_SEED", raising=False)
    monkeypatch.setenv("CE_ENVIRONMENT", "test")
    database_path = tmp_path / "lifespan-templates.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        session_cookie_secure=False,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app):
        db = app.state.session_factory()
        try:
            count = db.scalar(select(func.count()).select_from(PromptTemplate))
            assert count == 0
        finally:
            db.close()
    app.state.engine.dispose()


def test_safe_prompt_template_ref_omits_body() -> None:
    fixture = PROMPT_TEMPLATE_FIXTURES[0]
    template = PromptTemplate(
        id=fixture.seed_id,
        name=fixture.name,
        description=fixture.description,
        body=fixture.body,
        state=fixture.state,
    )
    projection = safe_prompt_template_ref(template)
    assert projection == {
        "kind": "template",
        "label": fixture.name,
        "description": fixture.description,
    }
    assert "body" not in projection
