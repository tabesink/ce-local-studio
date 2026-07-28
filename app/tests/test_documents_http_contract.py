from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from context_engine.api import routes as routes_module
from context_engine.api.contract_app import CANONICAL_API_PREFIX, CANONICAL_REQUEST_ID_HEADER
from context_engine.api.dependencies import CurrentSession, require_current_session
from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.db import Base
from context_engine.models import (
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_COMPLETED,
    Conversation,
    ConversationTurn,
    ConversationTurnEvidenceRef,
    User,
)
from context_engine.services.documents import DocumentContentResult, DocumentError


def _http_app(tmp_path: Path, *, role: str = "member", user_id: str = "user-docs-001"):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / f'docs-{role}-{user_id}.db'}", testing=True)
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    # Keep the session user transient so CurrentSession can read attributes without a live ORM session.
    user = User(
        id=user_id,
        username=f"{role}-{user_id}@example.test",
        password_hash="synthetic-password-hash",
        role=role,
    )
    app.dependency_overrides[require_current_session] = lambda: CurrentSession(  # type: ignore[arg-type]
        user=user,
        auth_session=None,
    )
    return app


def _document_summary(*, preview_kind: str = "pdf") -> dict[str, object]:
    return {
        "ref": "doc_libraryref00000000000001",
        "label": "pump-service-manual.pdf",
        "domain": {
            "id": "domain-manuals",
            "displayName": "Equipment Manuals",
            "state": "running",
            "queryEligible": True,
        },
        "contentType": "application/pdf",
        "previewKind": preview_kind,
        "pageCount": 24,
        "updatedAt": "2026-07-25T12:05:00Z",
    }


@pytest.mark.parametrize("role", ["member", "administrator"])
def test_list_documents_http_returns_closed_private_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    monkeypatch.setattr(
        routes_module,
        "list_documents",
        lambda *_args, **_kwargs: {"documents": [_document_summary()], "nextCursor": None},
    )
    app = _http_app(tmp_path, role=role)
    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/documents")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert response.headers[CANONICAL_REQUEST_ID_HEADER]
    body = response.json()
    assert body == {"documents": [_document_summary()], "nextCursor": None}
    for forbidden in ("originalSha256", "originalObjectKey", "obj_", "sourceDocumentId"):
        assert forbidden not in response.text


def test_get_document_http_maps_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args, **_kwargs):
        raise DocumentError(404, "document_not_found", "Document not found.")

    monkeypatch.setattr(routes_module, "get_document", boom)
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/documents/doc_missingref000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
    assert "fields" in response.json()["error"]


def test_document_content_http_full_and_range_and_unsatisfiable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_bytes = b"%PDF-1.4 synthetic-preview-bytes-0123456789"

    def content(_db, _settings, document_ref: str, *, range_header=None, if_range=None):
        assert document_ref == "doc_libraryref00000000000001"
        if range_header == "bytes=9999-10000":
            raise DocumentError(
                416,
                "range_not_satisfiable",
                "Requested range is not satisfiable.",
                headers={"Content-Range": f"bytes */{len(pdf_bytes)}"},
            )
        if range_header == "bytes=0-9":
            return DocumentContentResult(
                status_code=206,
                body=pdf_bytes[:10],
                total_size=len(pdf_bytes),
                etag='"preview-etag-1"',
                content_disposition='inline; filename="pump-service-manual.pdf"',
                content_range=f"bytes 0-9/{len(pdf_bytes)}",
            )
        return DocumentContentResult(
            status_code=200,
            body=pdf_bytes,
            total_size=len(pdf_bytes),
            etag='"preview-etag-1"',
            content_disposition='inline; filename="pump-service-manual.pdf"',
        )

    monkeypatch.setattr(routes_module, "get_document_content", content)
    app = _http_app(tmp_path)
    path = f"{CANONICAL_API_PREFIX}/documents/doc_libraryref00000000000001/content"

    with TestClient(app) as client:
        full = client.get(path)
        ranged = client.get(path, headers={"Range": "bytes=0-9"})
        bad = client.get(path, headers={"Range": "bytes=9999-10000"})

    assert full.status_code == 200
    assert full.headers["content-type"].startswith("application/pdf")
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["etag"] == '"preview-etag-1"'
    assert full.headers["cache-control"] == "private, no-store, no-transform"
    assert full.headers["x-content-type-options"] == "nosniff"
    assert "inline; filename=" in full.headers["content-disposition"]
    assert full.content == pdf_bytes

    assert ranged.status_code == 206
    assert ranged.headers["content-range"] == f"bytes 0-9/{len(pdf_bytes)}"
    assert ranged.content == pdf_bytes[:10]

    assert bad.status_code == 416
    assert bad.json()["error"]["code"] == "range_not_satisfiable"
    assert bad.headers["content-range"] == f"bytes */{len(pdf_bytes)}"


def test_document_content_http_non_pdf_preview_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args, **_kwargs):
        raise DocumentError(
            409,
            "document_preview_unavailable",
            "A governed PDF preview is not available for this document.",
        )

    monkeypatch.setattr(routes_module, "get_document_content", boom)
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/documents/doc_libraryref00000000000001/content")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_preview_unavailable"


def test_evidence_location_http_error_code_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = [
        ("evidence_not_found", 404, "evidence_not_found"),
        ("evidence_unavailable", 410, "evidence_unavailable"),
        ("document_preview_unavailable", 409, "document_preview_unavailable"),
    ]
    current = {"code": ""}

    def locate(*_args, **_kwargs):
        raise DocumentError(404, current["code"], "mapped")

    monkeypatch.setattr(routes_module, "get_evidence_location", locate)
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        for code, status, public in cases:
            current["code"] = code
            response = client.get(f"{CANONICAL_API_PREFIX}/evidence/ev_locationref000000000001/location")
            assert response.status_code == status
            assert response.json()["error"]["code"] == public


def test_evidence_location_http_wrong_owner_is_404_without_service_mock(tmp_path: Path) -> None:
    owner_id = "user-owner-docs"
    caller_id = "user-caller-docs"
    app = _http_app(tmp_path, user_id=caller_id)
    evidence_ref = "ev_" + "e" * 32
    with Session(app.state.engine) as db:
        # Ownership fails before source/domain eligibility — seed only the private chat graph.
        owner = User(id=owner_id, username="owner@example.test", password_hash="synthetic")
        conversation = Conversation(
            id=str(uuid4()),
            public_ref="conv_" + "c" * 32,
            owner_user_id=owner_id,
            title="Owned",
        )
        turn = ConversationTurn(
            id=str(uuid4()),
            public_ref="turn_" + "t" * 32,
            conversation_id=conversation.id,
            client_request_id="loc-http-1",
            route=TURN_ROUTE_DIRECT_LLM,
            status=TURN_STATUS_COMPLETED,
            user_message="q",
            assistant_answer="a",
        )
        evidence = ConversationTurnEvidenceRef(
            id=str(uuid4()),
            public_ref=evidence_ref,
            turn_id=turn.id,
            evidence_order=1,
            source_document_id=str(uuid4()),
            source_block_id=str(uuid4()),
            citation_label="[1]",
            source_label="pump.pdf",
            excerpt="excerpt",
        )
        db.add_all([owner, conversation, turn, evidence])
        db.commit()

    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/evidence/{evidence_ref}/location")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "evidence_not_found"


def test_evidence_location_http_success_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "evidence": {"id": "ev_locationref000000000001", "citationLabel": "[1]", "kind": "figure"},
        "document": {
            "ref": "doc_libraryref00000000000001",
            "label": "pump-service-manual.pdf",
            "previewKind": "pdf",
            "pageCount": 24,
        },
        "anchor": {
            "pageNumber": 18,
            "region": None,
            "sectionLabel": "4.2 Relief valve",
            "fallback": "section",
        },
    }
    monkeypatch.setattr(routes_module, "get_evidence_location", lambda *_a, **_k: payload)
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/evidence/ev_locationref000000000001/location")

    assert response.status_code == 200
    assert response.json() == payload
    assert "sourceDocumentId" not in response.text
    assert "originalObjectKey" not in response.text


def test_evidence_location_http_success_with_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "evidence": {"id": "ev_locationref000000000001", "citationLabel": "[1]", "kind": "figure"},
        "document": {
            "ref": "doc_libraryref00000000000001",
            "label": "pump-service-manual.pdf",
            "previewKind": "pdf",
            "pageCount": 24,
        },
        "anchor": {
            "pageNumber": 18,
            "region": {"x": 0.12, "y": 0.24, "width": 0.66, "height": 0.41},
            "sectionLabel": "4.2 Relief valve",
            "fallback": "region",
        },
    }
    monkeypatch.setattr(routes_module, "get_evidence_location", lambda *_a, **_k: payload)
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"{CANONICAL_API_PREFIX}/evidence/ev_locationref000000000001/location")

    assert response.status_code == 200
    assert response.json() == payload
    for forbidden in ("sourceDocumentId", "originalObjectKey", "block_valve", "region_x"):
        assert forbidden not in response.text


@pytest.mark.parametrize("query", ["x=0.1", "region=1", "y=0&width=1"])
def test_evidence_location_http_rejects_coordinate_query_params(
    tmp_path: Path,
    query: str,
) -> None:
    app = _http_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(
            f"{CANONICAL_API_PREFIX}/evidence/ev_locationref000000000001/location?{query}"
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
