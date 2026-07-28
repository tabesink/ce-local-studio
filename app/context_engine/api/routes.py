# FastAPI dependency markers are intentionally evaluated in route defaults.
# ruff: noqa: B008
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.api.catalog_schemas import (
    AdminDomainDto,
    AdminSourceDto,
    CONVERSATION_PUBLIC_REF_PATTERN,
    ComposerRefDto,
    ConversationDetailResponseDto,
    ConversationSummaryDto,
    DocumentSummaryDto,
    DomainSummaryDto,
    EvidenceLocationResponseDto,
    ModelProfileDto,
    OperationDto,
    OutlineItemDto,
    ProviderSummaryDto,
    RetrievalEvidenceRequestDto,
    RetrievalEvidenceResponseDto,
    RuntimeSettingsDto,
    TURN_PUBLIC_REF_PATTERN,
    TurnDto,
)
from context_engine.api.conventions import format_utc_timestamp
from context_engine.api.dependencies import (
    CurrentSession,
    get_db,
    get_settings,
    require_admin,
    require_current_session,
)
from context_engine.api.errors import ApiError, request_id_from
from context_engine.api.public_schemas import (
    CsrfResponse,
    CursorExpiredEnvelope,
    ErrorEnvelope,
    LiveHealthResponse,
    ReadyHealthResponse,
)
from context_engine.api.sse_schemas import TurnStreamEvent
from context_engine.config import Settings
from context_engine.models import (
    HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
    HTTP_IDEMPOTENCY_ROUTE_DOMAIN_CREATE,
    HTTP_IDEMPOTENCY_ROUTE_DOMAIN_DELETE,
    HTTP_IDEMPOTENCY_ROUTE_DOMAIN_START,
    HTTP_IDEMPOTENCY_ROUTE_DOMAIN_STOP,
    HTTP_IDEMPOTENCY_ROUTE_MODEL_PROFILE_CREATE,
    HTTP_IDEMPOTENCY_ROUTE_SOURCE_DELETE,
    HTTP_IDEMPOTENCY_ROUTE_SOURCE_INDEX_RETRY,
    HTTP_IDEMPOTENCY_ROUTE_SOURCE_RETRY,
    HTTP_IDEMPOTENCY_ROUTE_SOURCE_UPLOAD,
    DomainOperation,
    HttpIdempotencyRecord,
    ModelProfile,
    SourceDocument,
    SourcePreparationOperation,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import (
    authenticate_user,
    create_auth_session,
    revoke_session_token,
    safe_user,
)
from context_engine.services.chat_turns import (
    ChatTurnError,
    cancel_turn,
    conversation_turn_summaries,
    encode_sse_event,
    safe_turn_dto,
    stream_turn_events,
    stream_turn_events_by_turn,
)
from context_engine.services.composer_refs import (
    MAX_COMPOSER_REFS,
    MAX_DISCOVERY_LIMIT,
    ComposerRefError,
    discover_composer_refs,
)
from context_engine.services.conversations import (
    ConversationError,
    create_conversation,
    delete_conversation,
    get_owned_conversation,
    get_owned_conversation_detail,
    list_conversations,
    normalize_conversation_title,
    safe_conversation_summary,
    update_conversation_title,
)
from context_engine.services.idempotency import (
    IdempotencyError,
    abandon_idempotent,
    begin_idempotent,
    complete_idempotent,
    fingerprint_payload,
)
from context_engine.services.csrf import CSRF_PREAUTH_BINDING, issue_csrf_token
from context_engine.services.documents import (
    DEFAULT_DOCUMENT_PAGE_SIZE,
    MAX_DOCUMENT_PAGE_SIZE,
    DocumentError,
    get_document,
    get_document_content,
    get_evidence_location,
    list_documents,
)
from context_engine.services.domains import (
    DOMAIN_ID_PATTERN,
    DomainError,
    admin_domain_list,
    controller_from_settings,
    create_domain,
    domain_detail,
    domain_operations,
    domain_status,
    enqueue_delete_domain,
    member_domain_list,
    safe_domain_admin,
    safe_domain_operation,
    start_domain,
    stop_domain,
)
from context_engine.services.evidence import (
    EvidenceRetrievalError,
    retrieve_scoped_evidence,
)
from context_engine.services.indexing import (
    SourceIndexError,
    cancel_source_index,
    retry_source_index,
)
from context_engine.services.login_throttle import (
    LoginRateLimited,
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from context_engine.services.readiness import ReadinessError, check_readiness
from context_engine.services.runtime_config import (
    RuntimeConfigError,
    SecretCrypto,
    create_model_profile,
    delete_model_profile,
    ensure_runtime_settings,
    parse_if_match_version,
    rotate_provider_credential,
    runtime_settings_snapshot,
    safe_model_profile,
    safe_provider,
    safe_runtime_settings,
    strong_etag,
    update_model_profile,
    update_runtime_settings,
)
from context_engine.services.source_upload import (
    MAX_SOURCE_FILE_SIZE_BYTES,
    UploadValidationError,
    iter_upload_file,
    read_upload_stream,
)
from context_engine.services.sources import (
    SourceError,
    cancel_source,
    enqueue_delete_source,
    list_sources,
    retry_source,
    safe_source,
    safe_source_operation,
    sanitize_original_filename,
    source_detail,
    source_operations,
    source_outline,
    upload_source_bytes,
)
from context_engine.services.users import UserDirectoryError, list_admin_users


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    model_config = ConfigDict(extra="forbid")


class ProviderCredentialRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=20000)

    model_config = ConfigDict(extra="forbid")


class ModelProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_kind: str = Field(alias="profileKind")
    provider_kind: str = Field(alias="providerKind")
    model_name: str = Field(alias="modelName", min_length=1, max_length=200)
    vector_dimensions: int | None = Field(default=None, alias="vectorDimensions", gt=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelProfilePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    model_name: str | None = Field(default=None, alias="modelName", min_length=1, max_length=200)
    vector_dimensions: int | None = Field(default=None, alias="vectorDimensions", gt=0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeSettingsPatchRequest(BaseModel):
    active_synthesis_profile_id: str | None = Field(default=None, alias="activeSynthesisProfileId")
    active_parser_kind: str | None = Field(default=None, alias="activeParserKind")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeSettingsSnapshotResponse(BaseModel):
    providers: list[ProviderSummaryDto]
    model_profiles: list[ModelProfileDto] = Field(alias="modelProfiles")
    runtime_settings: RuntimeSettingsDto = Field(alias="runtimeSettings")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProviderMutationResponse(BaseModel):
    provider: ProviderSummaryDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelProfileMutationResponse(BaseModel):
    model_profile: ModelProfileDto = Field(alias="modelProfile")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeSettingsMutationResponse(BaseModel):
    runtime_settings: RuntimeSettingsDto = Field(alias="runtimeSettings")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DomainCreateRequest(BaseModel):
    id: str = Field(pattern=DOMAIN_ID_PATTERN)
    display_name: str | None = Field(default=None, alias="displayName", min_length=1, max_length=120)
    embedding_profile_id: str = Field(alias="embeddingProfileId", min_length=1, max_length=36)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminDomainMutationResponse(BaseModel):
    domain: AdminDomainDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminDomainListResponse(BaseModel):
    domains: list[AdminDomainDto]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminDomainStatusResponse(BaseModel):
    domain: AdminDomainDto
    active_operation: OperationDto | None = Field(alias="activeOperation")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DomainOperationMutationResponse(BaseModel):
    operation: OperationDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminDomainOperationsResponse(BaseModel):
    operations: list[OperationDto]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminSourceMutationResponse(BaseModel):
    source: AdminSourceDto
    operation: OperationDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminSourceDetailResponse(BaseModel):
    source: AdminSourceDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminSourceListResponse(BaseModel):
    sources: list[AdminSourceDto]
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminSourceOutlineResponse(BaseModel):
    items: list[OutlineItemDto]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminSourceOperationsResponse(BaseModel):
    operations: list[OperationDto]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SourceOperationMutationResponse(BaseModel):
    operation: OperationDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MemberDomainListResponse(BaseModel):
    domains: list[DomainSummaryDto]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DocumentsListResponse(BaseModel):
    documents: list[DocumentSummaryDto]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DocumentDetailResponse(BaseModel):
    document: DocumentSummaryDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ComposerRefDiscoverRequest(BaseModel):
    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
        pattern=CONVERSATION_PUBLIC_REF_PATTERN,
    )
    domain_id: str | None = Field(default=None, alias="domainId", max_length=64)
    kinds: list[Literal["source", "evidence", "template"]] | None = Field(default=None, max_length=3)
    query: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=MAX_COMPOSER_REFS, ge=1, le=MAX_DISCOVERY_LIMIT)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ComposerRefDiscoverResponse(BaseModel):
    refs: list[ComposerRefDto]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConversationTitleRequest(BaseModel):
    title: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConversationMutationResponse(BaseModel):
    conversation: ConversationSummaryDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryDto]
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TurnMutationResponse(BaseModel):
    turn: TurnDto

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TurnStreamRequest(BaseModel):
    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    domain_id: str | None = Field(default=None, alias="domainId", max_length=64)
    composer_ref_tokens: list[str] = Field(default_factory=list, alias="composerRefTokens", max_length=MAX_COMPOSER_REFS)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


api_router = APIRouter()
health_router = APIRouter()


def _client_bucket(request: Request) -> str:
    return getattr(request.state, "client_bucket", None) or "test-bypass"


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _set_csrf_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _expire_auth_cookies(response: Response, settings: Settings) -> None:
    common = {
        "value": "",
        "max_age": 0,
        "expires": 0,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
    }
    response.set_cookie(key=settings.session_cookie_name, httponly=True, **common)
    response.set_cookie(key=settings.csrf_cookie_name, httponly=False, **common)


@health_router.get("/health/live", response_model=LiveHealthResponse)
def live() -> dict[str, str]:
    return {"status": "live"}


@api_router.get("/auth/csrf", response_model=CsrfResponse)
def csrf(response: Response, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    token = issue_csrf_token(settings, binding=CSRF_PREAUTH_BINDING)
    _set_csrf_cookie(response, settings, token)
    response.headers["Cache-Control"] = "private, no-store, no-transform"
    return {"csrfToken": token}


@health_router.get(
    "/health/ready",
    response_model=ReadyHealthResponse,
    responses={503: {"model": ErrorEnvelope, "description": "Service is not ready."}},
)
def ready(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    try:
        check_readiness(db, settings)
    except ReadinessError as exc:
        raise ApiError(503, "dependency_unavailable", "Service unavailable.") from exc
    return {"status": "ready"}


@api_router.post("/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    client_bucket = _client_bucket(request)
    try:
        assert_login_allowed(db, client_bucket=client_bucket, username=payload.username)
    except LoginRateLimited as exc:
        raise ApiError(
            429,
            "rate_limited",
            "Login temporarily unavailable.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        record_login_failure(
            db,
            settings,
            client_bucket=client_bucket,
            username=payload.username,
        )
        raise ApiError(401, "invalid_credentials", "Invalid username or password.")

    clear_login_failures(db, client_bucket=client_bucket, username=payload.username)
    token, _auth_session = create_auth_session(
        db,
        user,
        settings,
        presented_token=request.cookies.get(settings.session_cookie_name),
    )
    _set_session_cookie(response, settings, token)
    _set_csrf_cookie(
        response,
        settings,
        issue_csrf_token(settings, binding=hash_session_token(token)),
    )
    response.headers["Cache-Control"] = "private, no-store, no-transform"
    return {"user": safe_user(user)}


@api_router.get("/auth/me")
def me(current: CurrentSession = Depends(require_current_session)) -> dict[str, object]:
    return {"user": safe_user(current.user)}


@api_router.post("/auth/logout", status_code=204, response_class=Response)
def logout(
    request: Request,
    response: Response,
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        revoke_session_token(db, token)
    _expire_auth_cookies(response, settings)
    response.status_code = 204
    response.headers["Cache-Control"] = "private, no-store, no-transform"
    return response


def _user_directory_api_error(exc: UserDirectoryError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


@api_router.get("/admin/users")
def admin_users(
    request: Request,
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        result = list_admin_users(db, cursor=cursor, limit=limit)
    except UserDirectoryError as exc:
        raise _user_directory_api_error(exc) from exc
    return _private_json_response(result)


def _runtime_config_api_error(exc: RuntimeConfigError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _domain_api_error(exc: DomainError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _source_api_error(exc: SourceError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


_DOCUMENT_HTTP_ERROR_MAP: dict[str, tuple[int, str, str]] = {
    "document_not_found": (404, "document_not_found", "Document not found."),
    "document_preview_unavailable": (
        409,
        "document_preview_unavailable",
        "A governed PDF preview is not available for this document.",
    ),
    "document_content_unavailable": (
        503,
        "document_content_unavailable",
        "Document content is temporarily unavailable.",
    ),
    "evidence_not_found": (404, "evidence_not_found", "Evidence not found."),
    "evidence_unavailable": (410, "evidence_unavailable", "Evidence is no longer available."),
    "range_not_satisfiable": (416, "range_not_satisfiable", "Requested range is not satisfiable."),
    "cursor_expired": (410, "cursor_expired", "The cursor has expired."),
    "validation_error": (422, "validation_error", "Request validation failed."),
}


def _document_api_error(exc: DocumentError) -> ApiError:
    mapped = _DOCUMENT_HTTP_ERROR_MAP.get(exc.code)
    if mapped is None:
        return ApiError(503, "dependency_unavailable", "Document service is temporarily unavailable.")
    status_code, code, message = mapped
    return ApiError(status_code, code, message, headers=exc.headers or None)


_SOURCE_INDEX_HTTP_ERROR_MAP: dict[str, tuple[int, str]] = {
    "domain_not_found": (404, "not_found"),
    "source_not_found": (404, "not_found"),
    "domain_state_conflict": (409, "domain_state_conflict"),
    "source_state_conflict": (409, "operation_conflict"),
    "source_index_in_progress": (409, "operation_conflict"),
    "source_index_conflict": (409, "operation_conflict"),
    "source_index_input_invalid": (422, "validation_error"),
    "source_index_unavailable": (503, "dependency_unavailable"),
    "source_index_timeout": (504, "dependency_unavailable"),
    "source_index_delete_failed": (502, "dependency_unavailable"),
}


def _source_index_api_error(exc: SourceIndexError) -> ApiError:
    mapped = _SOURCE_INDEX_HTTP_ERROR_MAP.get(exc.code)
    if mapped is None:
        return ApiError(exc.status_code, "dependency_unavailable", exc.message)
    status_code, code = mapped
    return ApiError(status_code, code, exc.message)


def _evidence_api_error(exc: EvidenceRetrievalError) -> ApiError:
    failures = {
        "domain_not_found": (404, "not_found", "Domain not found."),
        "domain_state_conflict": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "domain_runtime_unavailable": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "domain_no_eligible_sources": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "retrieval_capacity_unavailable": (
            503,
            "capacity_unavailable",
            "Retrieval capacity is temporarily unavailable.",
        ),
        "retrieval_dependency_unavailable": (
            503,
            "dependency_unavailable",
            "Retrieval is temporarily unavailable.",
        ),
        "domain_runtime_dependency_unavailable": (
            503,
            "dependency_unavailable",
            "Retrieval is temporarily unavailable.",
        ),
    }
    status_code, code, message = failures.get(
        exc.code,
        (503, "dependency_unavailable", "Retrieval is temporarily unavailable."),
    )
    return ApiError(status_code, code, message)


def _conversation_api_error(exc: ConversationError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _idempotency_api_error(exc: IdempotencyError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _complete_idempotent_claim(
    db: Session,
    record: HttpIdempotencyRecord,
    *,
    http_status: int,
    response_kind: str,
    response_refs: dict[str, object],
) -> None:
    complete_idempotent(
        db,
        record,
        http_status=http_status,
        response_kind=response_kind,
        response_refs=response_refs,
    )
    db.commit()


def _abandon_idempotent_claim(db: Session, record: HttpIdempotencyRecord) -> None:
    try:
        abandon_idempotent(db, record)
        db.commit()
    except Exception:
        db.rollback()


def _reject_unknown_query(request: Request, allowed: set[str] | None = None) -> None:
    if set(request.query_params) - (allowed or set()):
        raise ApiError(422, "validation_error", "Request validation failed.")


def _composer_ref_api_error(exc: ComposerRefError) -> ApiError:
    # Discover projector: only approved ErrorCodes escape (mirror turn-start allowlist).
    failures = {
        "validation_error": (422, "validation_error", "Request validation failed."),
        "composer_ref_unavailable": (
            409,
            "operation_conflict",
            "Composer reference is unavailable.",
        ),
    }
    status_code, code, message = failures.get(
        exc.code,
        (503, "dependency_unavailable", "Composer references are temporarily unavailable."),
    )
    return ApiError(status_code, code, message)


def _chat_turn_api_error(exc: ChatTurnError) -> ApiError:
    # Pre-stream / turn-boundary projector: only approved ErrorCodes escape.
    # Mirrors Evidence allowlisting; never passthrough private/internal codes.
    failures = {
        "validation_error": (422, "validation_error", "Request validation failed."),
        "domain_required": (422, "domain_required", "A knowledge domain is required."),
        "domain_not_found": (404, "not_found", "Domain not found."),
        "not_found": (404, "not_found", "Conversation turn not found."),
        "domain_state_conflict": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "domain_runtime_unavailable": (
            409,
            "domain_not_query_eligible",
            "This knowledge domain is not currently available for queries.",
        ),
        "domain_runtime_dependency_unavailable": (
            503,
            "dependency_unavailable",
            "Retrieval is temporarily unavailable.",
        ),
        "client_request_conflict": (
            409,
            "idempotency_conflict",
            "Client request conflicts with an existing turn.",
        ),
        "idempotency_conflict": (
            409,
            "idempotency_conflict",
            "Client request conflicts with an existing turn.",
        ),
        "conversation_turn_in_progress": (
            409,
            "operation_conflict",
            "A conversation turn is already running.",
        ),
        "composer_ref_unavailable": (
            409,
            "operation_conflict",
            "Composer reference is unavailable.",
        ),
        "synthesis_profile_not_ready": (
            503,
            "dependency_unavailable",
            "Synthesis is temporarily unavailable.",
        ),
        "unauthenticated": (401, "unauthenticated", "Authentication required."),
        "turn_not_cancellable": (409, "turn_not_cancellable", "Turn is not cancellable."),
        "cursor_expired": (410, "cursor_expired", "The event cursor is no longer available."),
    }
    status_code, code, message = failures.get(
        exc.code,
        (503, "dependency_unavailable", "Chat is temporarily unavailable."),
    )
    extra = None
    if code == "cursor_expired" and exc.terminal_snapshot is not None:
        extra = {"terminalSnapshot": exc.terminal_snapshot}
    return ApiError(status_code, code, message, extra=extra)


def _audit_context(request: Request, user: User) -> AuditContext:
    return AuditContext(actor_user=user, request_id=request_id_from(request))


def _parse_optional_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.removesuffix("Z"))
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Request validation failed.") from exc


def _content_length_too_large(request: Request) -> bool:
    raw = request.headers.get("content-length")
    if raw is None:
        return False
    try:
        # Multipart envelope overhead is small relative to the 25 MiB source cap.
        return int(raw) > MAX_SOURCE_FILE_SIZE_BYTES + (1024 * 1024)
    except ValueError:
        return False


@api_router.post("/composer-refs:discover", response_model=ComposerRefDiscoverResponse)
def post_composer_refs_discover(
    payload: ComposerRefDiscoverRequest,
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ComposerRefDiscoverResponse:
    try:
        refs = discover_composer_refs(
            db,
            settings=settings,
            owner=current.user,
            conversation_id=payload.conversation_id,
            domain_id=payload.domain_id,
            kinds=payload.kinds,
            query=payload.query,
            limit=payload.limit,
        )
    except ComposerRefError as exc:
        raise _composer_ref_api_error(exc) from exc
    return ComposerRefDiscoverResponse(
        refs=[
            ComposerRefDto(
                token=ref["token"],
                kind=ref["kind"],
                label=ref["label"],
                description=ref.get("description"),
                expiresAt=format_utc_timestamp(ref["expiresAt"]),
            )
            for ref in refs
        ]
    )


@api_router.get("/conversations", response_model=ConversationListResponse)
def get_conversations(
    request: Request,
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        page = list_conversations(db, owner=current.user, cursor=cursor, limit=limit)
        response = ConversationListResponse.model_validate(
            {"conversations": page.conversations, "nextCursor": page.next_cursor}
        )
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return _private_json_response(response.model_dump(by_alias=True, mode="json"))


@api_router.post(
    "/conversations",
    status_code=201,
    response_model=ConversationMutationResponse,
)
def post_conversation(
    request: Request,
    payload: ConversationTitleRequest | None = Body(default=None),
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    _reject_unknown_query(request)
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {"title": normalize_conversation_title(payload.title if payload else None)}
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=current.user.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_CONVERSATION_CREATE,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                conversation = get_owned_conversation(
                    db,
                    owner=current.user,
                    conversation_id=str(refs["conversationId"]),
                )
                response = ConversationMutationResponse.model_validate(
                    {"conversation": safe_conversation_summary(conversation)}
                )
                return _private_json_response(
                    response.model_dump(by_alias=True, mode="json"),
                    status_code=outcome.http_status or 201,
                    etag=strong_etag(conversation.version),
                )
            claim = outcome.record

        conversation = create_conversation(
            db,
            settings=settings,
            owner=current.user,
            title=payload.title if payload else None,
            auth_session=current.auth_session,
            audit_context=_audit_context(request, current.user),
        )
        response = ConversationMutationResponse.model_validate(
            {"conversation": safe_conversation_summary(conversation)}
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=201,
                response_kind="conversation",
                response_refs={"conversationId": conversation.public_ref},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except ConversationError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _conversation_api_error(exc) from exc
    return _private_json_response(
        response.model_dump(by_alias=True, mode="json"),
        status_code=201,
        etag=strong_etag(conversation.version),
    )


@api_router.get(
    "/conversations/{conversationId}",
    response_model=ConversationDetailResponseDto,
)
def get_conversation(
    request: Request,
    conversation_id: Annotated[
        str,
        Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN),
    ],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request)
    try:
        conversation = get_owned_conversation_detail(db, owner=current.user, conversation_id=conversation_id)
        response = ConversationDetailResponseDto.model_validate(
            {
                "conversation": safe_conversation_summary(conversation),
                "turns": conversation_turn_summaries(db, settings, conversation),
            }
        )
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return _private_json_response(
        response.model_dump(by_alias=True, mode="json"),
        etag=strong_etag(conversation.version),
    )


@api_router.patch(
    "/conversations/{conversationId}",
    response_model=ConversationMutationResponse,
)
def patch_conversation(
    request: Request,
    payload: ConversationTitleRequest,
    conversation_id: Annotated[
        str,
        Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN),
    ],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JSONResponse:
    _reject_unknown_query(request)
    try:
        expected_version = parse_if_match_version(if_match)
        conversation = update_conversation_title(
            db,
            settings=settings,
            owner=current.user,
            conversation_id=conversation_id,
            title=payload.title,
            expected_version=expected_version,
            auth_session=current.auth_session,
            audit_context=_audit_context(request, current.user),
        )
        response = ConversationMutationResponse.model_validate(
            {"conversation": safe_conversation_summary(conversation)}
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return _private_json_response(
        response.model_dump(by_alias=True, mode="json"),
        etag=strong_etag(conversation.version),
    )


@api_router.delete("/conversations/{conversationId}", status_code=204)
def remove_conversation(
    request: Request,
    conversation_id: Annotated[
        str,
        Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN),
    ],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    _reject_unknown_query(request)
    try:
        expected_version = parse_if_match_version(if_match)
        delete_conversation(
            db,
            settings=settings,
            owner=current.user,
            conversation_id=conversation_id,
            expected_version=expected_version,
            auth_session=current.auth_session,
            audit_context=_audit_context(request, current.user),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return Response(
        status_code=204,
        headers={"Cache-Control": "private, no-store, no-transform"},
    )



def _streaming_sse_response(first_event: TurnStreamEvent | None, remaining_events) -> StreamingResponse:
    def body():
        try:
            if first_event is not None:
                yield encode_sse_event(first_event)
            for event in remaining_events:
                yield encode_sse_event(event)
        finally:
            close = getattr(remaining_events, "close", None)
            if close is not None:
                close()

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "private, no-store, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@api_router.post("/conversations/{conversationId}/turns:stream")
def post_conversation_turn_stream(
    payload: TurnStreamRequest,
    request: Request,
    conversation_id: Annotated[str, Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _reject_unknown_query(request)
    events = stream_turn_events(
        db,
        settings=settings,
        owner=current.user,
        auth_session=current.auth_session,
        conversation_id=conversation_id,
        client_request_id=payload.client_request_id,
        message=payload.message,
        domain_id=payload.domain_id,
        composer_ref_tokens=payload.composer_ref_tokens,
        request_id=request_id_from(request),
        synthesis_adapter=getattr(request.app.state, "synthesis_stream_adapter", None),
        retrieval_port=getattr(request.app.state, "retrieval_port", None),
    )
    try:
        first_event = next(events)
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    except ChatTurnError as exc:
        raise _chat_turn_api_error(exc) from exc
    except StopIteration as exc:  # pragma: no cover - defensive guard for a broken projector
        raise ApiError(500, "internal_error", "Internal server error.") from exc
    return _streaming_sse_response(first_event, events)


@api_router.get(
    "/conversations/{conversationId}/turns/{turnId}/events",
    responses={
        410: {
            "model": CursorExpiredEnvelope,
            "description": "The event cursor is no longer available.",
        },
    },
)
def get_conversation_turn_events(
    request: Request,
    conversation_id: Annotated[str, Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN)],
    turn_id: Annotated[str, Path(alias="turnId", pattern=TURN_PUBLIC_REF_PATTERN)],
    after: int = Query(default=0, ge=0),
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    _reject_unknown_query(request, {"after"})
    try:
        events = stream_turn_events_by_turn(
            db,
            owner=current.user,
            conversation_id=conversation_id,
            turn_id=turn_id,
            after=after,
            settings=settings,
        )
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    except ChatTurnError as exc:
        raise _chat_turn_api_error(exc) from exc
    return _streaming_sse_response(None, events)


@api_router.post(
    "/conversations/{conversationId}/turns/{turnId}:cancel",
    status_code=202,
    response_model=TurnMutationResponse,
)
def post_conversation_turn_cancel(
    request: Request,
    conversation_id: Annotated[str, Path(alias="conversationId", pattern=CONVERSATION_PUBLIC_REF_PATTERN)],
    turn_id: Annotated[str, Path(alias="turnId", pattern=TURN_PUBLIC_REF_PATTERN)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request)
    try:
        turn = cancel_turn(
            db,
            settings=settings,
            owner=current.user,
            auth_session=current.auth_session,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    except ChatTurnError as exc:
        raise _chat_turn_api_error(exc) from exc
    response = TurnMutationResponse.model_validate({"turn": safe_turn_dto(db, settings, turn)})
    return _private_json_response(response.model_dump(by_alias=True, mode="json"), status_code=202)


def _private_json_response(payload: dict[str, object], *, status_code: int = 200, etag: str | None = None) -> JSONResponse:
    headers = {"Cache-Control": "private, no-store, no-transform"}
    if etag is not None:
        headers["ETag"] = etag
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


@api_router.get("/admin/runtime-settings", response_model=RuntimeSettingsSnapshotResponse)
def admin_runtime_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return _private_json_response(runtime_settings_snapshot(db))


@api_router.put("/admin/runtime-settings/providers/{kind}", response_model=ProviderMutationResponse)
def admin_rotate_provider_credential(
    request: Request,
    provider_kind: Annotated[str, Path(alias="kind")],
    payload: ProviderCredentialRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JSONResponse:
    try:
        expected_version = parse_if_match_version(if_match)
        provider = rotate_provider_credential(
            db,
            provider_kind,
            payload.credential,
            SecretCrypto.from_settings(settings),
            expected_version=expected_version,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    return _private_json_response(
        {"provider": safe_provider(provider)},
        etag=strong_etag(provider.version),
    )


@api_router.post(
    "/admin/runtime-settings/model-profiles",
    status_code=201,
    response_model=ModelProfileMutationResponse,
)
def admin_create_model_profile(
    request: Request,
    payload: ModelProfileCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {
                    "name": payload.name,
                    "profileKind": payload.profile_kind,
                    "providerKind": payload.provider_kind,
                    "modelName": payload.model_name,
                    "vectorDimensions": payload.vector_dimensions,
                }
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_MODEL_PROFILE_CREATE,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                profile = db.scalar(
                    select(ModelProfile).where(ModelProfile.id == refs["modelProfileId"])
                )
                if profile is None:
                    raise RuntimeConfigError(404, "model_profile_not_found", "Model profile not found.")
                return _private_json_response(
                    {"modelProfile": safe_model_profile(db, profile)},
                    status_code=outcome.http_status or 201,
                    etag=strong_etag(profile.version),
                )
            claim = outcome.record

        profile = create_model_profile(
            db,
            name=payload.name,
            profile_kind=payload.profile_kind,
            provider_kind=payload.provider_kind,
            model_name=payload.model_name,
            vector_dimensions=payload.vector_dimensions,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=201,
                response_kind="model_profile",
                response_refs={"modelProfileId": profile.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except RuntimeConfigError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _runtime_config_api_error(exc) from exc
    return _private_json_response(
        {"modelProfile": safe_model_profile(db, profile)},
        status_code=201,
        etag=strong_etag(profile.version),
    )


@api_router.patch(
    "/admin/runtime-settings/model-profiles/{id}",
    response_model=ModelProfileMutationResponse,
)
def admin_update_model_profile(
    request: Request,
    profile_id: Annotated[str, Path(alias="id")],
    payload: ModelProfilePatchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JSONResponse:
    try:
        expected_version = parse_if_match_version(if_match)
        profile = update_model_profile(
            db,
            profile_id,
            payload.model_dump(exclude_unset=True),
            expected_version=expected_version,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    return _private_json_response(
        {"modelProfile": safe_model_profile(db, profile)},
        etag=strong_etag(profile.version),
    )


@api_router.delete("/admin/runtime-settings/model-profiles/{id}", status_code=204)
def admin_delete_model_profile(
    request: Request,
    profile_id: Annotated[str, Path(alias="id")],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_model_profile(db, profile_id, audit_context=_audit_context(request, admin))
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    return Response(status_code=204, headers={"Cache-Control": "private, no-store, no-transform"})


@api_router.patch("/admin/runtime-settings", response_model=RuntimeSettingsMutationResponse)
def admin_update_runtime_settings(
    request: Request,
    payload: RuntimeSettingsPatchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JSONResponse:
    try:
        expected_version = parse_if_match_version(if_match)
        settings_row = update_runtime_settings(
            db,
            payload.model_dump(exclude_unset=True),
            expected_version=expected_version,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    return _private_json_response(
        {"runtimeSettings": safe_runtime_settings(settings_row)},
        etag=strong_etag(settings_row.version),
    )


@api_router.post("/admin/domains", status_code=201, response_model=AdminDomainMutationResponse)
def admin_create_domain(
    request: Request,
    payload: DomainCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {
                    "id": payload.id,
                    "displayName": payload.display_name,
                    "embeddingProfileId": payload.embedding_profile_id,
                }
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_DOMAIN_CREATE,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                projected = domain_detail(db, settings, str(refs["domainId"]))
                return _private_json_response(
                    {"domain": projected},
                    status_code=outcome.http_status or 201,
                    etag=strong_etag(int(projected["version"])),
                )
            claim = outcome.record

        domain = create_domain(
            db,
            settings=settings,
            domain_id=payload.id,
            display_name=payload.display_name,
            embedding_profile_id=payload.embedding_profile_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=201,
                response_kind="domain",
                response_refs={"domainId": domain.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except RuntimeConfigError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _runtime_config_api_error(exc) from exc
    except DomainError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _domain_api_error(exc) from exc
    projected = safe_domain_admin(db, settings, domain, controller_from_settings(settings))
    return _private_json_response(
        {"domain": projected},
        status_code=201,
        etag=strong_etag(domain.version),
    )


@api_router.get("/admin/domains", response_model=AdminDomainListResponse)
def admin_list_domains(
    request: Request,
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        result = admin_domain_list(db, settings, cursor=cursor, limit=limit)
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return _private_json_response(result)


@api_router.get("/admin/domains/{domainId}", response_model=AdminDomainMutationResponse)
def admin_get_domain(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    try:
        domain = domain_detail(db, settings, domain_id)
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return _private_json_response(
        {"domain": domain},
        etag=strong_etag(int(domain["version"])),
    )


@api_router.get("/admin/domains/{domainId}/status", response_model=AdminDomainStatusResponse)
def admin_get_domain_status(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    try:
        return _private_json_response(domain_status(db, settings, domain_id))
    except DomainError as exc:
        raise _domain_api_error(exc) from exc


@api_router.post("/admin/domains/{domainId}/start", status_code=202, response_model=DomainOperationMutationResponse)
def admin_start_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload({"domainId": domain_id})
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_DOMAIN_START,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                operation = db.get(DomainOperation, refs["operationId"])
                if operation is None:
                    raise DomainError(404, "not_found", "Domain not found.")
                return _private_json_response(
                    {"operation": safe_domain_operation(operation)},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        operation = start_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="domain_operation",
                response_refs={"operationId": operation.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except DomainError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _domain_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_domain_operation(operation)},
        status_code=202,
        etag=strong_etag(operation.version),
    )


@api_router.post("/admin/domains/{domainId}/stop", status_code=202, response_model=DomainOperationMutationResponse)
def admin_stop_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload({"domainId": domain_id})
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_DOMAIN_STOP,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                operation = db.get(DomainOperation, refs["operationId"])
                if operation is None:
                    raise DomainError(404, "not_found", "Domain not found.")
                return _private_json_response(
                    {"operation": safe_domain_operation(operation)},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        operation = stop_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="domain_operation",
                response_refs={"operationId": operation.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except DomainError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _domain_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_domain_operation(operation)},
        status_code=202,
        etag=strong_etag(operation.version),
    )


@api_router.delete("/admin/domains/{domainId}", status_code=202, response_model=DomainOperationMutationResponse)
def admin_delete_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        expected_version = parse_if_match_version(if_match)
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {"domainId": domain_id, "ifMatchVersion": expected_version}
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_DOMAIN_DELETE,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                operation = db.get(DomainOperation, refs["operationId"])
                if operation is None:
                    raise DomainError(404, "not_found", "Domain not found.")
                return _private_json_response(
                    {"operation": safe_domain_operation(operation)},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        operation = enqueue_delete_domain(
            db,
            domain_id=domain_id,
            requested_by_user=admin,
            expected_version=expected_version,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="domain_operation",
                response_refs={"operationId": operation.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except RuntimeConfigError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _runtime_config_api_error(exc) from exc
    except DomainError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _domain_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_domain_operation(operation)},
        status_code=202,
        etag=strong_etag(operation.version),
    )


@api_router.get("/admin/domains/{domainId}/operations", response_model=AdminDomainOperationsResponse)
def admin_domain_operations(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        return _private_json_response(domain_operations(db, domain_id, cursor=cursor, limit=limit))
    except DomainError as exc:
        raise _domain_api_error(exc) from exc


@api_router.post(
    "/admin/domains/{domainId}/sources",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def admin_upload_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    if _content_length_too_large(request):
        raise _source_api_error(SourceError(413, "content_rejected", "Uploaded content was rejected."))
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        raise ApiError(422, "validation_error", "Request validation failed.")
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise ApiError(422, "validation_error", "Request validation failed.")
    claim: HttpIdempotencyRecord | None = None
    try:
        validated = await read_upload_stream(iter_upload_file(upload), filename=upload.filename)
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {
                    "domainId": domain_id,
                    "contentSha256": validated.sha256,
                    "displayFilename": sanitize_original_filename(upload.filename),
                    "parserKind": ensure_runtime_settings(db).active_parser_kind,
                }
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_SOURCE_UPLOAD,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                source = db.get(SourceDocument, refs["sourceId"])
                operation = db.get(SourcePreparationOperation, refs["operationId"])
                if source is None or operation is None:
                    raise SourceError(404, "not_found", "Source not found.")
                return _private_json_response(
                    {"source": safe_source(db, source), "operation": safe_source_operation(operation)},
                    status_code=outcome.http_status or 201,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        source, operation = upload_source_bytes(
            db,
            settings=settings,
            domain_id=domain_id,
            filename=upload.filename,
            content_type=validated.content_type,
            data=validated.data,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=201,
                response_kind="source_upload",
                response_refs={
                    "sourceId": source.id,
                    "documentRef": source.public_ref,
                    "operationId": operation.id,
                },
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except UploadValidationError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _source_api_error(SourceError(exc.status_code, exc.code, exc.message)) from exc
    except SourceError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _source_api_error(exc) from exc
    finally:
        await upload.close()
    return _private_json_response(
        {"source": safe_source(db, source), "operation": safe_source_operation(operation)},
        status_code=201,
        etag=strong_etag(operation.version),
    )


@api_router.get("/admin/domains/{domainId}/sources", response_model=AdminSourceListResponse)
def admin_list_sources(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        return _private_json_response(list_sources(db, domain_id, cursor=cursor, limit=limit))
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.get("/admin/domains/{domainId}/sources/{sourceId}", response_model=AdminSourceDetailResponse)
def admin_get_source(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        source = source_detail(db, domain_id, source_id)
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    return _private_json_response({"source": source}, etag=strong_etag(int(source["version"])))


@api_router.get("/admin/domains/{domainId}/sources/{sourceId}/outline", response_model=AdminSourceOutlineResponse)
def admin_get_source_outline(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        return _private_json_response({"items": source_outline(db, domain_id, source_id)})
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.get(
    "/admin/domains/{domainId}/sources/{sourceId}/operations",
    response_model=AdminSourceOperationsResponse,
)
def admin_source_operations(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    _reject_unknown_query(request, {"cursor", "limit"})
    try:
        return _private_json_response(
            source_operations(db, domain_id, source_id, cursor=cursor, limit=limit)
        )
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.post(
    "/admin/domains/{domainId}/sources/{sourceId}/index/retry",
    status_code=202,
    response_model=AdminSourceDetailResponse,
)
def admin_retry_source_index(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload({"domainId": domain_id, "sourceId": source_id})
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_SOURCE_INDEX_RETRY,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                source = db.get(SourceDocument, refs["sourceId"])
                if source is None:
                    raise SourceIndexError(404, "source_not_found", "Source not found.")
                projection = safe_source(db, source)
                return _private_json_response(
                    {"source": projection},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(int(projection["version"])),
                )
            claim = outcome.record

        source = retry_source_index(
            db,
            settings=settings,
            domain_id=domain_id,
            source_id=source_id,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="source_index",
                response_refs={"sourceId": source.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except SourceIndexError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _source_index_api_error(exc) from exc
    projection = safe_source(db, source)
    return _private_json_response({"source": projection}, status_code=202, etag=strong_etag(int(projection["version"])))


@api_router.post(
    "/admin/domains/{domainId}/sources/{sourceId}/index/cancel",
    response_model=AdminSourceDetailResponse,
)
def admin_cancel_source_index(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    try:
        source = cancel_source_index(
            db,
            settings=settings,
            domain_id=domain_id,
            source_id=source_id,
            audit_context=_audit_context(request, admin),
        )
    except SourceIndexError as exc:
        raise _source_index_api_error(exc) from exc
    projection = safe_source(db, source)
    return _private_json_response({"source": projection}, etag=strong_etag(int(projection["version"])))


@api_router.post(
    "/admin/domains/{domainId}/sources/{sourceId}/retry",
    status_code=202,
    response_model=SourceOperationMutationResponse,
)
def admin_retry_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        if idempotency_key is not None:
            fingerprint = fingerprint_payload({"domainId": domain_id, "sourceId": source_id})
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_SOURCE_RETRY,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                operation = db.get(SourcePreparationOperation, refs["operationId"])
                if operation is None:
                    raise SourceError(404, "not_found", "Source not found.")
                return _private_json_response(
                    {"operation": safe_source_operation(operation)},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        operation = retry_source(
            db,
            domain_id=domain_id,
            source_id=source_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="source_operation",
                response_refs={"operationId": operation.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except SourceError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _source_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_source_operation(operation)},
        status_code=202,
        etag=strong_etag(operation.version),
    )


@api_router.post(
    "/admin/domains/{domainId}/sources/{sourceId}/cancel",
    response_model=SourceOperationMutationResponse,
)
def admin_cancel_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> JSONResponse:
    try:
        expected_version = parse_if_match_version(if_match)
        operation = cancel_source(
            db,
            domain_id=domain_id,
            source_id=source_id,
            expected_version=expected_version,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_source_operation(operation)},
        etag=strong_etag(operation.version),
    )


@api_router.delete(
    "/admin/domains/{domainId}/sources/{sourceId}",
    status_code=202,
    response_model=SourceOperationMutationResponse,
)
def admin_delete_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    claim: HttpIdempotencyRecord | None = None
    try:
        expected_version = parse_if_match_version(if_match)
        if idempotency_key is not None:
            fingerprint = fingerprint_payload(
                {"domainId": domain_id, "sourceId": source_id, "ifMatchVersion": expected_version}
            )
            outcome = begin_idempotent(
                db,
                principal_user_id=admin.id,
                route_class=HTTP_IDEMPOTENCY_ROUTE_SOURCE_DELETE,
                raw_key=idempotency_key,
                fingerprint=fingerprint,
            )
            if outcome.replay:
                refs = outcome.response_refs or {}
                operation = db.get(SourcePreparationOperation, refs["operationId"])
                if operation is None:
                    raise SourceError(404, "not_found", "Source not found.")
                return _private_json_response(
                    {"operation": safe_source_operation(operation)},
                    status_code=outcome.http_status or 202,
                    etag=strong_etag(operation.version),
                )
            claim = outcome.record

        operation = enqueue_delete_source(
            db,
            domain_id=domain_id,
            source_id=source_id,
            expected_version=expected_version,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
        if claim is not None:
            _complete_idempotent_claim(
                db,
                claim,
                http_status=202,
                response_kind="source_operation",
                response_refs={"operationId": operation.id},
            )
    except IdempotencyError as exc:
        raise _idempotency_api_error(exc) from exc
    except RuntimeConfigError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _runtime_config_api_error(exc) from exc
    except SourceError as exc:
        if claim is not None:
            _abandon_idempotent_claim(db, claim)
        raise _source_api_error(exc) from exc
    return _private_json_response(
        {"operation": safe_source_operation(operation)},
        status_code=202,
        etag=strong_etag(operation.version),
    )


@api_router.post(
    "/domains/{domainId}/evidence",
    response_model=RetrievalEvidenceResponseDto,
    responses={
        404: {"model": ErrorEnvelope, "description": "Domain not found."},
        409: {"model": ErrorEnvelope, "description": "Domain is not query eligible."},
        422: {"model": ErrorEnvelope, "description": "Request validation failed."},
        503: {"model": ErrorEnvelope, "description": "Retrieval is temporarily unavailable."},
    },
)
def retrieve_domain_evidence(
    payload: RetrievalEvidenceRequestDto,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    try:
        result = retrieve_scoped_evidence(db, settings=settings, domain_id=domain_id, question=payload.question)
    except EvidenceRetrievalError as exc:
        raise _evidence_api_error(exc) from exc
    try:
        response = RetrievalEvidenceResponseDto.model_validate(result)
    except ValidationError:
        raise ApiError(503, "dependency_unavailable", "Retrieval is temporarily unavailable.") from None
    return _private_json_response(response.model_dump(by_alias=True))


@api_router.get("/domains", response_model=MemberDomainListResponse)
def list_available_domains(
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    return _private_json_response({"domains": member_domain_list(db, settings)})


@api_router.get(
    "/documents",
    response_model=DocumentsListResponse,
    responses={
        410: {"model": ErrorEnvelope, "description": "Cursor expired."},
        422: {"model": ErrorEnvelope, "description": "Request validation failed."},
        503: {"model": ErrorEnvelope, "description": "Dependency unavailable."},
    },
)
def list_member_documents(
    request: Request,
    domain_id: Annotated[str | None, Query(alias="domainId", pattern=DOMAIN_ID_PATTERN)] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_DOCUMENT_PAGE_SIZE)] = DEFAULT_DOCUMENT_PAGE_SIZE,
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request, {"domainId", "query", "cursor", "limit"})
    normalized_query = query.strip() if query is not None else None
    if normalized_query == "":
        normalized_query = None
    try:
        payload = list_documents(
            db,
            settings,
            domain_id=domain_id,
            query=normalized_query,
            cursor=cursor,
            limit=limit,
        )
        response = DocumentsListResponse.model_validate(payload)
    except DocumentError as exc:
        raise _document_api_error(exc) from exc
    except ValidationError:
        raise ApiError(503, "dependency_unavailable", "Document library is temporarily unavailable.") from None
    return _private_json_response(response.model_dump(by_alias=True, mode="json"))


@api_router.get(
    "/documents/{documentRef}",
    response_model=DocumentDetailResponse,
    responses={
        404: {"model": ErrorEnvelope, "description": "Document not found."},
        422: {"model": ErrorEnvelope, "description": "Request validation failed."},
        503: {"model": ErrorEnvelope, "description": "Dependency unavailable."},
    },
)
def get_member_document(
    request: Request,
    document_ref: Annotated[str, Path(alias="documentRef", min_length=8, max_length=128)],
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request)
    try:
        payload = get_document(db, settings, document_ref)
        response = DocumentDetailResponse.model_validate(payload)
    except DocumentError as exc:
        raise _document_api_error(exc) from exc
    except ValidationError:
        raise ApiError(503, "dependency_unavailable", "Document library is temporarily unavailable.") from None
    return _private_json_response(response.model_dump(by_alias=True, mode="json"))


@api_router.get(
    "/documents/{documentRef}/content",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Full governed PDF preview.",
            "headers": {
                "Accept-Ranges": {"schema": {"type": "string"}},
                "ETag": {"schema": {"type": "string"}},
                "Content-Disposition": {"schema": {"type": "string"}},
                "Cache-Control": {"schema": {"type": "string"}},
                "X-Content-Type-Options": {"schema": {"type": "string"}},
            },
        },
        206: {
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Partial governed PDF preview.",
            "headers": {
                "Accept-Ranges": {"schema": {"type": "string"}},
                "Content-Range": {"schema": {"type": "string"}},
                "ETag": {"schema": {"type": "string"}},
                "Content-Disposition": {"schema": {"type": "string"}},
                "Cache-Control": {"schema": {"type": "string"}},
                "X-Content-Type-Options": {"schema": {"type": "string"}},
            },
        },
        404: {"model": ErrorEnvelope, "description": "Document not found."},
        409: {"model": ErrorEnvelope, "description": "Governed preview unavailable."},
        416: {
            "model": ErrorEnvelope,
            "description": "Range not satisfiable.",
            "headers": {"Content-Range": {"schema": {"type": "string"}}},
        },
        422: {"model": ErrorEnvelope, "description": "Request validation failed."},
        503: {"model": ErrorEnvelope, "description": "Document content unavailable."},
    },
)
def get_member_document_content(
    request: Request,
    document_ref: Annotated[str, Path(alias="documentRef", min_length=8, max_length=128)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    if_range: Annotated[str | None, Header(alias="If-Range")] = None,
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    _reject_unknown_query(request)
    try:
        result = get_document_content(
            db,
            settings,
            document_ref,
            range_header=range_header,
            if_range=if_range,
        )
    except DocumentError as exc:
        raise _document_api_error(exc) from exc

    headers = {
        "Cache-Control": "private, no-store, no-transform",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
        "ETag": result.etag,
        "Content-Disposition": result.content_disposition,
        "Content-Length": str(len(result.body)),
    }
    if result.content_range is not None:
        headers["Content-Range"] = result.content_range
    return Response(
        content=result.body,
        status_code=result.status_code,
        media_type="application/pdf",
        headers=headers,
    )


@api_router.get(
    "/evidence/{evidenceRef}/location",
    response_model=EvidenceLocationResponseDto,
    responses={
        404: {"model": ErrorEnvelope, "description": "Evidence not found."},
        409: {"model": ErrorEnvelope, "description": "Governed preview unavailable."},
        410: {"model": ErrorEnvelope, "description": "Evidence unavailable."},
        422: {"model": ErrorEnvelope, "description": "Request validation failed."},
        503: {"model": ErrorEnvelope, "description": "Dependency unavailable."},
    },
)
def get_member_evidence_location(
    request: Request,
    evidence_ref: Annotated[str, Path(alias="evidenceRef", min_length=8, max_length=128)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _reject_unknown_query(request)
    try:
        payload = get_evidence_location(
            db,
            settings,
            owner_user_id=current.user.id,
            evidence_ref=evidence_ref,
        )
        response = EvidenceLocationResponseDto.model_validate(payload)
    except DocumentError as exc:
        raise _document_api_error(exc) from exc
    except ValidationError:
        raise ApiError(503, "dependency_unavailable", "Evidence location is temporarily unavailable.") from None
    return _private_json_response(response.model_dump(by_alias=True, mode="json"))
