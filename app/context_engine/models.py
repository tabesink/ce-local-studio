from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from context_engine.db import Base, utc_now

ROLE_ADMINISTRATOR = "administrator"
ROLE_MEMBER = "member"

PROVIDER_OPENAI = "openai"
PROVIDER_BEDROCK = "bedrock"
PROVIDER_OLLAMA = "ollama"
PROVIDER_REDUCTO = "reducto"
PROVIDER_KINDS = (PROVIDER_OPENAI, PROVIDER_BEDROCK, PROVIDER_OLLAMA, PROVIDER_REDUCTO)
MODEL_PROVIDER_KINDS = (PROVIDER_OPENAI, PROVIDER_BEDROCK, PROVIDER_OLLAMA)
PROFILE_SYNTHESIS = "synthesis"
PROFILE_EMBEDDING = "embedding"
PROFILE_KINDS = (PROFILE_SYNTHESIS, PROFILE_EMBEDDING)
PARSER_DOCLING = "docling"
PARSER_REDUCTO = "reducto"
PARSER_KINDS = (PARSER_DOCLING, PARSER_REDUCTO)
DOMAIN_STATE_STOPPED = "stopped"
DOMAIN_STATE_RUNNING = "running"
DOMAIN_STATE_DELETING = "deleting"
DOMAIN_STATES = (DOMAIN_STATE_STOPPED, DOMAIN_STATE_RUNNING, DOMAIN_STATE_DELETING)
DOMAIN_OPERATION_CREATE = "create"
DOMAIN_OPERATION_START = "start"
DOMAIN_OPERATION_STOP = "stop"
DOMAIN_OPERATION_DELETE = "delete"
DOMAIN_OPERATION_TYPES = (
    DOMAIN_OPERATION_CREATE,
    DOMAIN_OPERATION_START,
    DOMAIN_OPERATION_STOP,
    DOMAIN_OPERATION_DELETE,
)
DOMAIN_OPERATION_STATUS_QUEUED = "queued"
DOMAIN_OPERATION_STATUS_RUNNING = "running"
DOMAIN_OPERATION_STATUS_SUCCEEDED = "succeeded"
DOMAIN_OPERATION_STATUS_FAILED = "failed"
DOMAIN_OPERATION_STATUS_CANCELLED = "cancelled"
DOMAIN_OPERATION_STATUSES = (
    DOMAIN_OPERATION_STATUS_QUEUED,
    DOMAIN_OPERATION_STATUS_RUNNING,
    DOMAIN_OPERATION_STATUS_SUCCEEDED,
    DOMAIN_OPERATION_STATUS_FAILED,
    DOMAIN_OPERATION_STATUS_CANCELLED,
)
DOMAIN_OPERATION_ACTIVE_STATUSES = (DOMAIN_OPERATION_STATUS_QUEUED, DOMAIN_OPERATION_STATUS_RUNNING)
SOURCE_STATE_PENDING = "pending"
SOURCE_STATE_PREPARED = "prepared"
SOURCE_STATE_DELETING = "deleting"
SOURCE_STATES = (SOURCE_STATE_PENDING, SOURCE_STATE_PREPARED, SOURCE_STATE_DELETING)
SOURCE_PREP_OPERATION_PREPARE = "prepare"
SOURCE_PREP_OPERATION_TYPES = (SOURCE_PREP_OPERATION_PREPARE,)
SOURCE_PREP_STATUS_QUEUED = "queued"
SOURCE_PREP_STATUS_RUNNING = "running"
SOURCE_PREP_STATUS_SUCCEEDED = "succeeded"
SOURCE_PREP_STATUS_FAILED = "failed"
SOURCE_PREP_STATUS_CANCELLED = "cancelled"
SOURCE_PREP_STATUSES = (
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_PREP_STATUS_RUNNING,
    SOURCE_PREP_STATUS_SUCCEEDED,
    SOURCE_PREP_STATUS_FAILED,
    SOURCE_PREP_STATUS_CANCELLED,
)
SOURCE_PREP_ACTIVE_STATUSES = (SOURCE_PREP_STATUS_QUEUED, SOURCE_PREP_STATUS_RUNNING)
SOURCE_BLOCK_KIND_TEXT = "text"
SOURCE_BLOCK_KIND_TABLE = "table"
SOURCE_BLOCK_KIND_FIGURE = "figure"
SOURCE_BLOCK_KINDS = (SOURCE_BLOCK_KIND_TEXT, SOURCE_BLOCK_KIND_TABLE, SOURCE_BLOCK_KIND_FIGURE)
SOURCE_INDEX_STATE_NOT_REQUESTED = "not_requested"
SOURCE_INDEX_STATE_QUEUED = "queued"
SOURCE_INDEX_STATE_SUBMITTING = "submitting"
SOURCE_INDEX_STATE_ACCEPTED = "accepted"
SOURCE_INDEX_STATE_READY = "ready"
SOURCE_INDEX_STATE_FAILED = "failed"
SOURCE_INDEX_STATE_CANCELLING = "cancelling"
SOURCE_INDEX_STATE_CANCELLED = "cancelled"
SOURCE_INDEX_STATES = (
    SOURCE_INDEX_STATE_NOT_REQUESTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_FAILED,
    SOURCE_INDEX_STATE_CANCELLING,
    SOURCE_INDEX_STATE_CANCELLED,
)
SOURCE_INDEX_ACTIVE_STATES = (
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLING,
)
SOURCE_INDEX_REMOTE_STATES = (
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_READY,
)
TURN_ROUTE_DIRECT_LLM = "direct_llm"
TURN_ROUTE_DOMAIN_RAG = "domain_rag"
TURN_ROUTES = (TURN_ROUTE_DIRECT_LLM, TURN_ROUTE_DOMAIN_RAG)
TURN_STATUS_RUNNING = "running"
TURN_STATUS_COMPLETED = "completed"
TURN_STATUS_FAILED = "failed"
TURN_STATUS_REDACTED = "redacted"
TURN_STATUSES = (TURN_STATUS_RUNNING, TURN_STATUS_COMPLETED, TURN_STATUS_FAILED, TURN_STATUS_REDACTED)
TURN_STOP_REASON_DIRECT_LLM = "direct_llm"
TURN_STOP_REASON_GROUNDED = "grounded"
TURN_STOP_REASON_NO_GROUNDED_CONTEXT = "no_grounded_context"
TURN_STOP_REASON_EVIDENCE_ONLY = "evidence_only"
TURN_STOP_REASON_TURN_BUDGET_EXHAUSTED = "turn_budget_exhausted"
TURN_STOP_REASON_PROVIDER_FAILURE = "provider_failure"
TURN_STOP_REASON_CITATION_VALIDATION_FAILED = "citation_validation_failed"
TURN_STOP_REASON_CANCELLED = "cancelled"
TURN_STOP_REASON_REDACTED = "redacted"
TURN_STOP_REASONS = (
    TURN_STOP_REASON_DIRECT_LLM,
    TURN_STOP_REASON_GROUNDED,
    TURN_STOP_REASON_NO_GROUNDED_CONTEXT,
    TURN_STOP_REASON_EVIDENCE_ONLY,
    TURN_STOP_REASON_TURN_BUDGET_EXHAUSTED,
    TURN_STOP_REASON_PROVIDER_FAILURE,
    TURN_STOP_REASON_CITATION_VALIDATION_FAILED,
    TURN_STOP_REASON_CANCELLED,
    TURN_STOP_REASON_REDACTED,
)
EMPTY_COMPOSER_REF_FINGERPRINT = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
COMPOSER_REF_KIND_SOURCE = "source"
COMPOSER_REF_KIND_EVIDENCE = "evidence"
COMPOSER_REF_KIND_TEMPLATE = "template"
COMPOSER_REF_KINDS = (
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_TEMPLATE,
)
PROMPT_TEMPLATE_STATE_APPROVED = "approved"
PROMPT_TEMPLATE_STATE_DISABLED = "disabled"
PROMPT_TEMPLATE_STATES = (PROMPT_TEMPLATE_STATE_APPROVED, PROMPT_TEMPLATE_STATE_DISABLED)
AUDIT_ACTOR_PUBLIC = "public"
AUDIT_ACTOR_MEMBER = "member"
AUDIT_ACTOR_ADMINISTRATOR = "administrator"
AUDIT_ACTOR_WORKER = "worker"
AUDIT_ACTOR_SYSTEM = "system"
AUDIT_ACTOR_KINDS = (
    AUDIT_ACTOR_PUBLIC,
    AUDIT_ACTOR_MEMBER,
    AUDIT_ACTOR_ADMINISTRATOR,
    AUDIT_ACTOR_WORKER,
    AUDIT_ACTOR_SYSTEM,
)
AUDIT_OUTCOME_SUCCEEDED = "succeeded"
AUDIT_OUTCOME_FAILED = "failed"
AUDIT_OUTCOME_DENIED = "denied"
AUDIT_OUTCOMES = (AUDIT_OUTCOME_SUCCEEDED, AUDIT_OUTCOME_FAILED, AUDIT_OUTCOME_DENIED)
AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED = "runtime_settings.provider_config_rotated"
AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED = "runtime_settings.model_profile_created"
AUDIT_EVENT_RUNTIME_MODEL_PROFILE_UPDATED = "runtime_settings.model_profile_updated"
AUDIT_EVENT_RUNTIME_MODEL_PROFILE_DELETED = "runtime_settings.model_profile_deleted"
AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED = "runtime_settings.defaults_updated"
AUDIT_EVENT_DOMAIN_CREATED = "domain.created"
AUDIT_EVENT_DOMAIN_STARTED = "domain.started"
AUDIT_EVENT_DOMAIN_STOPPED = "domain.stopped"
AUDIT_EVENT_DOMAIN_DELETE_QUEUED = "domain.delete_queued"
AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED = "domain.delete_succeeded"
AUDIT_EVENT_DOMAIN_DELETE_FAILED = "domain.delete_failed"
AUDIT_EVENT_SOURCE_UPLOADED = "source.uploaded"
AUDIT_EVENT_SOURCE_PREPARATION_RETRIED = "source.preparation_retried"
AUDIT_EVENT_SOURCE_PREPARATION_CANCELLED = "source.preparation_cancelled"
AUDIT_EVENT_SOURCE_DELETED = "source.deleted"
AUDIT_EVENT_SOURCE_INDEX_RETRY_QUEUED = "source.index_retry_queued"
AUDIT_EVENT_SOURCE_INDEX_CANCELLED = "source.index_cancelled"
AUDIT_EVENT_CHAT_TURN_REDACTED = "chat.turn_redacted"
AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED = "security.admin_route_denied"
AUDIT_EVENT_USER_DISABLED = "user.disabled"
AUDIT_EVENT_USER_ENABLED = "user.enabled"
AUDIT_EVENT_NAMES = (
    AUDIT_EVENT_RUNTIME_PROVIDER_CONFIG_ROTATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_CREATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_UPDATED,
    AUDIT_EVENT_RUNTIME_MODEL_PROFILE_DELETED,
    AUDIT_EVENT_RUNTIME_DEFAULTS_UPDATED,
    AUDIT_EVENT_DOMAIN_CREATED,
    AUDIT_EVENT_DOMAIN_STARTED,
    AUDIT_EVENT_DOMAIN_STOPPED,
    AUDIT_EVENT_DOMAIN_DELETE_QUEUED,
    AUDIT_EVENT_DOMAIN_DELETE_SUCCEEDED,
    AUDIT_EVENT_DOMAIN_DELETE_FAILED,
    AUDIT_EVENT_SOURCE_UPLOADED,
    AUDIT_EVENT_SOURCE_PREPARATION_RETRIED,
    AUDIT_EVENT_SOURCE_PREPARATION_CANCELLED,
    AUDIT_EVENT_SOURCE_DELETED,
    AUDIT_EVENT_SOURCE_INDEX_RETRY_QUEUED,
    AUDIT_EVENT_SOURCE_INDEX_CANCELLED,
    AUDIT_EVENT_CHAT_TURN_REDACTED,
    AUDIT_EVENT_SECURITY_ADMIN_ROUTE_DENIED,
    AUDIT_EVENT_USER_DISABLED,
    AUDIT_EVENT_USER_ENABLED,
)
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ROLE_MEMBER)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class ProviderConfig(Base):
    __tablename__ = "provider_configs"
    __table_args__ = (
        CheckConstraint("provider_kind in ('openai', 'bedrock', 'ollama', 'reducto')", name="ck_provider_configs_provider_kind"),
    )

    provider_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    requires_credentials: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        CheckConstraint("profile_kind in ('synthesis', 'embedding')", name="ck_model_profiles_profile_kind"),
        CheckConstraint("provider_kind in ('openai', 'bedrock', 'ollama')", name="ck_model_profiles_provider_kind"),
        CheckConstraint("profile_kind != 'embedding' or vector_dimensions is not null", name="ck_model_profiles_embedding_dimensions_required"),
        CheckConstraint("profile_kind != 'synthesis' or vector_dimensions is null", name="ck_model_profiles_synthesis_dimensions_absent"),
        CheckConstraint("vector_dimensions is null or vector_dimensions > 0", name="ck_model_profiles_vector_dimensions_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_kind: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("provider_configs.provider_kind"),
        index=True,
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    vector_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)


class RuntimeSettings(Base):
    __tablename__ = "runtime_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_runtime_settings_singleton"),
        CheckConstraint("active_parser_kind in ('docling', 'reducto')", name="ck_runtime_settings_active_parser_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_synthesis_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("model_profiles.id"),
        nullable=True,
    )
    active_parser_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=PARSER_DOCLING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (
        CheckConstraint("state in ('stopped', 'running', 'deleting')", name="ck_domains_state"),
        CheckConstraint("control_generation >= 1", name="ck_domains_control_generation_positive"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=DOMAIN_STATE_STOPPED)
    embedding_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("model_profiles.id"),
        index=True,
        nullable=False,
    )
    runtime_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    control_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    embedding_profile: Mapped[ModelProfile] = relationship()
    operations: Mapped[list["DomainOperation"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sources: Mapped[list["SourceDocument"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DomainOperation(Base):
    __tablename__ = "domain_operations"
    __table_args__ = (
        CheckConstraint("operation_type in ('create', 'start', 'stop', 'delete')", name="ck_domain_operations_type"),
        CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_domain_operations_status",
        ),
        Index("ix_domain_operations_domain_created", "domain_id", text("created_at DESC")),
        Index(
            "uq_domain_operations_one_active",
            "domain_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    control_generation_at_start: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    domain: Mapped[Domain] = relationship(back_populates="operations")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint("state in ('pending', 'prepared', 'deleting')", name="ck_source_documents_state"),
        CheckConstraint("parser_kind in ('docling', 'reducto')", name="ck_source_documents_parser_kind"),
        CheckConstraint(
            "index_state in ('not_requested', 'queued', 'submitting', 'accepted', 'ready', 'failed', 'cancelling', 'cancelled')",
            name="ck_source_documents_index_state",
        ),
        CheckConstraint("original_size_bytes > 0", name="ck_source_documents_size_positive"),
        CheckConstraint("preparation_generation >= 1", name="ck_source_documents_generation_positive"),
        CheckConstraint("index_generation >= 0", name="ck_source_documents_index_generation_nonnegative"),
        Index("uq_source_documents_domain_hash", "domain_id", "original_sha256", unique=True),
        Index("ix_source_documents_domain_created", "domain_id", text("created_at DESC")),
        Index("ix_source_documents_domain_index_state", "domain_id", "index_state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_STATE_PENDING)
    parser_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    preparation_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    index_state: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_INDEX_STATE_NOT_REQUESTED)
    index_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    index_request_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    index_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_remote_document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    index_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    index_lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    index_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    index_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    index_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    domain: Mapped[Domain] = relationship(back_populates="sources")
    operations: Mapped[list["SourcePreparationOperation"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    blocks: Mapped[list["SourceBlock"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    images: Mapped[list["SourceImage"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SourcePreparationOperation(Base):
    __tablename__ = "source_preparation_operations"
    __table_args__ = (
        CheckConstraint("operation_type in ('prepare')", name="ck_source_preparation_operations_type"),
        CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_source_preparation_operations_status",
        ),
        CheckConstraint("preparation_generation_at_start >= 1", name="ck_source_preparation_operations_generation_positive"),
        Index("ix_source_preparation_operations_domain_created", "domain_id", text("created_at DESC")),
        Index("ix_source_preparation_operations_source_created", "source_document_id", text("created_at DESC")),
        Index(
            "uq_source_preparation_operations_one_active",
            "source_document_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_PREP_OPERATION_PREPARE)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    preparation_generation_at_start: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    source_document: Mapped[SourceDocument] = relationship(back_populates="operations")


class SourceBlock(Base):
    __tablename__ = "source_blocks"
    __table_args__ = (
        CheckConstraint("source_order >= 1", name="ck_source_blocks_order_positive"),
        CheckConstraint("kind in ('text', 'table', 'figure')", name="ck_source_blocks_kind"),
        CheckConstraint("heading_level is null or heading_level >= 1", name="ck_source_blocks_heading_positive"),
        CheckConstraint("page_start is null or page_start >= 1", name="ck_source_blocks_page_start_positive"),
        CheckConstraint("page_end is null or page_end >= 1", name="ck_source_blocks_page_end_positive"),
        CheckConstraint("page_start is null or page_end is null or page_end >= page_start", name="ck_source_blocks_page_range"),
        Index("uq_source_blocks_source_order", "source_document_id", "source_order", unique=True),
        Index("ix_source_blocks_domain_source", "domain_id", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    canonical_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    heading_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    source_document: Mapped[SourceDocument] = relationship(back_populates="blocks")
    images: Mapped[list["SourceImage"]] = relationship(
        back_populates="source_block",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SourceImage(Base):
    __tablename__ = "source_images"
    __table_args__ = (
        CheckConstraint("page_number is null or page_number >= 1", name="ck_source_images_page_positive"),
        Index("ix_source_images_source_block", "source_document_id", "source_block_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_block_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_blocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    source_document: Mapped[SourceDocument] = relationship(back_populates="images")
    source_block: Mapped[SourceBlock] = relationship(back_populates="images")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_owner_updated", "owner_user_id", text("updated_at DESC")),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    owner: Mapped[User] = relationship()
    turns: Mapped[list["ConversationTurn"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (
        CheckConstraint(f"route in {TURN_ROUTES}", name="ck_conversation_turns_route"),
        CheckConstraint(f"status in {TURN_STATUSES}", name="ck_conversation_turns_status"),
        CheckConstraint(
            "stop_reason is null or stop_reason in "
            "('direct_llm', 'grounded', 'no_grounded_context', 'evidence_only', "
            "'turn_budget_exhausted', 'provider_failure', 'citation_validation_failed', "
            "'cancelled', 'redacted')",
            name="ck_conversation_turns_stop_reason",
        ),
        CheckConstraint("plan_step_count >= 0", name="ck_conversation_turns_plan_step_count_nonnegative"),
        CheckConstraint(
            "retrieval_operation_count >= 0",
            name="ck_conversation_turns_retrieval_operation_count_nonnegative",
        ),
        CheckConstraint("repair_attempt_count >= 0", name="ck_conversation_turns_repair_attempt_count_nonnegative"),
        CheckConstraint(
            "(route = 'domain_rag' and domain_id is not null) or (route = 'direct_llm' and domain_id is null)",
            name="ck_conversation_turns_route_domain",
        ),
        Index("ix_conversation_turns_conversation_created", "conversation_id", text("created_at DESC")),
        Index("uq_conversation_turns_client_request", "conversation_id", "client_request_id", unique=True),
        Index(
            "uq_conversation_turns_one_running",
            "conversation_id",
            unique=True,
            sqlite_where=text("status = 'running'"),
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    domain_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    route: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_message: Mapped[str] = mapped_column(Text(), nullable=False)
    assistant_answer: Mapped[str | None] = mapped_column(Text(), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    composer_ref_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=EMPTY_COMPOSER_REF_FINGERPRINT,
    )
    plan_step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_operation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")
    evidence_refs: Mapped[list["ConversationTurnEvidenceRef"]] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    composer_refs: Mapped[list["ConversationTurnComposerRef"]] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationTurnComposerRef.ref_order",
    )


class ConversationTurnEvidenceRef(Base):
    __tablename__ = "conversation_turn_evidence_refs"
    __table_args__ = (
        CheckConstraint("evidence_order >= 1", name="ck_conversation_turn_evidence_refs_order_positive"),
        CheckConstraint(
            "(redacted_at IS NULL) OR (citation_label IS NULL AND source_label IS NULL AND excerpt IS NULL)",
            name="ck_conversation_turn_evidence_refs_redacted_fields",
        ),
        Index("uq_conversation_turn_evidence_refs_order", "turn_id", "evidence_order", unique=True),
        Index(
            "uq_conversation_turn_evidence_refs_citation_label",
            "turn_id",
            "citation_label",
            unique=True,
            sqlite_where=text("redacted_at IS NULL"),
            postgresql_where=text("redacted_at IS NULL"),
        ),
        Index("ix_conversation_turn_evidence_refs_source_document", "source_document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    turn_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversation_turns.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_block_id: Mapped[str] = mapped_column(String(36), nullable=False)
    citation_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    turn: Mapped[ConversationTurn] = relationship(back_populates="evidence_refs")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_prompt_templates_name_not_blank"),
        CheckConstraint("length(body) > 0 and length(body) <= 2000", name="ck_prompt_templates_body_size"),
        CheckConstraint(f"state in {PROMPT_TEMPLATE_STATES}", name="ck_prompt_templates_state"),
        Index("uq_prompt_templates_name", "name", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=PROMPT_TEMPLATE_STATE_APPROVED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now)


class ComposerRefToken(Base):
    __tablename__ = "composer_ref_tokens"
    __table_args__ = (
        CheckConstraint(f"ref_kind in {COMPOSER_REF_KINDS}", name="ck_composer_ref_tokens_kind"),
        CheckConstraint("length(token_hash) = 64", name="ck_composer_ref_tokens_hash_size"),
        Index("uq_composer_ref_tokens_hash", "token_hash", unique=True),
        Index("ix_composer_ref_tokens_owner_expires", "owner_user_id", "expires_at"),
        Index("ix_composer_ref_tokens_target", "ref_kind", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ref_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    safe_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    owner: Mapped[User] = relationship()


class ConversationTurnComposerRef(Base):
    __tablename__ = "conversation_turn_composer_refs"
    __table_args__ = (
        CheckConstraint("ref_order >= 1", name="ck_conversation_turn_composer_refs_order_positive"),
        CheckConstraint(f"ref_kind in {COMPOSER_REF_KINDS}", name="ck_conversation_turn_composer_refs_kind"),
        CheckConstraint(
            "(redacted_at IS NULL) OR (safe_label IS NULL AND safe_description IS NULL)",
            name="ck_conversation_turn_composer_refs_redacted_fields",
        ),
        CheckConstraint(
            "(ref_kind = 'source' AND source_document_id IS NOT NULL AND evidence_ref_id IS NULL "
            "AND prompt_template_id IS NULL) OR "
            "(ref_kind = 'evidence' AND evidence_ref_id IS NOT NULL AND source_document_id IS NULL "
            "AND source_block_id IS NULL AND prompt_template_id IS NULL) OR "
            "(ref_kind = 'template' AND prompt_template_id IS NOT NULL AND source_document_id IS NULL "
            "AND source_block_id IS NULL AND evidence_ref_id IS NULL)",
            name="ck_conversation_turn_composer_refs_kind_target",
        ),
        Index("uq_conversation_turn_composer_refs_order", "turn_id", "ref_order", unique=True),
        Index("ix_conversation_turn_composer_refs_turn_kind", "turn_id", "ref_kind"),
        Index("ix_conversation_turn_composer_refs_source_document", "source_document_id"),
        Index("ix_conversation_turn_composer_refs_evidence_ref", "evidence_ref_id"),
        Index("ix_conversation_turn_composer_refs_template", "prompt_template_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    turn_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversation_turns.id", ondelete="CASCADE"),
        nullable=False,
    )
    ref_order: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    safe_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    safe_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_block_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence_ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    turn: Mapped[ConversationTurn] = relationship(back_populates="composer_refs")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            f"event_name in {AUDIT_EVENT_NAMES}",
            name="ck_audit_events_event_name",
        ),
        CheckConstraint(f"actor_kind in {AUDIT_ACTOR_KINDS}", name="ck_audit_events_actor_kind"),
        CheckConstraint(f"outcome in {AUDIT_OUTCOMES}", name="ck_audit_events_outcome"),
        Index("ix_audit_events_created_at", text("created_at DESC")),
        Index("ix_audit_events_event_created", "event_name", text("created_at DESC")),
        Index("ix_audit_events_actor_created", "actor_user_id", text("created_at DESC")),
        Index("ix_audit_events_target_created", "target_kind", "target_id", text("created_at DESC")),
        Index("ix_audit_events_request_id", "request_id"),
        Index("ix_audit_events_trace_id", "trace_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    actor: Mapped[User | None] = relationship()
