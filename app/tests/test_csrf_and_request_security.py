from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from context_engine.config import Settings
from context_engine.security import hash_session_token
from context_engine.services.csrf import (
    CSRF_PREAUTH_BINDING,
    CsrfTokenError,
    TEST_CSRF_SIGNING_KEY,
    issue_csrf_token,
    verify_csrf_token,
)
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
    RequestSecurityError,
    build_request_security_policy,
    enforce_request_security,
)


def _secured_settings(**overrides: object) -> Settings:
    values = {
        "testing": True,
        "public_origin": "http://ce.example.test",
        "internal_hosts": "testserver",
        "trusted_bff_peers": "testclient",
        "csrf_signing_key": TEST_CSRF_SIGNING_KEY,
        "session_cookie_secure": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_csrf_token_round_trip_binds_preauth_and_session() -> None:
    settings = _secured_settings()
    preauth = issue_csrf_token(settings, binding=CSRF_PREAUTH_BINDING)
    verify_csrf_token(settings, preauth, binding=CSRF_PREAUTH_BINDING)

    session_binding = hash_session_token("session-token")
    bound = issue_csrf_token(settings, binding=session_binding)
    verify_csrf_token(settings, bound, binding=session_binding)

    with pytest.raises(CsrfTokenError):
        verify_csrf_token(settings, preauth, binding=session_binding)
    with pytest.raises(CsrfTokenError):
        verify_csrf_token(settings, bound, binding=CSRF_PREAUTH_BINDING)


def test_request_security_policy_requires_complete_ingress_settings() -> None:
    with pytest.raises(ValueError, match="Trusted ingress"):
        build_request_security_policy(
            Settings(
                testing=False,
                public_origin="https://ce.example.test",
                internal_hosts="api.internal",
                trusted_bff_peers="10.0.0.0/8",
                csrf_signing_key=None,
            )
        )


def test_enforce_request_security_rejects_hostile_origin_and_csrf() -> None:
    settings = _secured_settings()
    policy = build_request_security_policy(settings)
    app = FastAPI()

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        try:
            enforce_request_security(request, settings, policy)
        except RequestSecurityError as exc:
            return JSONResponse({"code": exc.code}, status_code=exc.status_code)
        return await call_next(request)

    @app.post("/api/v1/probe")
    def probe() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        missing_origin = client.post(
            "/api/v1/probe",
            headers={
                PUBLIC_HOST_HEADER: "ce.example.test",
                PUBLIC_PROTO_HEADER: "http",
                CLIENT_BUCKET_HEADER: "bucket-a",
            },
        )
        assert missing_origin.status_code == 403
        assert missing_origin.json()["code"] == "csrf_invalid"

        token = issue_csrf_token(settings, binding=CSRF_PREAUTH_BINDING)
        client.cookies.set(settings.csrf_cookie_name, token, path="/")
        mismatched = client.post(
            "/api/v1/probe",
            headers={
                "Origin": "http://ce.example.test",
                PUBLIC_HOST_HEADER: "ce.example.test",
                PUBLIC_PROTO_HEADER: "http",
                CLIENT_BUCKET_HEADER: "bucket-a",
                CSRF_HEADER: "not-the-cookie",
            },
        )
        assert mismatched.status_code == 403
        assert mismatched.json()["code"] == "csrf_invalid"
