from __future__ import annotations

from typing import Any

import pytest

from context_engine.models import (
    PARSER_DOCLING,
    PROFILE_SYNTHESIS,
    PROVIDER_OPENAI,
    ModelProfile,
    ProviderConfig,
    RuntimeSettings,
)
from context_engine.services.audit import AuditContext, AuditError
from context_engine.services.runtime_config import (
    DEFAULT_SYNTHESIS_PROFILE_ID,
    RuntimeConfigError,
    create_model_profile,
    delete_model_profile,
    update_runtime_settings,
)


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commit_count = 0
        self.rollback_count = 0
        self._store: dict[tuple[type[Any], Any], Any] = {}
        self._scalars: list[Any] = []

    def add(self, value: Any) -> None:
        self.added.append(value)
        key = getattr(value, "id", None)
        if key is None and isinstance(value, ProviderConfig):
            key = value.provider_kind
        if key is not None:
            self._store[(type(value), key)] = value

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def refresh(self, _value: Any) -> None:
        return None

    def get(self, model: type[Any], key: Any) -> Any | None:
        return self._store.get((model, key))

    def scalars(self, _statement: Any) -> Any:
        class _Result:
            def __init__(self, values: list[Any]) -> None:
                self._values = values

            def __iter__(self):
                return iter(self._values)

        return _Result(self._scalars)


def test_delete_rejects_default_catalog_profile() -> None:
    session = RecordingSession()
    session.add(
        ModelProfile(
            id=DEFAULT_SYNTHESIS_PROFILE_ID,
            name="OpenAI Default Synthesis",
            profile_kind=PROFILE_SYNTHESIS,
            provider_kind=PROVIDER_OPENAI,
            model_name="gpt-4.1-mini",
            vector_dimensions=None,
        )
    )
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING))

    with pytest.raises(RuntimeConfigError) as exc_info:
        delete_model_profile(session, DEFAULT_SYNTHESIS_PROFILE_ID, audit_context=AuditContext(actor_kind="administrator"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "model_profile_in_use"
    assert session.commit_count == 0


def test_create_model_profile_requires_protected_audit_commit_path() -> None:
    """Red proof: create must not commit without going through protected mutation."""
    session = RecordingSession()
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
        )
    )

    # Force audit failure via invalid actor kind after mutation preparation.
    with pytest.raises(AuditError):
        create_model_profile(
            session,
            name="OpenAI GPT-4o",
            profile_kind=PROFILE_SYNTHESIS,
            provider_kind=PROVIDER_OPENAI,
            model_name="gpt-4o",
            vector_dimensions=None,
            audit_context=AuditContext(actor_kind="not-an-actor"),
        )

    assert session.commit_count == 0
    assert session.rollback_count >= 1


def test_update_runtime_settings_rejects_unready_provider() -> None:
    session = RecordingSession()
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            credential_ciphertext=None,
        )
    )
    session.add(
        ModelProfile(
            id=DEFAULT_SYNTHESIS_PROFILE_ID,
            name="OpenAI Default Synthesis",
            profile_kind=PROFILE_SYNTHESIS,
            provider_kind=PROVIDER_OPENAI,
            model_name="gpt-4.1-mini",
            vector_dimensions=None,
        )
    )
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING))

    with pytest.raises(RuntimeConfigError) as exc_info:
        update_runtime_settings(
            session,
            {"active_synthesis_profile_id": DEFAULT_SYNTHESIS_PROFILE_ID},
            audit_context=AuditContext(actor_kind="administrator"),
        )

    assert exc_info.value.code == "provider_not_ready"
    assert session.commit_count == 0

