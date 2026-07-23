from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_DELETED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_UPDATED,
    AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED,
    MODEL_PROVIDER_KINDS,
    PARSER_DOCLING,
    PARSER_KINDS,
    PARSER_REDUCTO,
    PROFILE_EMBEDDING,
    PROFILE_KINDS,
    PROFILE_SYNTHESIS,
    PROVIDER_BEDROCK,
    PROVIDER_KINDS,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_REDUCTO,
    ModelProfile,
    ProviderConfig,
    RuntimeSettings,
)
from context_engine.services.audit import AuditContext, AuditService

TEST_CONFIG_ENCRYPTION_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
RUNTIME_SETTINGS_ID = 1

PROVIDER_DEFAULTS: tuple[tuple[str, str, bool], ...] = (
    (PROVIDER_OPENAI, "OpenAI", True),
    (PROVIDER_BEDROCK, "AWS Bedrock", True),
    (PROVIDER_OLLAMA, "Ollama", False),
    (PROVIDER_REDUCTO, "Reducto", True),
)


@dataclass(frozen=True)
class ModelCatalogEntry:
    seed_id: str
    name: str
    profile_kind: str
    provider_kind: str
    model_name: str
    vector_dimensions: int | None
    is_default: bool = False


MODEL_CATALOG: tuple[ModelCatalogEntry, ...] = (
    ModelCatalogEntry("openai-embedding-default", "OpenAI Default Embedding", PROFILE_EMBEDDING, PROVIDER_OPENAI, "text-embedding-3-small", 1536, True),
    ModelCatalogEntry("openai-embedding-large", "OpenAI Embedding Large", PROFILE_EMBEDDING, PROVIDER_OPENAI, "text-embedding-3-large", 3072),
    ModelCatalogEntry("openai-embedding-ada002", "OpenAI Embedding Ada 002 (legacy)", PROFILE_EMBEDDING, PROVIDER_OPENAI, "text-embedding-ada-002", 1536),
    ModelCatalogEntry("bedrock-titan-embed-v2", "Bedrock Titan Embed v2", PROFILE_EMBEDDING, PROVIDER_BEDROCK, "amazon.titan-embed-text-v2:0", 1024),
    ModelCatalogEntry("bedrock-cohere-embed-v4", "Bedrock Cohere Embed v4", PROFILE_EMBEDDING, PROVIDER_BEDROCK, "cohere.embed-v4:0", 1536),
    ModelCatalogEntry("bedrock-cohere-embed-en-v3", "Bedrock Cohere Embed English v3", PROFILE_EMBEDDING, PROVIDER_BEDROCK, "cohere.embed-english-v3", 1024),
    ModelCatalogEntry("bedrock-cohere-embed-multi-v3", "Bedrock Cohere Embed Multilingual v3", PROFILE_EMBEDDING, PROVIDER_BEDROCK, "cohere.embed-multilingual-v3", 1024),
    ModelCatalogEntry("bedrock-titan-embed-v1", "Bedrock Titan Embed v1 (legacy)", PROFILE_EMBEDDING, PROVIDER_BEDROCK, "amazon.titan-embed-text-v1", 1536),
    ModelCatalogEntry("openai-synthesis-default", "OpenAI Default Synthesis", PROFILE_SYNTHESIS, PROVIDER_OPENAI, "gpt-4.1-mini", None, True),
    ModelCatalogEntry("openai-gpt-4-1", "OpenAI GPT-4.1", PROFILE_SYNTHESIS, PROVIDER_OPENAI, "gpt-4.1", None),
    ModelCatalogEntry("openai-gpt-4-1-nano", "OpenAI GPT-4.1 Nano", PROFILE_SYNTHESIS, PROVIDER_OPENAI, "gpt-4.1-nano", None),
    ModelCatalogEntry("openai-gpt-4o", "OpenAI GPT-4o", PROFILE_SYNTHESIS, PROVIDER_OPENAI, "gpt-4o", None),
    ModelCatalogEntry("openai-gpt-4o-mini", "OpenAI GPT-4o Mini", PROFILE_SYNTHESIS, PROVIDER_OPENAI, "gpt-4o-mini", None),
    ModelCatalogEntry("bedrock-claude-sonnet-4-5", "Bedrock Claude Sonnet 4.5", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "anthropic.claude-sonnet-4-5-20250929-v1:0", None),
    ModelCatalogEntry("bedrock-claude-35-sonnet-v2", "Bedrock Claude 3.5 Sonnet v2", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "anthropic.claude-3-5-sonnet-20241022-v2:0", None),
    ModelCatalogEntry("bedrock-claude-35-haiku", "Bedrock Claude 3.5 Haiku", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "anthropic.claude-3-5-haiku-20241022-v1:0", None),
    ModelCatalogEntry("bedrock-claude-3-opus", "Bedrock Claude 3 Opus", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "anthropic.claude-3-opus-20240229-v1:0", None),
    ModelCatalogEntry("bedrock-cohere-command-r-plus", "Bedrock Cohere Command R+", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "cohere.command-r-plus-v1:0", None),
    ModelCatalogEntry("bedrock-cohere-command-r", "Bedrock Cohere Command R", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "cohere.command-r-v1:0", None),
    ModelCatalogEntry("bedrock-llama-33-70b", "Bedrock Llama 3.3 70B Instruct", PROFILE_SYNTHESIS, PROVIDER_BEDROCK, "meta.llama3-3-70b-instruct-v1:0", None),
)

DEFAULT_MODEL_PROFILE_IDS = {entry.seed_id for entry in MODEL_CATALOG if entry.is_default}
DEFAULT_SYNTHESIS_PROFILE_ID = "openai-synthesis-default"


class RuntimeConfigError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _effective_encryption_key(settings: Settings) -> str:
    if settings.config_encryption_key:
        return settings.config_encryption_key
    if settings.testing:
        return TEST_CONFIG_ENCRYPTION_KEY
    raise RuntimeError("CONFIG_ENCRYPTION_KEY is required outside test.")


def validate_config_encryption_key(settings: Settings) -> None:
    key = _effective_encryption_key(settings)
    try:
        Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError("CONFIG_ENCRYPTION_KEY must be a valid Fernet key.") from exc


class SecretCrypto:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("utf-8"))

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecretCrypto":
        return cls(_effective_encryption_key(settings))

    def encrypt_secret(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeConfigError(500, "runtime_config_unavailable", "Runtime configuration unavailable.") from exc


def seed_runtime_config(db: Session) -> None:
    existing = {provider.provider_kind: provider for provider in db.scalars(select(ProviderConfig))}
    for provider_kind, display_name, requires_credentials in PROVIDER_DEFAULTS:
        provider = existing.get(provider_kind)
        if provider is None:
            db.add(
                ProviderConfig(
                    provider_kind=provider_kind,
                    display_name=display_name,
                    requires_credentials=requires_credentials,
                )
            )
        else:
            provider.display_name = display_name
            provider.requires_credentials = requires_credentials
            provider.updated_at = utc_now()

    if db.get(RuntimeSettings, RUNTIME_SETTINGS_ID) is None:
        db.add(RuntimeSettings(id=RUNTIME_SETTINGS_ID, active_parser_kind=PARSER_DOCLING))

    db.flush()
    _seed_model_catalog(db)
    db.flush()
    _activate_default_synthesis_if_ready(db)
    db.commit()


def _seed_model_catalog(db: Session) -> None:
    existing = {profile.id: profile for profile in db.scalars(select(ModelProfile))}
    for entry in MODEL_CATALOG:
        profile = existing.get(entry.seed_id)
        if profile is None:
            db.add(
                ModelProfile(
                    id=entry.seed_id,
                    name=entry.name,
                    profile_kind=entry.profile_kind,
                    provider_kind=entry.provider_kind,
                    model_name=entry.model_name,
                    vector_dimensions=entry.vector_dimensions,
                )
            )
        elif profile.name != entry.name:
            profile.name = entry.name
            profile.updated_at = utc_now()


def _activate_default_synthesis_if_ready(db: Session) -> None:
    settings = db.get(RuntimeSettings, RUNTIME_SETTINGS_ID)
    if settings is None:
        settings = RuntimeSettings(id=RUNTIME_SETTINGS_ID, active_parser_kind=PARSER_DOCLING)
        db.add(settings)
        db.flush()
    if settings.active_synthesis_profile_id is not None:
        return

    profile = db.get(ModelProfile, DEFAULT_SYNTHESIS_PROFILE_ID)
    provider = db.get(ProviderConfig, PROVIDER_OPENAI)
    if profile is not None and provider is not None and is_provider_configured(provider):
        settings.active_synthesis_profile_id = profile.id
        settings.updated_at = utc_now()


def is_provider_configured(provider: ProviderConfig) -> bool:
    return not provider.requires_credentials or bool(provider.credential_ciphertext)


def safe_provider(provider: ProviderConfig) -> dict[str, Any]:
    return {"providerKind": provider.provider_kind, "isConfigured": is_provider_configured(provider)}


def safe_model_profile(profile: ModelProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "profileKind": profile.profile_kind,
        "providerKind": profile.provider_kind,
        "modelName": profile.model_name,
        "vectorDimensions": profile.vector_dimensions,
        "isDefault": profile.id in DEFAULT_MODEL_PROFILE_IDS,
    }


def safe_runtime_settings(settings: RuntimeSettings) -> dict[str, Any]:
    return {
        "activeSynthesisProfileId": settings.active_synthesis_profile_id,
        "activeParserKind": settings.active_parser_kind,
    }


def ensure_runtime_settings(db: Session) -> RuntimeSettings:
    settings = db.get(RuntimeSettings, RUNTIME_SETTINGS_ID)
    if settings is None:
        settings = RuntimeSettings(id=RUNTIME_SETTINGS_ID, active_parser_kind=PARSER_DOCLING)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def runtime_settings_snapshot(db: Session) -> dict[str, Any]:
    providers = list(db.scalars(select(ProviderConfig).order_by(ProviderConfig.provider_kind)))
    profiles = list(db.scalars(select(ModelProfile).order_by(ModelProfile.name, ModelProfile.id)))
    settings = ensure_runtime_settings(db)
    return {
        "providers": [safe_provider(provider) for provider in providers],
        "modelProfiles": [safe_model_profile(profile) for profile in profiles],
        "runtimeSettings": safe_runtime_settings(settings),
    }


def _provider_or_error(db: Session, provider_kind: str) -> ProviderConfig:
    if provider_kind not in PROVIDER_KINDS:
        raise RuntimeConfigError(404, "provider_not_found", "Provider not found.")
    provider = db.get(ProviderConfig, provider_kind)
    if provider is None:
        raise RuntimeConfigError(404, "provider_not_found", "Provider not found.")
    return provider


def rotate_provider_credential(
    db: Session,
    provider_kind: str,
    credential: str,
    crypto: SecretCrypto,
    audit_context: AuditContext | None = None,
) -> ProviderConfig:
    provider = _provider_or_error(db, provider_kind)
    if not provider.requires_credentials:
        raise RuntimeConfigError(422, "provider_credentials_unsupported", "Provider does not accept credentials.")
    provider.credential_ciphertext = crypto.encrypt_secret(credential)
    provider.credential_updated_at = utc_now()
    provider.updated_at = provider.credential_updated_at
    _activate_default_synthesis_if_ready(db)
    if audit_context is not None:
        AuditService(db).record(AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED, context=audit_context)
    db.commit()
    db.refresh(provider)
    return provider


def _validate_model_profile(provider_kind: str, profile_kind: str, vector_dimensions: int | None) -> None:
    if profile_kind not in PROFILE_KINDS:
        raise RuntimeConfigError(422, "invalid_profile_kind", "Invalid profile kind.")
    if provider_kind not in MODEL_PROVIDER_KINDS:
        raise RuntimeConfigError(422, "invalid_model_provider", "Invalid model profile provider.")
    if profile_kind == PROFILE_EMBEDDING and vector_dimensions is None:
        raise RuntimeConfigError(422, "vector_dimensions_required", "Embedding profiles require vector dimensions.")
    if profile_kind == PROFILE_SYNTHESIS and vector_dimensions is not None:
        raise RuntimeConfigError(422, "vector_dimensions_not_allowed", "Synthesis profiles do not use vector dimensions.")


def _catalog_entry_for(
    provider_kind: str,
    profile_kind: str,
    model_name: str,
    vector_dimensions: int | None,
) -> ModelCatalogEntry | None:
    for entry in MODEL_CATALOG:
        if (
            entry.provider_kind == provider_kind
            and entry.profile_kind == profile_kind
            and entry.model_name == model_name
            and entry.vector_dimensions == vector_dimensions
        ):
            return entry
    return None


def _validate_model_catalog(provider_kind: str, profile_kind: str, model_name: str, vector_dimensions: int | None) -> None:
    if _catalog_entry_for(provider_kind, profile_kind, model_name, vector_dimensions) is None:
        raise RuntimeConfigError(422, "model_profile_not_in_catalog", "Model profile is not in the approved catalog.")


def _domain_references_model_profile(db: Session, profile_id: str) -> bool:
    bind = db.get_bind()
    try:
        inspector = inspect(bind)
        if not inspector.has_table("domains"):
            return False
        columns = {column["name"] for column in inspector.get_columns("domains")}
        if "embedding_profile_id" not in columns:
            return False
        row = db.execute(
            text("SELECT 1 FROM domains WHERE embedding_profile_id = :profile_id LIMIT 1"),
            {"profile_id": profile_id},
        ).first()
    except SQLAlchemyError:
        return False
    return row is not None


def _reject_if_embedding_profile_in_use(db: Session, profile: ModelProfile) -> None:
    if profile.profile_kind == PROFILE_EMBEDDING and _domain_references_model_profile(db, profile.id):
        raise RuntimeConfigError(409, "model_profile_in_use", "Model profile is in use.")


def create_model_profile(
    db: Session,
    *,
    name: str,
    profile_kind: str,
    provider_kind: str,
    model_name: str,
    vector_dimensions: int | None,
    audit_context: AuditContext | None = None,
) -> ModelProfile:
    _validate_model_profile(provider_kind, profile_kind, vector_dimensions)
    _validate_model_catalog(provider_kind, profile_kind, model_name, vector_dimensions)
    _provider_or_error(db, provider_kind)
    profile = ModelProfile(
        name=name,
        profile_kind=profile_kind,
        provider_kind=provider_kind,
        model_name=model_name,
        vector_dimensions=vector_dimensions,
    )
    db.add(profile)
    if audit_context is not None:
        AuditService(db).record(AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED, context=audit_context)
    db.commit()
    db.refresh(profile)
    return profile


def update_model_profile(
    db: Session,
    profile_id: str,
    updates: dict[str, Any],
    audit_context: AuditContext | None = None,
) -> ModelProfile:
    profile = db.get(ModelProfile, profile_id)
    if profile is None:
        raise RuntimeConfigError(404, "model_profile_not_found", "Model profile not found.")

    _reject_if_embedding_profile_in_use(db, profile)
    next_model_name = updates.get("model_name", profile.model_name)
    next_dimensions = updates.get("vector_dimensions", profile.vector_dimensions)
    if "model_name" in updates or "vector_dimensions" in updates:
        _validate_model_profile(profile.provider_kind, profile.profile_kind, next_dimensions)
        _validate_model_catalog(profile.provider_kind, profile.profile_kind, next_model_name, next_dimensions)

    if "vector_dimensions" in updates:
        profile.vector_dimensions = next_dimensions
    if "name" in updates:
        profile.name = updates["name"]
    if "model_name" in updates:
        profile.model_name = next_model_name
    profile.updated_at = utc_now()
    if audit_context is not None:
        AuditService(db).record(AUDIT_EVENT_RUNTIME_MODEL_PROFILE_UPDATED, context=audit_context)
    db.commit()
    db.refresh(profile)
    return profile


def delete_model_profile(db: Session, profile_id: str, audit_context: AuditContext | None = None) -> None:
    profile = db.get(ModelProfile, profile_id)
    if profile is None:
        raise RuntimeConfigError(404, "model_profile_not_found", "Model profile not found.")
    settings = ensure_runtime_settings(db)
    if settings.active_synthesis_profile_id == profile.id:
        raise RuntimeConfigError(409, "model_profile_in_use", "Model profile is in use.")
    _reject_if_embedding_profile_in_use(db, profile)
    db.delete(profile)
    if audit_context is not None:
        AuditService(db).record(AUDIT_EVENT_RUNTIME_MODEL_PROFILE_DELETED, context=audit_context)
    db.commit()


def _provider_ready_or_error(provider: ProviderConfig) -> None:
    if not is_provider_configured(provider):
        raise RuntimeConfigError(409, "provider_not_ready", "Provider is not configured.")


def update_runtime_settings(
    db: Session,
    updates: dict[str, Any],
    audit_context: AuditContext | None = None,
) -> RuntimeSettings:
    if not updates:
        raise RuntimeConfigError(422, "empty_runtime_settings_patch", "At least one runtime setting is required.")

    settings = ensure_runtime_settings(db)
    if "active_synthesis_profile_id" in updates:
        profile_id = updates["active_synthesis_profile_id"]
        if profile_id is None:
            raise RuntimeConfigError(422, "active_synthesis_required", "Active synthesis profile is required.")
        profile = db.get(ModelProfile, profile_id)
        if profile is None:
            raise RuntimeConfigError(404, "model_profile_not_found", "Model profile not found.")
        if profile.profile_kind != PROFILE_SYNTHESIS:
            raise RuntimeConfigError(422, "invalid_active_synthesis_profile", "Active synthesis profile must be a synthesis profile.")
        provider = _provider_or_error(db, profile.provider_kind)
        _provider_ready_or_error(provider)
        settings.active_synthesis_profile_id = profile.id

    if "active_parser_kind" in updates:
        parser_kind = updates["active_parser_kind"]
        if parser_kind not in PARSER_KINDS:
            raise RuntimeConfigError(422, "invalid_parser_kind", "Invalid parser kind.")
        if parser_kind == PARSER_REDUCTO:
            reducto = _provider_or_error(db, PROVIDER_REDUCTO)
            _provider_ready_or_error(reducto)
        settings.active_parser_kind = parser_kind

    settings.updated_at = utc_now()
    if audit_context is not None:
        AuditService(db).record(AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED, context=audit_context)
    db.commit()
    db.refresh(settings)
    return settings


@dataclass(frozen=True)
class TrustedModelRuntimeConfig:
    profile_id: str
    provider_kind: str
    model_name: str
    credential: str | None


@dataclass(frozen=True)
class TrustedEmbeddingRuntimeConfig:
    profile_id: str
    provider_kind: str
    model_name: str
    vector_dimensions: int
    credential: str | None


@dataclass(frozen=True)
class TrustedParserRuntimeConfig:
    parser_kind: str
    credential: str | None


@dataclass(frozen=True)
class TrustedRuntimeConfig:
    synthesis: TrustedModelRuntimeConfig
    parser: TrustedParserRuntimeConfig


class TrustedRuntimeResolver:
    def __init__(self, db: Session, crypto: SecretCrypto) -> None:
        self._db = db
        self._crypto = crypto

    def resolve(self) -> TrustedRuntimeConfig:
        settings = ensure_runtime_settings(self._db)
        if settings.active_synthesis_profile_id is None:
            raise RuntimeConfigError(409, "runtime_settings_not_ready", "Runtime settings are not ready.")

        profile = self._db.get(ModelProfile, settings.active_synthesis_profile_id)
        if profile is None or profile.profile_kind != PROFILE_SYNTHESIS:
            raise RuntimeConfigError(409, "runtime_settings_not_ready", "Runtime settings are not ready.")
        provider = _provider_or_error(self._db, profile.provider_kind)
        _provider_ready_or_error(provider)
        synthesis = TrustedModelRuntimeConfig(
            profile_id=profile.id,
            provider_kind=provider.provider_kind,
            model_name=profile.model_name,
            credential=self._credential_for(provider),
        )

        parser_credential = None
        if settings.active_parser_kind == PARSER_REDUCTO:
            reducto = _provider_or_error(self._db, PROVIDER_REDUCTO)
            _provider_ready_or_error(reducto)
            parser_credential = self._credential_for(reducto)
        parser = TrustedParserRuntimeConfig(parser_kind=settings.active_parser_kind, credential=parser_credential)
        return TrustedRuntimeConfig(synthesis=synthesis, parser=parser)

    def resolve_embedding_profile(self, embedding_profile_id: str) -> TrustedEmbeddingRuntimeConfig:
        profile = self._db.get(ModelProfile, embedding_profile_id)
        if profile is None:
            raise RuntimeConfigError(404, "embedding_profile_not_found", "Embedding profile not found.")
        if profile.profile_kind != PROFILE_EMBEDDING or profile.vector_dimensions is None:
            raise RuntimeConfigError(400, "embedding_profile_invalid", "Embedding profile is invalid.")
        provider = _provider_or_error(self._db, profile.provider_kind)
        if not is_provider_configured(provider):
            raise RuntimeConfigError(400, "embedding_profile_invalid", "Embedding profile is invalid.")
        return TrustedEmbeddingRuntimeConfig(
            profile_id=profile.id,
            provider_kind=provider.provider_kind,
            model_name=profile.model_name,
            vector_dimensions=profile.vector_dimensions,
            credential=self._credential_for(provider),
        )

    def _credential_for(self, provider: ProviderConfig) -> str | None:
        if not provider.requires_credentials:
            return None
        if not provider.credential_ciphertext:
            raise RuntimeConfigError(409, "provider_not_ready", "Provider is not configured.")
        return self._crypto.decrypt_secret(provider.credential_ciphertext)
