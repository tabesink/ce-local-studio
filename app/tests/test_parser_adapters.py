from __future__ import annotations

import hashlib

import pytest

from context_engine.config import Settings
from context_engine.adapters.parsers import (
    DoclingDocumentParser,
    ParserAdapterError,
    ParserRequest,
    PreparedBlock,
    PreparedImage,
    PreparedSource,
    ReductoDocumentParser,
    dump_prepared_source_for_privacy_scan,
    normalize_docling_document,
    normalize_reducto_parse_response,
    validate_prepared_source,
)
from context_engine.models import PARSER_DOCLING, PARSER_REDUCTO, SOURCE_BLOCK_KIND_FIGURE, SOURCE_BLOCK_KIND_TEXT


def test_normalize_docling_happy_path_ordered_blocks_and_figure_image() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"figure-bytes"
    payload = {
        "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/pictures/0"}]},
        "texts": [{"self_ref": "#/texts/0", "label": "title", "text": "Overview", "prov": {"page": 1}}],
        "pictures": [
            {
                "self_ref": "#/pictures/0",
                "label": "picture",
                "alt_text": "Diagram",
                "image_bytes": png,
                "mime_type": "image/png",
                "prov": {"page": 2},
            }
        ],
    }
    prepared = normalize_docling_document("src-1", PARSER_DOCLING, payload)
    assert [block.kind for block in prepared.blocks] == [SOURCE_BLOCK_KIND_TEXT, SOURCE_BLOCK_KIND_FIGURE]
    assert prepared.blocks[0].canonical_markdown == "# Overview"
    assert prepared.images[0].content_hash == hashlib.sha256(png).hexdigest()
    validate_prepared_source(prepared)


def test_normalize_reducto_malformed_and_url_result_fail_closed() -> None:
    with pytest.raises(ParserAdapterError) as malformed:
        normalize_reducto_parse_response("src-1", PARSER_REDUCTO, {"result": {"chunks": "nope"}})
    assert malformed.value.code == "parser_malformed_response"

    with pytest.raises(ParserAdapterError) as url_result:
        normalize_reducto_parse_response(
            "src-1",
            PARSER_REDUCTO,
            {"result": {"type": "url", "url": "https://example.invalid/presigned"}, "job_id": "job-1"},
        )
    assert url_result.value.code == "parser_malformed_response"


def test_normalize_reducto_happy_path_and_privacy_scan_omits_provider_fields() -> None:
    payload = {
        "job_id": "job-secret",
        "pdf_url": "https://example.invalid/pdf",
        "studio_link": "https://example.invalid/studio",
        "result": {
            "type": "full",
            "chunks": [
                {
                    "blocks": [
                        {"type": "Title", "content": "Policy", "page": 1},
                        {"type": "Text", "content": "Authorized excerpt only.", "page": 1},
                    ]
                }
            ],
        },
    }
    prepared = normalize_reducto_parse_response("src-2", PARSER_REDUCTO, payload)
    assert len(prepared.blocks) == 2
    scanned = dump_prepared_source_for_privacy_scan(prepared)
    assert "job-secret" not in scanned
    assert "example.invalid" not in scanned
    assert "pdf_url" not in scanned
    assert "studio_link" not in scanned


def test_docling_adapter_uses_injected_converter_and_timeout_maps() -> None:
    parser = DoclingDocumentParser(
        convert=lambda _bytes, _ctype, _name: {
            "texts": [{"label": "text", "text": "Injected body"}],
            "body": {"children": [{"$ref": "#/texts/0"}]},
        }
    )
    prepared = parser.parse(
        ParserRequest(
            source_document_id="src-3",
            parser_kind=PARSER_DOCLING,
            original_bytes=b"%PDF-1.4",
            content_type="application/pdf",
            filename="a.pdf",
        )
    )
    assert prepared.blocks[0].canonical_markdown == "Injected body"

    def boom(_bytes, _ctype, _name):
        raise TimeoutError("slow")

    with pytest.raises(ParserAdapterError) as timed_out:
        DoclingDocumentParser(convert=boom).parse(
            ParserRequest(
                source_document_id="src-3",
                parser_kind=PARSER_DOCLING,
                original_bytes=b"%PDF-1.4",
            )
        )
    assert timed_out.value.code == "parser_timeout"


def test_reducto_adapter_requires_credential_and_maps_transport_errors() -> None:
    with pytest.raises(ParserAdapterError) as not_ready:
        ReductoDocumentParser(transport=lambda _req, _timeout: {"result": {"chunks": []}}).parse(
            ParserRequest(
                source_document_id="src-4",
                parser_kind=PARSER_REDUCTO,
                original_bytes=b"%PDF-1.4",
                credential=None,
            )
        )
    assert not_ready.value.code == "parser_not_ready"

    def auth_fail(_req, _timeout):
        raise ParserAdapterError("parser_not_ready", "Parser is not configured.", 409)

    with pytest.raises(ParserAdapterError) as auth:
        ReductoDocumentParser(transport=auth_fail).parse(
            ParserRequest(
                source_document_id="src-4",
                parser_kind=PARSER_REDUCTO,
                original_bytes=b"%PDF-1.4",
                credential="secret",
            )
        )
    assert auth.value.code == "parser_not_ready"

    def ok(_req, _timeout):
        return {"result": {"chunks": [{"content": "Grounded answer source."}]}}

    prepared = ReductoDocumentParser(transport=ok).parse(
        ParserRequest(
            source_document_id="src-4",
            parser_kind=PARSER_REDUCTO,
            original_bytes=b"%PDF-1.4",
            credential="secret",
        )
    )
    assert prepared.blocks[0].canonical_markdown == "Grounded answer source."


def test_settings_require_prep_lease_longer_than_parser_timeout() -> None:
    with pytest.raises(ValueError, match="source_prep_lease_seconds must exceed"):
        Settings(
            testing=True,
            public_origin="http://ce.example.test",
            internal_hosts="testserver",
            trusted_bff_peers="testclient",
            csrf_signing_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
            session_cookie_secure=False,
            source_prep_lease_seconds=60,
            source_parser_timeout_seconds=120,
        )


def test_validate_prepared_source_rejects_hash_mismatch() -> None:
    prepared = PreparedSource(
        source_document_id="src-5",
        parser_kind=PARSER_DOCLING,
        blocks=[PreparedBlock(source_order=1, kind=SOURCE_BLOCK_KIND_FIGURE, canonical_markdown="Figure")],
        images=[
            PreparedImage(
                source_order=1,
                content_hash="0" * 64,
                mime_type="image/png",
                bytes_data=b"not-matching",
            )
        ],
    )
    with pytest.raises(ParserAdapterError) as invalid:
        validate_prepared_source(prepared)
    assert invalid.value.code == "source_preparation_invalid"
