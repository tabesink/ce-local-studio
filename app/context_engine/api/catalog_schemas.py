from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import models_json_schema

OpaqueRef = Annotated[str, Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
CONVERSATION_PUBLIC_REF_PATTERN = r"^conv_[0-9a-f]{32}$"
TURN_PUBLIC_REF_PATTERN = r"^turn_[0-9a-f]{32}$"
SafeLabel = Annotated[str, Field(min_length=1, max_length=255)]
SafeMessage = Annotated[str, Field(min_length=1, max_length=500)]
UtcTimestamp = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
Version = Annotated[int, Field(gt=0)]

Role = Literal["member", "administrator"]
DomainState = Literal["stopped", "running", "deleting"]
OperationStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SourceState = Literal["pending", "prepared", "deleting"]
IndexState = Literal["not_requested", "queued", "processing", "ready", "failed", "cancelled", "deleting"]
TurnRoute = Literal["direct_llm", "domain_rag"]
TurnStatus = Literal["running", "completed", "failed", "cancelled", "redacted"]
EvidenceKind = Literal["text", "table", "figure"]


class PublicDto(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AllowedAction(PublicDto):
    action: str = Field(min_length=1, max_length=120)
    enabled: bool
    reason_code: str | None = Field(default=None, alias="reasonCode", min_length=1, max_length=120)


class CurrentUserDto(PublicDto):
    id: OpaqueRef
    display_name: SafeLabel = Field(alias="displayName")
    role: Role
    disabled: Literal[False]


class ProviderSummaryDto(PublicDto):
    kind: Literal["openai", "bedrock", "ollama", "reducto"]
    display_name: SafeLabel = Field(alias="displayName")
    requires_credentials: bool = Field(alias="requiresCredentials")
    configured: bool
    credential_updated_at: UtcTimestamp | None = Field(alias="credentialUpdatedAt")
    version: Version


class ModelProfileDto(PublicDto):
    id: OpaqueRef
    name: SafeLabel
    profile_kind: Literal["synthesis", "embedding"] = Field(alias="profileKind")
    provider_kind: Literal["openai", "bedrock", "ollama"] = Field(alias="providerKind")
    model_name: str = Field(alias="modelName", min_length=1, max_length=200)
    vector_dimensions: int | None = Field(alias="vectorDimensions", gt=0)
    in_use: bool = Field(alias="inUse")
    version: Version


class RuntimeSettingsDto(PublicDto):
    active_synthesis_profile_id: OpaqueRef | None = Field(alias="activeSynthesisProfileId")
    active_parser_kind: Literal["docling", "reducto"] = Field(alias="activeParserKind")
    version: Version


class DomainSummaryDto(PublicDto):
    id: OpaqueRef
    display_name: SafeLabel = Field(alias="displayName")
    state: DomainState
    query_eligible: bool = Field(alias="queryEligible")


class EmbeddingProfileSummaryDto(PublicDto):
    id: OpaqueRef
    name: SafeLabel
    vector_dimensions: int = Field(alias="vectorDimensions", gt=0)


class AdminDomainDto(DomainSummaryDto):
    embedding_profile: EmbeddingProfileSummaryDto = Field(alias="embeddingProfile")
    runtime_ready: bool = Field(alias="runtimeReady")
    control_generation: int = Field(alias="controlGeneration", ge=0)
    active_operation_id: OpaqueRef | None = Field(alias="activeOperationId")
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")
    version: Version
    allowed_actions: list[AllowedAction] = Field(alias="allowedActions")


class OperationErrorDto(PublicDto):
    code: str = Field(min_length=1, max_length=120)
    message: SafeMessage


class OperationDto(PublicDto):
    id: OpaqueRef
    target_kind: Literal["domain", "source", "index"] = Field(alias="targetKind")
    target_ref: OpaqueRef = Field(alias="targetRef")
    operation_type: str = Field(alias="operationType", min_length=1, max_length=120)
    status: OperationStatus
    generation: int = Field(ge=0)
    message: SafeMessage | None
    error: OperationErrorDto | None
    requested_at: UtcTimestamp = Field(alias="requestedAt")
    started_at: UtcTimestamp | None = Field(alias="startedAt")
    finished_at: UtcTimestamp | None = Field(alias="finishedAt")
    version: Version
    allowed_actions: list[AllowedAction] = Field(alias="allowedActions")


class AdminSourceDto(PublicDto):
    id: OpaqueRef
    document_ref: OpaqueRef = Field(alias="documentRef")
    domain_id: OpaqueRef = Field(alias="domainId")
    display_name: SafeLabel = Field(alias="displayName")
    content_type: str = Field(alias="contentType", min_length=1, max_length=255)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    state: SourceState
    parser_kind: Literal["docling", "reducto"] = Field(alias="parserKind")
    index_state: IndexState = Field(alias="indexState")
    active_operation_id: OpaqueRef | None = Field(alias="activeOperationId")
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")
    version: Version
    allowed_actions: list[AllowedAction] = Field(alias="allowedActions")


class OutlineItemDto(PublicDto):
    kind: Literal["heading", "figure", "table"]
    label: SafeLabel
    level: int | None = Field(default=None, ge=1)
    page_number: int | None = Field(default=None, alias="pageNumber", ge=1)


class DocumentSummaryDto(PublicDto):
    ref: OpaqueRef
    label: SafeLabel
    domain: DomainSummaryDto
    content_type: Literal["application/pdf"] = Field(alias="contentType")
    preview_kind: Literal["pdf", "unavailable"] = Field(alias="previewKind")
    page_count: int | None = Field(alias="pageCount", gt=0)
    updated_at: UtcTimestamp = Field(alias="updatedAt")


class ConversationSummaryDto(PublicDto):
    id: OpaqueRef
    title: str | None = Field(max_length=120)
    created_at: UtcTimestamp = Field(alias="createdAt")
    updated_at: UtcTimestamp = Field(alias="updatedAt")
    version: Version


class AcceptedRefDto(PublicDto):
    id: OpaqueRef
    kind: Literal["source", "evidence", "template"]
    order: int = Field(ge=0)
    label: SafeLabel
    description: SafeMessage | None


class EvidenceRegionDto(PublicDto):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class EvidenceAnchorDto(PublicDto):
    page_number: int = Field(alias="pageNumber", ge=1)
    region: EvidenceRegionDto | None = None
    section_label: str | None = Field(default=None, alias="sectionLabel", min_length=1, max_length=160)
    fallback: Literal["region", "section", "page"]


class EvidenceItemDto(PublicDto):
    id: OpaqueRef
    citation_label: str = Field(alias="citationLabel", min_length=1, max_length=32)
    source_label: SafeLabel = Field(alias="sourceLabel")
    excerpt: str = Field(min_length=1, max_length=500)
    kind: EvidenceKind
    document_ref: OpaqueRef = Field(alias="documentRef")
    document_label: SafeLabel = Field(alias="documentLabel")
    anchor: EvidenceAnchorDto


class EvidenceLocationEvidenceDto(PublicDto):
    id: OpaqueRef
    citation_label: str = Field(alias="citationLabel", min_length=1, max_length=32)
    kind: EvidenceKind


class EvidenceLocationDocumentDto(PublicDto):
    ref: OpaqueRef
    label: SafeLabel
    preview_kind: Literal["pdf", "unavailable"] = Field(alias="previewKind")
    page_count: int | None = Field(alias="pageCount", gt=0)


class EvidenceLocationResponseDto(PublicDto):
    evidence: EvidenceLocationEvidenceDto
    document: EvidenceLocationDocumentDto
    anchor: EvidenceAnchorDto


class RetrievalEvidenceRequestDto(PublicDto):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class RetrievalEvidenceAnchorDto(PublicDto):
    page_number: int = Field(alias="pageNumber", ge=1)
    section_label: str | None = Field(default=None, alias="sectionLabel", min_length=1, max_length=160)
    fallback: Literal["section", "page"]


class RetrievalEvidenceItemDto(PublicDto):
    citation_label: str = Field(alias="citationLabel", min_length=1, max_length=32)
    source_label: SafeLabel = Field(alias="sourceLabel")
    excerpt: str = Field(min_length=1, max_length=500)
    kind: EvidenceKind
    document_ref: OpaqueRef = Field(alias="documentRef")
    document_label: SafeLabel = Field(alias="documentLabel")
    anchor: RetrievalEvidenceAnchorDto | None


class RetrievalEvidenceResponseDto(PublicDto):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "oneOf": [
                {
                    "properties": {
                        "result": {"const": "evidence_found"},
                        "evidence": {"minItems": 1},
                    }
                },
                {
                    "properties": {
                        "result": {"const": "no_grounded_context"},
                        "evidence": {"maxItems": 0},
                    }
                },
            ]
        },
    )

    result: Literal["evidence_found", "no_grounded_context"]
    evidence: list[RetrievalEvidenceItemDto]

    @model_validator(mode="after")
    def validate_result_consistency(self) -> Self:
        if self.result == "evidence_found" and not self.evidence:
            raise ValueError("evidence_found requires at least one evidence item")
        if self.result == "no_grounded_context" and self.evidence:
            raise ValueError("no_grounded_context requires an empty evidence list")
        return self


class TurnErrorDto(PublicDto):
    code: str = Field(min_length=1, max_length=120)
    message: SafeMessage
    retryable: bool


class TurnDto(PublicDto):
    id: OpaqueRef
    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=80)
    route: TurnRoute
    status: TurnStatus
    domain: DomainSummaryDto | None
    user_message: str = Field(alias="userMessage", min_length=1, max_length=4000)
    assistant_answer: str | None = Field(alias="assistantAnswer")
    evidence: list[EvidenceItemDto]
    accepted_refs: list[AcceptedRefDto] = Field(alias="acceptedRefs")
    error: TurnErrorDto | None
    created_at: UtcTimestamp = Field(alias="createdAt")
    completed_at: UtcTimestamp | None = Field(alias="completedAt")


class ConversationDetailResponseDto(PublicDto):
    conversation: ConversationSummaryDto
    turns: list[TurnDto]


class ComposerRefDto(PublicDto):
    token: str = Field(min_length=1, max_length=512)
    kind: Literal["source", "evidence", "template"]
    label: SafeLabel
    description: SafeMessage | None
    expires_at: UtcTimestamp = Field(alias="expiresAt")


AUTHORITATIVE_PUBLIC_DTOS = (
    AcceptedRefDto,
    AdminDomainDto,
    AdminSourceDto,
    AllowedAction,
    ComposerRefDto,
    ConversationDetailResponseDto,
    ConversationSummaryDto,
    CurrentUserDto,
    DocumentSummaryDto,
    EmbeddingProfileSummaryDto,
    EvidenceAnchorDto,
    EvidenceItemDto,
    EvidenceLocationDocumentDto,
    EvidenceLocationEvidenceDto,
    EvidenceLocationResponseDto,
    EvidenceRegionDto,
    ModelProfileDto,
    OperationDto,
    OperationErrorDto,
    OutlineItemDto,
    ProviderSummaryDto,
    RetrievalEvidenceAnchorDto,
    RetrievalEvidenceItemDto,
    RetrievalEvidenceRequestDto,
    RetrievalEvidenceResponseDto,
    RuntimeSettingsDto,
    TurnDto,
    TurnErrorDto,
)


def authoritative_component_schemas(
    *, ref_template: str = "#/components/schemas/{model}"
) -> dict[str, object]:
    _, schema = models_json_schema(
        [(model, "serialization") for model in AUTHORITATIVE_PUBLIC_DTOS],
        by_alias=True,
        ref_template=ref_template,
    )
    return schema["$defs"]
