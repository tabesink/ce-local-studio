from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from context_engine.api import routes as routes_module
from context_engine.api.contract_app import (
    CANONICAL_API_PREFIX,
    CANONICAL_REQUEST_ID_HEADER,
)
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import User
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.evidence import EvidenceRetrievalError
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


def _http_app(tmp_path: Path, *, role: str = "member"):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / f'evidence-{role}.db'}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    user = User(
        username=f"{role}@example.test",
        password_hash="synthetic-password-hash",
        role=role,
    )
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(  # type: ignore[arg-type]
        user=user,
        auth_session=None,
    )
    return app


def _success_payload() -> dict[str, object]:
    return {
        "result": "evidence_found",
        "evidence": [
            {
                "citationLabel": "[1]",
                "sourceLabel": "manual.pdf",
                "excerpt": "SAFE-EXCERPT-SENTINEL",
                "kind": "figure",
                "documentRef": "docref-http-001",
                "documentLabel": "SAFE-DOCUMENT-LABEL.pdf",
                "anchor": {
                    "pageNumber": 8,
                    "sectionLabel": "Relief valve",
                    "fallback": "section",
                },
            }
        ],
    }


def _database_row_counts(app) -> dict[str, int]:
    with app.state.session_factory() as db:
        return {
            table.name: db.scalar(select(func.count()).select_from(table)) or 0
            for table in Base.metadata.sorted_tables
        }


@pytest.mark.parametrize("role", ["member", "administrator"])
def test_m02_stateless_evidence_http_returns_exact_closed_private_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    role: str,
) -> None:
    seen: dict[str, object] = {}
    private_question = "SENTINEL-PRIVATE-QUESTION"

    def retrieve(_db, *, settings, domain_id: str, question: str):
        seen.update(domain_id=domain_id, question=question, testing=settings.testing)
        return _success_payload()

    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", retrieve)
    app = _http_app(tmp_path, role=role)

    with TestClient(app) as client:
        before = _database_row_counts(app)
        writes: list[str] = []

        def capture_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
            normalized = statement.lstrip().upper()
            if normalized.startswith(("INSERT ", "UPDATE ", "DELETE ")):
                writes.append(normalized.split(maxsplit=1)[0])

        event.listen(app.state.engine, "before_cursor_execute", capture_writes)
        try:
            response = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                json={"question": f"  {private_question}  "},
            )
        finally:
            event.remove(app.state.engine, "before_cursor_execute", capture_writes)
        after = _database_row_counts(app)

    assert response.status_code == 200
    assert response.json() == _success_payload()
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert response.headers[CANONICAL_REQUEST_ID_HEADER]
    assert seen == {
        "domain_id": "domain-http-001",
        "question": private_question,
        "testing": True,
    }
    assert "sourceDocumentId" not in response.text
    assert "sourceBlockId" not in response.text
    assert after == before
    assert writes == []
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    for private_value in (
        private_question,
        "SAFE-EXCERPT-SENTINEL",
        "SAFE-DOCUMENT-LABEL.pdf",
    ):
        assert private_value not in rendered_logs


def test_m02_stateless_evidence_http_exhaustively_maps_safe_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cases = [
        ("domain_not_found", 404, "not_found"),
        ("domain_state_conflict", 409, "domain_not_query_eligible"),
        ("domain_runtime_unavailable", 409, "domain_not_query_eligible"),
        ("domain_no_eligible_sources", 409, "domain_not_query_eligible"),
        ("retrieval_capacity_unavailable", 503, "capacity_unavailable"),
        ("retrieval_dependency_unavailable", 503, "dependency_unavailable"),
        ("domain_runtime_dependency_unavailable", 503, "dependency_unavailable"),
        ("unexpected_internal_category", 503, "dependency_unavailable"),
    ]
    current = {"code": ""}

    def fail(*_args, **_kwargs):
        raise EvidenceRetrievalError(599, current["code"], "SENTINEL-PRIVATE-DEPENDENCY-EXCEPTION")

    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", fail)
    app = _http_app(tmp_path)

    with TestClient(app) as client:
        for internal_code, status_code, public_code in cases:
            current["code"] = internal_code
            response = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                json={"question": "Where is the valve?"},
            )

            body = response.json()
            assert response.status_code == status_code
            assert body["error"]["code"] == public_code
            assert body["error"]["requestId"] == response.headers[CANONICAL_REQUEST_ID_HEADER]
            assert body["error"]["fields"] == {}
            assert response.headers["cache-control"] == "private, no-store, no-transform"
            assert "SENTINEL-PRIVATE-DEPENDENCY-EXCEPTION" not in response.text

    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "SENTINEL-PRIVATE-DEPENDENCY-EXCEPTION" not in rendered_logs


def test_m02_stateless_evidence_http_rejects_invalid_input_before_retrieval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def unexpected(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", unexpected)
    app = _http_app(tmp_path)

    with TestClient(app) as client:
        for payload in (
            {"question": "   "},
            {"question": "x" * 2001},
            {"question": "valid", "privateField": "SENTINEL-PRIVATE"},
        ):
            response = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                json=payload,
            )

            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"
            assert response.headers["cache-control"] == "private, no-store, no-transform"
            assert "SENTINEL-PRIVATE" not in response.text
    assert called is False


def test_m02_stateless_evidence_http_trims_before_question_length_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def retrieve(_db, *, settings, domain_id: str, question: str):
        seen.append(question)
        return {"result": "no_grounded_context", "evidence": []}

    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", retrieve)
    app = _http_app(tmp_path)
    normalized = "x" * 2000

    with TestClient(app) as client:
        response = client.post(
            f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
            json={"question": f" {normalized} "},
        )

    assert response.status_code == 200
    assert seen == [normalized]


def test_m02_stateless_evidence_http_fails_closed_on_private_response_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _success_payload()
    payload["evidence"][0]["sourceDocumentId"] = "SENTINEL-PRIVATE-SOURCE-ID"  # type: ignore[index]
    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", lambda *_args, **_kwargs: payload)
    app = _http_app(tmp_path)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
            json={"question": "Where is the valve?"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert "SENTINEL-PRIVATE-SOURCE-ID" not in response.text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["evidence"][0]["anchor"].update({"region": None}),
        lambda payload: payload["evidence"][0]["anchor"].update({"fallback": "region"}),
        lambda payload: payload.update({"result": "no_grounded_context"}),
        lambda payload: payload.update({"evidence": []}),
    ],
)
def test_m02_stateless_evidence_http_fails_closed_on_invalid_anchor_or_result_pairing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
) -> None:
    payload = _success_payload()
    mutate(payload)
    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", lambda *_args, **_kwargs: payload)
    app = _http_app(tmp_path)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
            json={"question": "Where is the valve?"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert response.headers["cache-control"] == "private, no-store, no-transform"


def test_m02_stateless_evidence_http_denies_missing_disabled_revoked_and_expired_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def unexpected(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(routes_module, "retrieve_scoped_evidence", unexpected)
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'evidence-auth.db'}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    session = app.state.session_factory()
    try:
        disabled = User(
            username="disabled@example.test",
            password_hash="synthetic-password-hash",
            is_disabled=True,
        )
        revoked = User(username="revoked@example.test", password_hash="synthetic-password-hash")
        expired = User(username="expired@example.test", password_hash="synthetic-password-hash")
        session.add_all([disabled, revoked, expired])
        session.commit()
        disabled_token, _ = create_auth_session(session, disabled, settings)
        revoked_token, revoked_session = create_auth_session(session, revoked, settings)
        expired_token, expired_session = create_auth_session(session, expired, settings)
        revoked_session.revoked_at = utc_now()
        expired_session.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()

        with TestClient(app) as client:
            for token in (None, disabled_token, revoked_token, expired_token):
                if token is None:
                    client.cookies.delete(settings.session_cookie_name, path="/")
                else:
                    client.cookies.set(settings.session_cookie_name, token, path="/")
                response = client.post(
                    f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                    json={"question": "Where is the valve?"},
                )
                assert response.status_code == 401
                assert response.json()["error"]["code"] == "unauthenticated"
                assert response.headers["cache-control"] == "private, no-store, no-transform"
    finally:
        session.close()

    assert called is False


def test_m02_stateless_evidence_http_enforces_origin_and_session_bound_csrf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        routes_module,
        "retrieve_scoped_evidence",
        lambda *_args, **_kwargs: {"result": "no_grounded_context", "evidence": []},
    )
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'evidence-csrf.db'}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key=TEST_CSRF_SIGNING_KEY,
        session_cookie_secure=False,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    session = app.state.session_factory()
    try:
        user = User(username="csrf-member@example.test", password_hash="synthetic-password-hash")
        session.add(user)
        session.commit()
        token, _ = create_auth_session(session, user, settings)
        csrf = issue_csrf_token(settings, binding=hash_session_token(token))
        trusted = {
            PUBLIC_HOST_HEADER: "ce.example.test",
            PUBLIC_PROTO_HEADER: "http",
            CLIENT_BUCKET_HEADER: "evidence-csrf",
        }

        with TestClient(app) as client:
            client.cookies.set(settings.session_cookie_name, token, path="/")
            client.cookies.set(settings.csrf_cookie_name, csrf, path="/")
            hostile = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                headers={**trusted, "Origin": "http://evil.example.test", CSRF_HEADER: csrf},
                json={"question": "Where is the valve?"},
            )
            missing = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                headers={**trusted, "Origin": "http://ce.example.test"},
                json={"question": "Where is the valve?"},
            )
            invalid = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                headers={
                    **trusted,
                    "Origin": "http://ce.example.test",
                    CSRF_HEADER: "not-the-cookie",
                },
                json={"question": "Where is the valve?"},
            )
            valid = client.post(
                f"{CANONICAL_API_PREFIX}/domains/domain-http-001/evidence",
                headers={**trusted, "Origin": "http://ce.example.test", CSRF_HEADER: csrf},
                json={"question": "Where is the valve?"},
            )

        for denied in (hostile, missing, invalid):
            assert denied.status_code == 403
            assert denied.json()["error"]["code"] == "csrf_invalid"
            assert denied.headers["cache-control"] == "private, no-store, no-transform"
        assert valid.status_code == 200
        assert valid.json() == {"result": "no_grounded_context", "evidence": []}
    finally:
        session.close()
