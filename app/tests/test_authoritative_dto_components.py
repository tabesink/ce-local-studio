from __future__ import annotations

import json
from pathlib import Path


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

    turn = schemas["TurnDto"]
    assert turn["additionalProperties"] is False
    assert turn["properties"]["status"]["enum"] == ["running", "completed", "failed", "cancelled", "redacted"]
    assert turn["properties"]["domain"]["anyOf"][0]["$ref"] == "#/components/schemas/DomainSummaryDto"


def test_authoritative_components_are_available_to_generated_browser_types() -> None:
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    for component in EXPECTED_COMPONENTS:
        assert f"/** {component} */" in generated
        assert f"{component}:" in generated
