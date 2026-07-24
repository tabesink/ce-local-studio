from __future__ import annotations

from context_engine.services.readiness import ReadinessError, check_readiness

from datetime import datetime
from email.parser import BytesParser
from email.policy import default as email_policy
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, Path, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from context_engine.api.catalog_schemas import (
    ModelProfileDto,
    ProviderSummaryDto,
    RuntimeSettingsDto,
)
from context_engine.api.dependencies import CurrentSession, get_db, get_settings, require_admin, require_current_session
from context_engine.api.errors import ApiError, request_id_from
from context_engine.api.public_schemas import ErrorEnvelope, CsrfResponse, LiveHealthResponse, ReadyHealthResponse
from context_engine.config import Settings
from context_engine.models import (
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.audit import AuditContext
from context_engine.services.auth import (
    authenticate_user,
    create_auth_session,
    iso_utc,
    revoke_session_token,
    safe_user,
)
from context_engine.services.csrf import CSRF_PREAUTH_BINDING, issue_csrf_token
from context_engine.services.login_throttle import (
    LoginRateLimited,
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from context_engine.services.chat_turns import (
    ChatTurnError,
    cancel_turn,
    conversation_turn_summaries,
    encode_sse_event,
    safe_turn_summary,
    stream_turn_events,
    stream_turn_events_by_turn,
)
from context_engine.services.composer_refs import (
    ComposerRefError,
    MAX_COMPOSER_REFS,
    MAX_DISCOVERY_LIMIT,
    discover_composer_refs,
)
from context_engine.services.conversations import (
    ConversationError,
    create_conversation,
    delete_conversation,
    get_owned_conversation,
    list_conversations,
    safe_conversation_summary,
    update_conversation_title,
)
from context_engine.services.runtime_config import (
    RuntimeConfigError,
    SecretCrypto,
    create_model_profile,
    delete_model_profile,
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
from context_engine.services.domains import (
    DOMAIN_ID_PATTERN,
    DomainError,
    admin_domain_list,
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
    controller_from_settings,
)
from context_engine.services.evidence import EvidenceRetrievalError, retrieve_scoped_evidence
from context_engine.services.indexing import SourceIndexError, cancel_source_index, retry_source_index
from context_engine.services.sources import (
    MAX_SOURCE_FILE_SIZE_BYTES,
    SourceError,
    cancel_source,
    delete_source,
    list_sources,
    retry_source,
    safe_source,
    safe_source_operation,
    source_detail,
    source_operations,
    source_outline,
    upload_source_bytes,
)


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

    model_config = ConfigDict(extra="forbid")


class EvidenceRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question is required.")
        return stripped


class ComposerRefDiscoverRequest(BaseModel):
    conversation_id: str | None = Field(default=None, alias="conversationId", max_length=36)
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


class ConversationTitleRequest(BaseModel):
    title: str | None = None

    model_config = ConfigDict(extra="forbid")


class TurnStreamRequest(BaseModel):
    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    domain_id: str | None = Field(default=None, alias="domainId", max_length=64)
    composer_ref_tokens: list[str] = Field(default_factory=list, alias="composerRefTokens", max_length=MAX_COMPOSER_REFS)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EvidenceItemResponse(BaseModel):
    excerpt: str = Field(max_length=500)
    source_label: str = Field(alias="sourceLabel", max_length=255)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EvidenceResponse(BaseModel):
    result: Literal["evidence_found", "no_grounded_context"]
    evidence: list[EvidenceItemResponse]

    model_config = ConfigDict(extra="forbid")


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
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        check_readiness(db)
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


@api_router.get("/admin/users")
def admin_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    users = list(db.scalars(select(User).order_by(User.username)))
    return {"users": [safe_user(user) for user in users]}


def _runtime_config_api_error(exc: RuntimeConfigError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _domain_api_error(exc: DomainError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _source_api_error(exc: SourceError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _source_index_api_error(exc: SourceIndexError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _evidence_api_error(exc: EvidenceRetrievalError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _conversation_api_error(exc: ConversationError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _composer_ref_api_error(exc: ComposerRefError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _chat_turn_api_error(exc: ChatTurnError) -> ApiError:
    return ApiError(exc.status_code, exc.code, exc.message)


def _audit_context(request: Request, user: User) -> AuditContext:
    return AuditContext(actor_user=user, request_id=request_id_from(request))


def _parse_optional_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.removesuffix("Z"))
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Request validation failed.") from exc


def _multipart_file_from_request(request: Request, body: bytes) -> tuple[str | None, str | None, bytes]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        raise ApiError(422, "validation_error", "Request validation failed.")
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=email_policy).parsebytes(header + body)
    if not message.is_multipart():
        raise ApiError(422, "validation_error", "Request validation failed.")
    for part in message.iter_parts():
        disposition = part.get("content-disposition", "")
        if part.get_param("name", header="content-disposition") == "file" and "form-data" in disposition:
            payload = part.get_payload(decode=True)
            if payload is None:
                raise ApiError(422, "validation_error", "Request validation failed.")
            return part.get_filename(), part.get_content_type(), payload
    raise ApiError(422, "validation_error", "Request validation failed.")


@api_router.post("/composer-refs:discover")
def post_composer_refs_discover(
    payload: ComposerRefDiscoverRequest,
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
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
    return {"refs": refs}


@api_router.get("/conversations")
def get_conversations(
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return {"conversations": list_conversations(db, owner=current.user)}


@api_router.post("/conversations", status_code=201)
def post_conversation(
    payload: ConversationTitleRequest | None = Body(default=None),
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        conversation = create_conversation(db, owner=current.user, title=payload.title if payload else None)
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return {"conversation": safe_conversation_summary(conversation)}


@api_router.get("/conversations/{conversationId}")
def get_conversation(
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        conversation = get_owned_conversation(db, owner=current.user, conversation_id=conversation_id)
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return {"conversation": safe_conversation_summary(conversation), "turns": conversation_turn_summaries(db, conversation)}


@api_router.patch("/conversations/{conversationId}")
def patch_conversation(
    payload: ConversationTitleRequest,
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        conversation = update_conversation_title(
            db,
            owner=current.user,
            conversation_id=conversation_id,
            title=payload.title,
        )
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return {"conversation": safe_conversation_summary(conversation)}


@api_router.delete("/conversations/{conversationId}", status_code=204)
def remove_conversation(
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_conversation(db, owner=current.user, conversation_id=conversation_id)
    except ConversationError as exc:
        raise _conversation_api_error(exc) from exc
    return Response(status_code=204)



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
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    events = stream_turn_events(
        db,
        settings=settings,
        owner=current.user,
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


@api_router.get("/conversations/{conversationId}/turns/{turnId}/events")
def get_conversation_turn_events(
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    turn_id: Annotated[str, Path(alias="turnId", min_length=1, max_length=36)],
    after: int = Query(default=0, ge=0),
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    events = stream_turn_events_by_turn(
        db,
        owner=current.user,
        conversation_id=conversation_id,
        turn_id=turn_id,
        after=after,
    )
    return _streaming_sse_response(None, events)


@api_router.post("/conversations/{conversationId}/turns/{turnId}:cancel", status_code=202)
def post_conversation_turn_cancel(
    conversation_id: Annotated[str, Path(alias="conversationId", min_length=1, max_length=36)],
    turn_id: Annotated[str, Path(alias="turnId", min_length=1, max_length=36)],
    current: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        turn = cancel_turn(
            db,
            owner=current.user,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )
    except ChatTurnError as exc:
        raise _chat_turn_api_error(exc) from exc
    return {"turn": safe_turn_summary(turn)}


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
) -> JSONResponse:
    try:
        profile = create_model_profile(
            db,
            name=payload.name,
            profile_kind=payload.profile_kind,
            provider_kind=payload.provider_kind,
            model_name=payload.model_name,
            vector_dimensions=payload.vector_dimensions,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
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


@api_router.post("/admin/domains", status_code=201)
def admin_create_domain(
    request: Request,
    payload: DomainCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        domain = create_domain(
            db,
            settings=settings,
            domain_id=payload.id,
            display_name=payload.display_name,
            embedding_profile_id=payload.embedding_profile_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except RuntimeConfigError as exc:
        raise _runtime_config_api_error(exc) from exc
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return {"domain": safe_domain_admin(db, settings, domain, controller_from_settings(settings))}


@api_router.get("/admin/domains")
def admin_list_domains(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"domains": admin_domain_list(db, settings)}


@api_router.get("/admin/domains/{domainId}")
def admin_get_domain(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return {"domain": domain_detail(db, settings, domain_id)}
    except DomainError as exc:
        raise _domain_api_error(exc) from exc


@api_router.get("/admin/domains/{domainId}/status")
def admin_get_domain_status(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return domain_status(db, settings, domain_id)
    except DomainError as exc:
        raise _domain_api_error(exc) from exc


@api_router.post("/admin/domains/{domainId}/start")
def admin_start_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        domain = start_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return {"domain": safe_domain_admin(db, settings, domain, controller_from_settings(settings))}


@api_router.post("/admin/domains/{domainId}/stop")
def admin_stop_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        domain = stop_domain(
            db,
            settings=settings,
            domain_id=domain_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return {"domain": safe_domain_admin(db, settings, domain, controller_from_settings(settings))}


@api_router.delete("/admin/domains/{domainId}", status_code=202)
def admin_delete_domain(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        operation = enqueue_delete_domain(
            db,
            domain_id=domain_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except DomainError as exc:
        raise _domain_api_error(exc) from exc
    return {"operation": safe_domain_operation(operation)}


@api_router.get("/admin/domains/{domainId}/operations")
def admin_domain_operations(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"operations": domain_operations(db, domain_id)}
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
) -> dict[str, object]:
    filename, content_type, data = _multipart_file_from_request(request, await request.body())
    if len(data) > MAX_SOURCE_FILE_SIZE_BYTES:
        raise _source_api_error(SourceError(413, "source_file_too_large", "File is too large."))
    try:
        source, operation = upload_source_bytes(
            db,
            settings=settings,
            domain_id=domain_id,
            filename=filename,
            content_type=content_type,
            data=data,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    return {"source": safe_source(db, source), "operation": safe_source_operation(operation)}


@api_router.get("/admin/domains/{domainId}/sources")
def admin_list_sources(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"sources": list_sources(db, domain_id)}
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.get("/admin/domains/{domainId}/sources/{sourceId}")
def admin_get_source(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"source": source_detail(db, domain_id, source_id)}
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.get("/admin/domains/{domainId}/sources/{sourceId}/outline")
def admin_get_source_outline(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"items": source_outline(db, domain_id, source_id)}
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.get("/admin/domains/{domainId}/sources/{sourceId}/operations")
def admin_source_operations(
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return {"operations": source_operations(db, domain_id, source_id)}
    except SourceError as exc:
        raise _source_api_error(exc) from exc


@api_router.post("/admin/domains/{domainId}/sources/{sourceId}/index/retry", status_code=202)
def admin_retry_source_index(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        source = retry_source_index(
            db,
            settings=settings,
            domain_id=domain_id,
            source_id=source_id,
            audit_context=_audit_context(request, admin),
        )
    except SourceIndexError as exc:
        raise _source_index_api_error(exc) from exc
    return {"source": safe_source(db, source)}


@api_router.post("/admin/domains/{domainId}/sources/{sourceId}/index/cancel")
def admin_cancel_source_index(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
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
    return {"source": safe_source(db, source)}


@api_router.post("/admin/domains/{domainId}/sources/{sourceId}/retry", status_code=202)
def admin_retry_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        operation = retry_source(
            db,
            domain_id=domain_id,
            source_id=source_id,
            requested_by_user=admin,
            audit_context=_audit_context(request, admin),
        )
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    return {"operation": safe_source_operation(operation)}


@api_router.post("/admin/domains/{domainId}/sources/{sourceId}/cancel")
def admin_cancel_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        operation = cancel_source(
            db,
            domain_id=domain_id,
            source_id=source_id,
            audit_context=_audit_context(request, admin),
        )
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    return {"operation": safe_source_operation(operation)}


@api_router.delete("/admin/domains/{domainId}/sources/{sourceId}", status_code=204)
def admin_delete_source(
    request: Request,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    source_id: Annotated[str, Path(alias="sourceId", min_length=1, max_length=36)],
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        delete_source(
            db,
            settings=settings,
            domain_id=domain_id,
            source_id=source_id,
            audit_context=_audit_context(request, admin),
        )
    except SourceError as exc:
        raise _source_api_error(exc) from exc
    except SourceIndexError as exc:
        raise _source_index_api_error(exc) from exc
    return Response(status_code=204)


@api_router.post("/domains/{domainId}/evidence", response_model=EvidenceResponse)
def retrieve_domain_evidence(
    payload: EvidenceRequest,
    domain_id: Annotated[str, Path(alias="domainId", pattern=DOMAIN_ID_PATTERN)],
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return retrieve_scoped_evidence(db, settings=settings, domain_id=domain_id, question=payload.question)
    except EvidenceRetrievalError as exc:
        raise _evidence_api_error(exc) from exc


@api_router.get("/domains")
def list_available_domains(
    _: CurrentSession = Depends(require_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return {"domains": member_domain_list(db, settings)}
