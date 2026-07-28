"""P10-05 U6: killable Docling timeout and Reducto URL/asset transport (AE5/AE6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_engine.adapters.parser_runtime import (
    materialize_reducto_remote_assets,
    resolve_reducto_url_result,
    run_docling_convert_killable,
)
from context_engine.adapters.parsers import (
    PARSER_DOCLING,
    PARSER_REDUCTO,
    DoclingDocumentParser,
    ParserAdapterError,
    ParserRequest,
    dump_prepared_source_for_privacy_scan,
    normalize_docling_document,
    normalize_reducto_parse_response,
    validate_prepared_source,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "parsers"
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_docling_fixture_normalizes_ordered_blocks_without_provider_fields() -> None:
    payload = json.loads((FIXTURES / "docling_export_dict.json").read_text(encoding="utf-8"))
    prepared = normalize_docling_document("src-docling-fix", PARSER_DOCLING, payload)
    validate_prepared_source(prepared)
    assert [block.kind for block in prepared.blocks] == ["text", "text", "table", "figure"]
    assert "Procedure" in prepared.blocks[0].canonical_markdown
    scanned = dump_prepared_source_for_privacy_scan(prepared)
    assert "self_ref" not in scanned
    assert "prov" not in scanned


def test_reducto_url_result_resolves_privately_before_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    pointer = json.loads((FIXTURES / "reducto_url_pointer.json").read_text(encoding="utf-8"))
    resolved_body = json.loads((FIXTURES / "reducto_url_resolved_body.json").read_text(encoding="utf-8"))

    def fake_get_json(url: str, *, timeout_seconds: float) -> dict:
        assert "presigned-result" in url
        assert timeout_seconds > 0
        return resolved_body

    monkeypatch.setattr(
        "context_engine.adapters.parser_runtime._httpx_get_json",
        fake_get_json,
    )
    resolved = resolve_reducto_url_result(pointer, timeout_seconds=5.0)
    assert resolved["result"]["type"] == "full"
    assert "url" not in resolved["result"]
    assert "job_id" not in resolved
    prepared = normalize_reducto_parse_response("src-url", PARSER_REDUCTO, resolved)
    validate_prepared_source(prepared)
    scanned = dump_prepared_source_for_privacy_scan(prepared)
    assert "example.invalid" not in scanned
    assert "job-secret" not in scanned


def test_reducto_remote_asset_materialize_strips_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "result": {
            "type": "full",
            "chunks": [
                {
                    "blocks": [
                        {
                            "type": "Figure",
                            "content": "Valve",
                            "page": 1,
                            "image_url": "https://example.invalid/figure.png",
                        }
                    ]
                }
            ],
        }
    }

    def fake_get_bytes(url: str, *, timeout_seconds: float, max_bytes: int) -> bytes:
        assert url.endswith("figure.png")
        assert max_bytes > 0
        return PNG_1X1

    monkeypatch.setattr(
        "context_engine.adapters.parser_runtime._httpx_get_bytes",
        fake_get_bytes,
    )
    materialized = materialize_reducto_remote_assets(payload, timeout_seconds=5.0)
    block = materialized["result"]["chunks"][0]["blocks"][0]
    assert block["image_bytes"] == PNG_1X1
    assert block["mime_type"] == "image/png"
    assert "image_url" not in block
    prepared = normalize_reducto_parse_response("src-asset", PARSER_REDUCTO, materialized)
    validate_prepared_source(prepared)
    assert prepared.images[0].bytes_data == PNG_1X1
    scanned = dump_prepared_source_for_privacy_scan(prepared)
    assert "example.invalid" not in scanned


def test_reducto_oversized_asset_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "result": {
            "type": "full",
            "chunks": [{"blocks": [{"type": "Figure", "content": "X", "image_url": "https://example.invalid/big.png"}]}],
        }
    }

    def too_big(url: str, *, timeout_seconds: float, max_bytes: int) -> bytes:
        raise ParserAdapterError("parser_malformed_response", "Parser response could not be normalized.", 502)

    monkeypatch.setattr(
        "context_engine.adapters.parser_runtime._httpx_get_bytes",
        too_big,
    )
    with pytest.raises(ParserAdapterError) as exc_info:
        materialize_reducto_remote_assets(payload, timeout_seconds=5.0)
    assert exc_info.value.code == "parser_malformed_response"


def test_docling_killable_timeout_terminates_hung_child(monkeypatch: pytest.MonkeyPatch) -> None:
    # Spawn re-imports the worker target; mock Process so the parent timeout/
    # terminate path is proven without a real hung child.
    class _HungProc:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
            self._alive = True
            self.exitcode = None

        def start(self) -> None:
            return None

        def join(self, timeout: float | None = None) -> None:
            del timeout
            return None

        def is_alive(self) -> bool:
            return self._alive

        def terminate(self) -> None:
            self._alive = False

        def kill(self) -> None:
            self._alive = False

    class _Ctx:
        def Process(self, *args, **kwargs):  # noqa: N802 - mirrors multiprocessing API
            del args, kwargs
            return _HungProc()

    monkeypatch.setattr(
        "context_engine.adapters.parser_runtime.mp.get_context",
        lambda *_args, **_kwargs: _Ctx(),
    )
    with pytest.raises(ParserAdapterError) as exc_info:
        run_docling_convert_killable(b"%PDF-1.4", "application/pdf", "a.pdf", timeout_seconds=0.2)
    assert exc_info.value.code == "parser_timeout"


def test_docling_default_parser_uses_killable_path(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, float] = {}

    def fake_killable(original_bytes, content_type, filename, *, timeout_seconds: float):
        called["timeout"] = timeout_seconds
        assert original_bytes.startswith(b"%PDF")
        return json.loads((FIXTURES / "docling_export_dict.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "context_engine.adapters.parser_runtime.run_docling_convert_killable",
        fake_killable,
    )
    prepared = DoclingDocumentParser(timeout_seconds=33.0).parse(
        ParserRequest(
            source_document_id="src-killable",
            parser_kind=PARSER_DOCLING,
            original_bytes=b"%PDF-1.4",
            content_type="application/pdf",
            filename="a.pdf",
        )
    )
    assert called["timeout"] == 33.0
    assert prepared.blocks
