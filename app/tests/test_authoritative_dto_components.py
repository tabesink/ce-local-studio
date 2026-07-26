from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from context_engine.api import catalog_schemas
from context_engine.api.catalog_schemas import (
    RetrievalEvidenceRequestDto,
    RetrievalEvidenceResponseDto,
)

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "app" / "contracts" / "openapi.json"
GENERATED_TYPES = ROOT / "app" / "client" / "src" / "lib" / "api" / "generated" / "openapi.ts"

EXPECTED_COMPONENTS = {
    "AcceptedRefDto",
    "AdminDomainDto",
    "AdminSourceDto",
    "AllowedAction",
    "ComposerRefDto",
    "ConversationDetailDto",
    "ConversationSummaryDto",
    "CurrentUserDto",
    "DocumentSummaryDto",
    "DomainSummaryDto",
    "EmbeddingProfileSummaryDto",
    "EvidenceAnchorDto",
    "EvidenceItemDto",
    "EvidenceRegionDto",
    "ModelProfileDto",
    "OperationDto",
    "OperationErrorDto",
    "ProviderSummaryDto",
    "RetrievalEvidenceAnchorDto",
    "RetrievalEvidenceItemDto",
    "RetrievalEvidenceRequestDto",
    "RetrievalEvidenceResponseDto",
    "RuntimeSettingsDto",
    "TurnDto",
    "TurnErrorDto",
}


def _openapi() -> dict[str, object]:
    return json.loads(OPENAPI.read_text(encoding="utf-8"))


def test_authoritative_dto_catalog_is_generated_without_placeholder_routes() -> None:
    document = _openapi()
    schemas = document["components"]["schemas"]

    assert EXPECTED_COMPONENTS <= schemas.keys()
    assert all("schema" not in path.lower() for path in document["paths"])


def test_authoritative_components_are_closed_camel_case_contracts() -> None:
    schemas = _openapi()["components"]["schemas"]

    current_user = schemas["CurrentUserDto"]
    assert current_user["additionalProperties"] is False
    assert set(current_user["properties"]) == {"id", "displayName", "role", "disabled"}
    assert set(current_user["required"]) == {"id", "displayName", "role", "disabled"}
    assert current_user["properties"]["disabled"]["const"] is False
    assert current_user["properties"]["role"]["enum"] == ["member", "administrator"]

    domain = schemas["DomainSummaryDto"]
    assert domain["additionalProperties"] is False
    assert set(domain["properties"]) == {"id", "displayName", "state", "queryEligible"}
    assert domain["properties"]["state"]["enum"] == ["stopped", "running", "deleting"]

    evidence = schemas["EvidenceItemDto"]
    assert evidence["additionalProperties"] is False
    assert set(evidence["properties"]) == {
        "id",
        "citationLabel",
        "sourceLabel",
        "excerpt",
        "kind",
        "documentRef",
        "documentLabel",
        "anchor",
    }
    assert evidence["properties"]["excerpt"]["maxLength"] == 500
    assert evidence["properties"]["anchor"]["$ref"] == "#/components/schemas/EvidenceAnchorDto"
    assert "region" not in schemas["EvidenceAnchorDto"]["required"]

    retrieval_request = schemas["RetrievalEvidenceRequestDto"]
    assert retrieval_request["additionalProperties"] is False
    assert set(retrieval_request["properties"]) == {"question"}
    assert set(retrieval_request["required"]) == {"question"}
    assert retrieval_request["properties"]["question"]["minLength"] == 1
    assert retrieval_request["properties"]["question"]["maxLength"] == 2000

    retrieval_anchor = schemas["RetrievalEvidenceAnchorDto"]
    assert retrieval_anchor["additionalProperties"] is False
    assert set(retrieval_anchor["properties"]) == {
        "pageNumber",
        "sectionLabel",
        "fallback",
    }
    assert set(retrieval_anchor["required"]) == {"pageNumber", "fallback"}
    assert retrieval_anchor["properties"]["fallback"]["enum"] == ["section", "page"]
    assert "region" not in retrieval_anchor["properties"]

    retrieval_evidence = schemas["RetrievalEvidenceItemDto"]
    assert retrieval_evidence["additionalProperties"] is False
    assert set(retrieval_evidence["properties"]) == {
        "citationLabel",
        "sourceLabel",
        "excerpt",
        "kind",
        "documentRef",
        "documentLabel",
        "anchor",
    }
    assert "id" not in retrieval_evidence["properties"]
    assert retrieval_evidence["properties"]["excerpt"]["maxLength"] == 500
    assert retrieval_evidence["properties"]["anchor"]["anyOf"] == [
        {"$ref": "#/components/schemas/RetrievalEvidenceAnchorDto"},
        {"type": "null"},
    ]

    retrieval_response = schemas["RetrievalEvidenceResponseDto"]
    assert retrieval_response["oneOf"] == [
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

    assert retrieval_response["additionalProperties"] is False
    assert set(retrieval_response["properties"]) == {"result", "evidence"}
    assert retrieval_response["properties"]["result"]["enum"] == [
        "evidence_found",
        "no_grounded_context",
    ]
    assert retrieval_response["properties"]["evidence"]["items"]["$ref"] == (
        "#/components/schemas/RetrievalEvidenceItemDto"
    )

    turn = schemas["TurnDto"]
    assert turn["additionalProperties"] is False
    assert turn["properties"]["status"]["enum"] == ["running", "completed", "failed", "cancelled", "redacted"]
    assert turn["properties"]["domain"]["anyOf"][0]["$ref"] == "#/components/schemas/DomainSummaryDto"


def test_authoritative_components_are_available_to_generated_browser_types() -> None:
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    for component in EXPECTED_COMPONENTS:
        assert f"/** {component} */" in generated
        assert f"{component}:" in generated


def test_retrieval_request_trims_before_applying_length_bounds() -> None:
    assert RetrievalEvidenceRequestDto(question=" x ").question == "x"
    assert RetrievalEvidenceRequestDto(question=f" {'x' * 2000} ").question == "x" * 2000

    for invalid_question in ("   ", f" {'x' * 2001} "):
        with pytest.raises(ValidationError):
            RetrievalEvidenceRequestDto(question=invalid_question)


def test_retrieval_anchor_is_closed_and_never_accepts_regions() -> None:
    assert catalog_schemas.RetrievalEvidenceAnchorDto(
        pageNumber=8,
        sectionLabel="Relief valve",
        fallback="section",
    ).model_dump(by_alias=True) == {
        "pageNumber": 8,
        "sectionLabel": "Relief valve",
        "fallback": "section",
    }

    for invalid_anchor in (
        {"pageNumber": 8, "sectionLabel": None, "fallback": "region"},
        {
            "pageNumber": 8,
            "sectionLabel": None,
            "fallback": "page",
            "region": None,
        },
    ):
        with pytest.raises(ValidationError):
            catalog_schemas.RetrievalEvidenceAnchorDto.model_validate(invalid_anchor)


def test_retrieval_response_rejects_result_evidence_contradictions() -> None:
    evidence = {
        "citationLabel": "[1]",
        "sourceLabel": "manual.pdf",
        "excerpt": "Canonical excerpt.",
        "kind": "text",
        "documentRef": "document_ref_001",
        "documentLabel": "manual.pdf",
        "anchor": None,
    }

    for invalid_response in (
        {"result": "evidence_found", "evidence": []},
        {"result": "no_grounded_context", "evidence": [evidence]},
    ):
        with pytest.raises(ValidationError):
            RetrievalEvidenceResponseDto.model_validate(invalid_response)
