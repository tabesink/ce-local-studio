from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.sql import Select

from context_engine.db import utc_now
from context_engine.models import ComposerRefToken
from context_engine.services.composer_refs import (
    ComposerRefError,
    ValidatedComposerRef,
    _discover_evidence,
    _discover_templates,
    _normalize_kinds,
    _token_hash,
    validate_composer_ref_tokens,
)
from context_engine.services.prompt_assembly import PromptAssemblyService


class UnsupportedRefTokenSession:
    def __init__(self, token: ComposerRefToken) -> None:
        self.token = token

    def scalar(self, _statement: object) -> ComposerRefToken:
        return self.token


class EmptyDiscoverySession:
    def __init__(self) -> None:
        self.statements: list[Select[tuple[object]]] = []

    def scalars(self, statement: Select[tuple[object]]) -> tuple[object, ...]:
        self.statements.append(statement)
        return ()


class LookupRejectingSession:
    def get(self, *_args: object) -> None:
        raise AssertionError("unsupported refs must not trigger prompt-assembly lookups")


def test_default_composer_kinds_are_phase_one_set() -> None:
    assert _normalize_kinds(None) == ["source", "evidence", "template"]


def test_explicit_unsupported_composer_kind_is_rejected() -> None:
    with pytest.raises(ComposerRefError) as error:
        _normalize_kinds(["unsupported"])

    assert error.value.code == "validation_error"


def test_unsupported_token_kind_is_unavailable() -> None:
    token = "unsupported-ref-token"
    row = ComposerRefToken(
        token_hash=_token_hash(token),
        owner_user_id="owner_1",
        ref_kind="unsupported",
        target_id="unsupported_target_1",
        domain_id="domain_1",
        safe_label="Unsupported ref",
        safe_description="Unsupported compatibility data",
        expires_at=utc_now() + timedelta(minutes=1),
    )

    with pytest.raises(ComposerRefError) as error:
        validate_composer_ref_tokens(
            UnsupportedRefTokenSession(row),
            settings=SimpleNamespace(),
            owner=SimpleNamespace(id="owner_1"),
            conversation_id="conversation_1",
            domain_id="domain_1",
            tokens=[token],
        )

    assert error.value.code == "composer_ref_unavailable"


def test_unsupported_ref_contributes_no_prompt_assembly() -> None:
    result = PromptAssemblyService(LookupRejectingSession()).assemble(
        (
            ValidatedComposerRef(
                order=1,
                kind="unsupported",
                label="Unsupported ref",
                description="Unsupported compatibility data",
            ),
        )
    )

    assert result.is_empty
    assert result.total_chars == 0


def test_unfiltered_template_discovery_is_limited_at_the_database() -> None:
    db = EmptyDiscoverySession()

    assert _discover_templates(
        db,
        owner=SimpleNamespace(id="owner_1"),
        query=None,
        remaining=3,
    ) == []

    assert "LIMIT" in str(db.statements[0]).upper()


def test_unfiltered_evidence_discovery_is_limited_at_the_database() -> None:
    db = EmptyDiscoverySession()

    assert _discover_evidence(
        db,
        owner=SimpleNamespace(id="owner_1"),
        conversation_id="conversation_1",
        domain_id="domain_1",
        query=None,
        remaining=3,
    ) == []

    assert "LIMIT" in str(db.statements[0]).upper()


def test_filtered_template_discovery_does_not_limit_before_matching() -> None:
    db = EmptyDiscoverySession()

    assert _discover_templates(
        db,
        owner=SimpleNamespace(id="owner_1"),
        query="later match",
        remaining=3,
    ) == []

    assert "LIMIT" not in str(db.statements[0]).upper()


def test_filtered_evidence_discovery_does_not_limit_before_matching() -> None:
    db = EmptyDiscoverySession()

    assert _discover_evidence(
        db,
        owner=SimpleNamespace(id="owner_1"),
        conversation_id="conversation_1",
        domain_id="domain_1",
        query="later match",
        remaining=3,
    ) == []

    assert "LIMIT" not in str(db.statements[0]).upper()
