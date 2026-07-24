from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from context_engine.api.catalog_schemas import (
    AcceptedRefDto,
    EvidenceItemDto,
    OpaqueRef,
    PublicDto,
    SafeLabel,
    SafeMessage,
    TurnRoute,
    UtcTimestamp,
)


class TurnAcceptedPayload(PublicDto):
    conversation_id: OpaqueRef = Field(alias="conversationId")
    client_request_id: str = Field(alias="clientRequestId", min_length=8, max_length=80)
    replay: bool


class SelectedDomain(PublicDto):
    id: OpaqueRef
    display_name: SafeLabel = Field(alias="displayName")


class RouteSelectedPayload(PublicDto):
    route: TurnRoute
    domain: SelectedDomain | None = None


class RetrievalStartedPayload(PublicDto):
    attempt: int = Field(ge=1)
    max_attempts: int = Field(alias="maxAttempts", ge=1)


class RetrievalCompletedPayload(PublicDto):
    result: Literal["evidence_found", "no_grounded_context"]
    evidence_count: int = Field(alias="evidenceCount", ge=0)


class EvidenceDeltaPayload(PublicDto):
    items: list[EvidenceItemDto]


class AnswerDeltaPayload(PublicDto):
    text: str


class CitationDto(PublicDto):
    evidence_ref_id: OpaqueRef = Field(alias="evidenceRefId")
    citation_label: str = Field(alias="citationLabel", min_length=1, max_length=32)


class TurnBudgetDto(PublicDto):
    plan_step_count: int = Field(alias="planStepCount", ge=0)
    retrieval_operation_count: int = Field(alias="retrievalOperationCount", ge=0)
    repair_attempt_count: int = Field(alias="repairAttemptCount", ge=0)


class TurnCompletedPayload(PublicDto):
    route: TurnRoute
    status: Literal["completed"]
    stop_reason: Literal[
        "direct_llm",
        "grounded",
        "no_grounded_context",
        "evidence_only",
        "turn_budget_exhausted",
    ] = Field(alias="stopReason")
    citations: list[CitationDto]
    accepted_refs: list[AcceptedRefDto] = Field(alias="acceptedRefs")
    budget: TurnBudgetDto
    replay: bool


class TurnFailedPayload(PublicDto):
    code: str = Field(min_length=1, max_length=120)
    message: SafeMessage
    retryable: bool
    replay: bool


class TurnCancelledPayload(PublicDto):
    code: Literal["turn_cancelled"]
    message: SafeMessage
    replay: bool


class TurnRedactedPayload(PublicDto):
    code: Literal["turn_redacted"]
    message: SafeMessage
    redacted_at: UtcTimestamp = Field(alias="redactedAt")


class EventEnvelope(PublicDto):
    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    event_id: OpaqueRef = Field(alias="eventId")
    turn_id: OpaqueRef = Field(alias="turnId")
    sequence: int = Field(ge=1)
    occurred_at: UtcTimestamp = Field(alias="occurredAt")


class TurnAcceptedEvent(EventEnvelope):
    type: Literal["turn.accepted"]
    payload: TurnAcceptedPayload


class RouteSelectedEvent(EventEnvelope):
    type: Literal["route.selected"]
    payload: RouteSelectedPayload


class RetrievalStartedEvent(EventEnvelope):
    type: Literal["retrieval.started"]
    payload: RetrievalStartedPayload


class RetrievalCompletedEvent(EventEnvelope):
    type: Literal["retrieval.completed"]
    payload: RetrievalCompletedPayload


class EvidenceDeltaEvent(EventEnvelope):
    type: Literal["evidence.delta"]
    payload: EvidenceDeltaPayload


class AnswerDeltaEvent(EventEnvelope):
    type: Literal["answer.delta"]
    payload: AnswerDeltaPayload


class TurnCompletedEvent(EventEnvelope):
    type: Literal["turn.completed"]
    payload: TurnCompletedPayload


class TurnFailedEvent(EventEnvelope):
    type: Literal["turn.failed"]
    payload: TurnFailedPayload


class TurnCancelledEvent(EventEnvelope):
    type: Literal["turn.cancelled"]
    payload: TurnCancelledPayload


class TurnRedactedEvent(EventEnvelope):
    type: Literal["turn.redacted"]
    payload: TurnRedactedPayload


TurnStreamEvent = Annotated[
    TurnAcceptedEvent
    | RouteSelectedEvent
    | RetrievalStartedEvent
    | RetrievalCompletedEvent
    | EvidenceDeltaEvent
    | AnswerDeltaEvent
    | TurnCompletedEvent
    | TurnFailedEvent
    | TurnCancelledEvent
    | TurnRedactedEvent,
    Field(discriminator="type"),
]
TURN_STREAM_EVENT_ADAPTER = TypeAdapter(TurnStreamEvent)


def canonical_sse_json_schema(*, ref_template: str = "#/$defs/{model}") -> dict[str, object]:
    return TURN_STREAM_EVENT_ADAPTER.json_schema(by_alias=True, ref_template=ref_template)
