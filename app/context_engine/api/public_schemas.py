from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

APPROVED_HTTP_ERROR_CODES = (
    "account_unavailable",
    "audit_unavailable",
    "capacity_unavailable",
    "content_rejected",
    "csrf_invalid",
    "cursor_expired",
    "dependency_unavailable",
    "document_content_unavailable",
    "document_not_found",
    "document_preview_unavailable",
    "domain_not_query_eligible",
    "domain_operation_in_progress",
    "domain_required",
    "domain_state_conflict",
    "duplicate_source",
    "evidence_not_found",
    "evidence_unavailable",
    "forbidden",
    "http_error",
    "idempotency_conflict",
    "internal_error",
    "invalid_credentials",
    "not_found",
    "operation_conflict",
    "range_not_satisfiable",
    "rate_limited",
    "session_expired",
    "source_not_ready",
    "stale_revision",
    "turn_not_cancellable",
    "unauthenticated",
    "validation_error",
)
ErrorCode = Literal[*APPROVED_HTTP_ERROR_CODES]


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str = Field(alias="requestId", min_length=1, max_length=80)
    fields: dict[str, str]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail

    model_config = ConfigDict(extra="forbid")


class CsrfResponse(BaseModel):
    csrf_token: str = Field(alias="csrfToken")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
class LiveHealthResponse(BaseModel):
    status: Literal["live"]

    model_config = ConfigDict(extra="forbid")


class ReadyHealthResponse(BaseModel):
    status: Literal["ready"]

    model_config = ConfigDict(extra="forbid")
