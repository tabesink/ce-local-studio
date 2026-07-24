from __future__ import annotations

from typing import Any

import pytest
from cryptography.fernet import Fernet

from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    PARSER_DOCLING,
    PROFILE_EMBEDDING,
    PROFILE_SYNTHESIS,
    PROVIDER_OPENAI,
    Domain,
    ModelProfile,
    ProviderConfig,
    RuntimeSettings,
)
from context_engine.services.audit import AuditContext, AuditError
from context_engine.services.runtime_config import (
    DEFAULT_SYNTHESIS_PROFILE_ID,
    RuntimeConfigError,
    SecretCrypto,
    TrustedRuntimeResolver,
    create_model_profile,
    delete_model_profile,
    parse_if_match_version,
    rotate_provider_credential,
    safe_model_profile,
    safe_provider,
    strong_etag,
    update_model_profile,
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

    def scalars(self, statement: Any) -> Any:
        class _Result:
            def __init__(self, values: list[Any]) -> None:
                self._values = values

            def __iter__(self):
                return iter(self._values)

            def first(self):
                return self._values[0] if self._values else None

            def one(self):
                if len(self._values) != 1:
                    raise RuntimeError("expected exactly one row")
                return self._values[0]

        entity = statement.column_descriptions[0]["entity"]
        matched = [value for (model, _key), value in self._store.items() if model is entity]
        if matched:
            return _Result(matched)
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
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING, version=1))

    with pytest.raises(RuntimeConfigError) as exc_info:
        update_runtime_settings(
            session,
            {"active_synthesis_profile_id": DEFAULT_SYNTHESIS_PROFILE_ID},
            expected_version=1,
            audit_context=AuditContext(actor_kind="administrator"),
        )

    assert exc_info.value.code == "provider_not_ready"
    assert session.commit_count == 0


def test_parse_if_match_version_requires_strong_etag() -> None:
    with pytest.raises(RuntimeConfigError) as missing:
        parse_if_match_version(None)
    assert missing.value.status_code == 428
    assert missing.value.code == "validation_error"

    with pytest.raises(RuntimeConfigError) as weak:
        parse_if_match_version('W/"1"')
    assert weak.value.status_code == 428

    assert parse_if_match_version('"3"') == 3
    assert parse_if_match_version("3") == 3
    assert strong_etag(3) == '"3"'


def test_safe_provider_projects_closed_dto_without_secrets() -> None:
    provider = ProviderConfig(
        provider_kind=PROVIDER_OPENAI,
        display_name="OpenAI",
        requires_credentials=True,
        credential_ciphertext="cipher-text-value",
        version=4,
    )
    projected = safe_provider(provider)
    assert projected == {
        "kind": "openai",
        "displayName": "OpenAI",
        "requiresCredentials": True,
        "configured": True,
        "credentialUpdatedAt": None,
        "version": 4,
    }
    assert "credential" not in projected
    assert "ciphertext" not in str(projected).lower()
    assert "providerKind" not in projected
    assert "isConfigured" not in projected


def test_secret_crypto_round_trip_and_wrong_key_fail_closed() -> None:
    current = SecretCrypto(Fernet.generate_key().decode("utf-8"))
    other = SecretCrypto(Fernet.generate_key().decode("utf-8"))
    ciphertext = current.encrypt_secret("provider-secret")
    assert ciphertext != "provider-secret"
    assert current.decrypt_secret(ciphertext) == "provider-secret"
    with pytest.raises(RuntimeConfigError) as exc_info:
        other.decrypt_secret(ciphertext)
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "runtime_config_unavailable"


def test_validate_embedding_rejects_non_positive_vector_dimensions() -> None:
    session = RecordingSession()
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            credential_ciphertext="cipher",
        )
    )

    with pytest.raises(RuntimeConfigError) as zero:
        create_model_profile(
            session,
            name="Zero Dim Embedding",
            profile_kind=PROFILE_EMBEDDING,
            provider_kind=PROVIDER_OPENAI,
            model_name="text-embedding-3-small",
            vector_dimensions=0,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert zero.value.status_code == 422
    assert zero.value.code == "validation_error"
    assert session.commit_count == 0

    with pytest.raises(RuntimeConfigError) as negative:
        create_model_profile(
            session,
            name="Negative Dim Embedding",
            profile_kind=PROFILE_EMBEDDING,
            provider_kind=PROVIDER_OPENAI,
            model_name="text-embedding-3-small",
            vector_dimensions=-1,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert negative.value.code == "validation_error"
    assert session.commit_count == 0


def test_update_rejects_domain_referenced_embedding_profile_a02() -> None:
    session = RecordingSession()
    profile = ModelProfile(
        id="openai-embedding-default",
        name="OpenAI Default Embedding",
        profile_kind=PROFILE_EMBEDDING,
        provider_kind=PROVIDER_OPENAI,
        model_name="text-embedding-3-small",
        vector_dimensions=1536,
        version=1,
    )
    session.add(profile)
    session.add(
        Domain(
            id="domain_manuals",
            display_name="Equipment Manuals",
            state=DOMAIN_STATE_STOPPED,
            embedding_profile_id=profile.id,
            runtime_instance_id="runtime-1",
            control_generation=1,
        )
    )
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING))

    projected = safe_model_profile(session, profile)
    assert projected["inUse"] is True

    with pytest.raises(RuntimeConfigError) as exc_info:
        update_model_profile(
            session,
            profile.id,
            {"vector_dimensions": 3072, "model_name": "text-embedding-3-large"},
            expected_version=1,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "model_profile_in_use"
    assert session.commit_count == 0
    assert profile.vector_dimensions == 1536


def test_update_runtime_settings_rejects_embedding_as_active_synthesis() -> None:
    session = RecordingSession()
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            credential_ciphertext="cipher",
        )
    )
    session.add(
        ModelProfile(
            id="openai-embedding-default",
            name="OpenAI Default Embedding",
            profile_kind=PROFILE_EMBEDDING,
            provider_kind=PROVIDER_OPENAI,
            model_name="text-embedding-3-small",
            vector_dimensions=1536,
        )
    )
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING, version=1))

    with pytest.raises(RuntimeConfigError) as exc_info:
        update_runtime_settings(
            session,
            {"active_synthesis_profile_id": "openai-embedding-default"},
            expected_version=1,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert exc_info.value.code == "invalid_active_synthesis_profile"
    assert session.commit_count == 0


def test_resolve_embedding_profile_rejects_synthesis_and_unready_provider() -> None:
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
    session.add(
        ModelProfile(
            id="openai-embedding-default",
            name="OpenAI Default Embedding",
            profile_kind=PROFILE_EMBEDDING,
            provider_kind=PROVIDER_OPENAI,
            model_name="text-embedding-3-small",
            vector_dimensions=1536,
        )
    )
    crypto = SecretCrypto(Fernet.generate_key().decode("utf-8"))
    resolver = TrustedRuntimeResolver(session, crypto)

    with pytest.raises(RuntimeConfigError) as synthesis:
        resolver.resolve_embedding_profile(DEFAULT_SYNTHESIS_PROFILE_ID)
    assert synthesis.value.code == "embedding_profile_invalid"

    with pytest.raises(RuntimeConfigError) as unready:
        resolver.resolve_embedding_profile("openai-embedding-default")
    assert unready.value.code == "embedding_profile_invalid"


def test_rotate_provider_credential_rejects_stale_version() -> None:
    session = RecordingSession()
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            version=2,
        )
    )
    crypto = SecretCrypto(Fernet.generate_key().decode("utf-8"))

    with pytest.raises(RuntimeConfigError) as exc_info:
        rotate_provider_credential(
            session,
            PROVIDER_OPENAI,
            "new-secret",
            crypto,
            expected_version=1,
            audit_context=AuditContext(actor_kind="administrator"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "stale_revision"
    assert session.commit_count == 0
