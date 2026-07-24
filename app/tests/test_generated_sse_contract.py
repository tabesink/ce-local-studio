from __future__ import annotations

import json
from pathlib import Path

from context_engine.api.sse_schemas import TURN_STREAM_EVENT_ADAPTER


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "app" / "contracts"
SSE_FIXTURES = ROOT / "app" / "tests" / "fixtures" / "sse"


def test_standalone_public_dto_and_sse_schemas_are_versioned_and_closed() -> None:
    public = json.loads((CONTRACTS / "public-dtos.schema.json").read_text())
    sse = json.loads((CONTRACTS / "sse-events.schema.json").read_text())

    assert public["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert public["$id"] == "urn:context-engine:public-dtos:1.0"
    assert {"CurrentUserDto", "EvidenceItemDto", "TurnDto"} <= public["$defs"].keys()
    assert sse["$id"] == "urn:context-engine:sse-events:1.0"
    assert sse["discriminator"]["propertyName"] == "type"
    assert len(sse["oneOf"]) == 10


def test_all_committed_sse_transcripts_validate_with_production_schema() -> None:
    fixture_paths = sorted(SSE_FIXTURES.glob("*.sse"))
    assert fixture_paths
    for path in fixture_paths:
        for line in path.read_text().splitlines():
            if line.startswith("data: "):
                TURN_STREAM_EVENT_ADAPTER.validate_python(json.loads(line.removeprefix("data: ")))


def test_chat_adapter_uses_generated_sse_union() -> None:
    api = (ROOT / "app/client/src/features/chat-shell/api.ts").read_text()
    generated = (ROOT / "app/client/src/lib/api/generated/sse.ts").read_text()

    assert 'components as sseComponents' in api
    assert 'TurnStreamEvent = sseComponents["schemas"]["TurnStreamEvent"]' in api
    assert "TurnStreamEvent:" in generated
    assert '"turn.redacted"' in generated
