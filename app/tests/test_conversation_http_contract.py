from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from context_engine.api.contract_app import CANONICAL_API_PREFIX
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base, utc_now
from context_engine.models import (
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_REDACTED,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    PromptTemplate,
    User,
)
from context_engine.security import hash_session_token
from context_engine.services.auth import create_auth_session, create_user
from context_engine.services.csrf import TEST_CSRF_SIGNING_KEY, issue_csrf_token
from context_engine.services.request_security import (
    CLIENT_BUCKET_HEADER,
    CSRF_HEADER,
    PUBLIC_HOST_HEADER,
    PUBLIC_PROTO_HEADER,
)


def _context():
    database_path = f".data/ce-conversation-http-{uuid4().hex}.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        testing=True,
        public_origin="http://ce.example.test",
        internal_hosts="testserver",
        trusted_bff_peers="testclient",
        csrf_signing_key=TEST_CSRF_SIGNING_KEY,
        session_cookie_secure=False,
    )
    app = create_app(settings)
    app.state.test_database_path = Path(database_path).resolve()
    Base.metadata.create_all(app.state.engine)
    db = app.state.session_factory()
    try:
        owner = create_user(db, "owner-http@example.test", "Password123!")
        other = create_user(db, "other-http@example.test", "Password123!")
        owner_token, _ = create_auth_session(db, owner, settings)
        other_token, _ = create_auth_session(db, other, settings)
    finally:
        db.close()
    return app, settings, owner_token, other_token


@pytest.fixture
def conversation_http_context():
    context = _context()
    try:
        yield context
    finally:
        app = context[0]
        app.state.engine.dispose()
        app.state.test_database_path.unlink(missing_ok=True)


def _security(settings: Settings, token: str, bucket: str) -> tuple[dict[str, str], dict[str, str]]:
    csrf = issue_csrf_token(settings, binding=hash_session_token(token))
    headers = {
        "Origin": "http://ce.example.test",
        PUBLIC_HOST_HEADER: "ce.example.test",
        PUBLIC_PROTO_HEADER: "http",
        CLIENT_BUCKET_HEADER: bucket,
        CSRF_HEADER: csrf,
    }
    cookies = {
        settings.session_cookie_name: token,
        settings.csrf_cookie_name: csrf,
    }
    return headers, cookies


def test_m08_conversation_http_owner_etag_paging_and_denial_contract(
    conversation_http_context,
) -> None:
    app, settings, owner_token, other_token = conversation_http_context
    owner_headers, owner_cookies = _security(settings, owner_token, "owner-bucket")
    other_headers, other_cookies = _security(settings, other_token, "other-bucket")

    with TestClient(app) as client:
        created = client.post(
            f"{CANONICAL_API_PREFIX}/conversations",
            json={"title": "  Maintenance notes  "},
            headers=owner_headers,
            cookies=owner_cookies,
        )
        assert created.status_code == 201
        assert created.headers["cache-control"] == "private, no-store, no-transform"
        assert created.headers["etag"] == '"1"'
        conversation = created.json()["conversation"]
        assert conversation["id"].startswith("conv_")
        assert conversation["title"] == "Maintenance notes"
        assert conversation["version"] == 1
        assert set(conversation) == {"id", "title", "createdAt", "updatedAt", "version"}

        listing = client.get(
            f"{CANONICAL_API_PREFIX}/conversations",
            params={"limit": 1},
            headers=owner_headers,
            cookies=owner_cookies,
        )
        assert listing.status_code == 200
        assert listing.json() == {"conversations": [conversation], "nextCursor": None}

        detail = client.get(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            headers=owner_headers,
            cookies=owner_cookies,
        )
        assert detail.status_code == 200
        assert detail.headers["etag"] == '"1"'
        assert detail.json() == {"conversation": conversation, "turns": []}

        other_denial = client.get(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            headers=other_headers,
            cookies=other_cookies,
        )
        unknown_denial = client.get(
            f"{CANONICAL_API_PREFIX}/conversations/conv_{'0' * 32}",
            headers=other_headers,
            cookies=other_cookies,
        )
        assert other_denial.status_code == unknown_denial.status_code == 404
        for response in (other_denial, unknown_denial):
            assert response.headers["cache-control"] == "private, no-store, no-transform"
            assert response.json()["error"]["code"] == "not_found"
            assert response.json()["error"]["message"] == "Conversation not found."

        missing_precondition = client.patch(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            json={"title": "Renamed"},
            headers=owner_headers,
            cookies=owner_cookies,
        )
        assert missing_precondition.status_code == 428

        renamed = client.patch(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            json={"title": "Renamed"},
            headers={**owner_headers, "If-Match": '"1"'},
            cookies=owner_cookies,
        )
        assert renamed.status_code == 200
        assert renamed.headers["etag"] == '"2"'
        assert renamed.json()["conversation"]["version"] == 2

        stale = client.patch(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            json={"title": "Stale"},
            headers={**owner_headers, "If-Match": '"1"'},
            cookies=owner_cookies,
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "stale_revision"

        deleted = client.delete(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation['id']}",
            headers={**owner_headers, "If-Match": '"2"'},
            cookies=owner_cookies,
        )
        assert deleted.status_code == 204
        assert deleted.headers["cache-control"] == "private, no-store, no-transform"


def test_m08_conversation_mutations_require_origin_and_csrf(
    conversation_http_context,
) -> None:
    app, settings, owner_token, _ = conversation_http_context
    headers, cookies = _security(settings, owner_token, "csrf-bucket")
    with TestClient(app) as client:
        missing_origin = client.post(
            f"{CANONICAL_API_PREFIX}/conversations",
            json={},
            headers={key: value for key, value in headers.items() if key != "Origin"},
            cookies=cookies,
        )
        assert missing_origin.status_code == 403
        assert missing_origin.json()["error"]["code"] == "csrf_invalid"

        missing_csrf = client.post(
            f"{CANONICAL_API_PREFIX}/conversations",
            json={},
            headers={key: value for key, value in headers.items() if key != CSRF_HEADER},
            cookies=cookies,
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_invalid"


def test_m08_redacted_turn_detail_never_projects_stored_private_fields(
    conversation_http_context,
) -> None:
    app, settings, owner_token, _ = conversation_http_context
    headers, cookies = _security(settings, owner_token, "redacted-detail-bucket")
    db = app.state.session_factory()
    try:
        owner = db.scalar(select(User).where(User.username == "owner-http@example.test"))
        assert owner is not None
        conversation = Conversation(owner_user_id=owner.id, title="Redacted detail")
        template = PromptTemplate(name=f"Private {uuid4().hex}", body="Private template body")
        db.add_all([conversation, template])
        db.flush()
        turn = ConversationTurn(
            conversation_id=conversation.id,
            client_request_id="redacted-detail-request",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_REDACTED,
            stop_reason="redacted",
            user_message="The retained user question.",
            assistant_answer="PRIVATE ANSWER MUST NOT PROJECT",
            safe_error_code="private_error",
            safe_error_message="PRIVATE ERROR MUST NOT PROJECT",
            completed_at=utc_now(),
        )
        db.add(turn)
        db.flush()
        db.add(
            ConversationTurnComposerRef(
                turn_id=turn.id,
                ref_order=1,
                ref_kind="template",
                safe_label="PRIVATE LABEL MUST NOT PROJECT",
                safe_description="PRIVATE DESCRIPTION MUST NOT PROJECT",
                prompt_template_id=template.id,
            )
        )
        db.commit()
        conversation_ref = conversation.public_ref
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/conversations/{conversation_ref}",
            headers=headers,
            cookies=cookies,
        )

    assert response.status_code == 200
    projected = response.json()["turns"][0]
    assert projected["status"] == "redacted"
    assert projected["userMessage"] == "The retained user question."
    assert projected["assistantAnswer"] is None
    assert projected["evidence"] == []
    assert projected["acceptedRefs"] == []
    assert projected["error"] is None
    assert "PRIVATE" not in response.text
