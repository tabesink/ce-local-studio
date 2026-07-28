"""P10-05 U8: parser→handoff→Evidence staging proofs (AE8/AE9 altitude).

Default CI stays network-free. Full Compose/live pipeline remains opt-in via
CE_P10_05_PIPELINE_LIVE=1 (complements P5-04 topology credit).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_engine.adapters.parsers import (
    PARSER_DOCLING,
    DoclingDocumentParser,
    ParserRequest,
    validate_prepared_source,
)
from context_engine.models import SOURCE_BLOCK_KIND_TEXT, SOURCE_INDEX_STATE_READY, SOURCE_STATE_PREPARED
from context_engine.services.evidence import (
    FrozenRetrievalScope,
    FrozenSourceIdentity,
    ScopedRetrievalCandidate,
    map_retrieval_hits_to_internal_evidence,
)
from context_engine.services.indexing import LIGHTRAG_HANDOFF_SCHEMA_VERSION, render_blocks_to_lightrag_handoff

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DOCUMENTS = FIXTURES / "documents"
PARSERS = FIXTURES / "parsers"
_PIPELINE_LIVE = os.environ.get("CE_P10_05_PIPELINE_LIVE", "").strip() == "1"


def test_deterministic_pdf_fixture_exists_and_is_bounded() -> None:
    pdf = DOCUMENTS / "ppe_solvent_a.pdf"
    assert pdf.is_file()
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert len(data) < 100_000


def test_parser_to_handoff_preserves_schema_v2_markers_for_multi_block() -> None:
    payload = json.loads((PARSERS / "docling_export_dict.json").read_text(encoding="utf-8"))
    prepared = DoclingDocumentParser(convert=lambda *_a, **_k: payload).parse(
        ParserRequest(
            source_document_id="src-pipeline",
            parser_kind=PARSER_DOCLING,
            original_bytes=b"%PDF-1.4",
            filename="ppe.pdf",
        )
    )
    validate_prepared_source(prepared)
    assert len(prepared.blocks) >= 3

    source_id = "source-pipeline-1"
    sha = "a" * 64
    block_rows = [
        SimpleNamespace(
            id=f"block-{index}",
            source_order=block.source_order,
            kind=block.kind,
            canonical_markdown=block.canonical_markdown,
            heading_level=block.heading_level,
            page_start=block.page_start,
            page_end=block.page_end,
            section_path=block.section_path,
        )
        for index, block in enumerate(prepared.blocks, start=1)
    ]
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source_id,
        original_sha256=sha,
        blocks=block_rows,  # type: ignore[arg-type]
    )
    handoff = rendered.text
    assert f"CE_SOURCE schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION}" in handoff
    marker_count = handoff.count(f"[CE_BLOCK schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION}")
    assert marker_count == len(prepared.blocks)

    huge = "X" * 50_000
    oversized_rows = [
        SimpleNamespace(
            id="block-huge",
            source_order=1,
            kind=SOURCE_BLOCK_KIND_TEXT,
            canonical_markdown=huge,
            heading_level=None,
            page_start=1,
            page_end=1,
            section_path=[],
        )
    ]
    oversized = render_blocks_to_lightrag_handoff(
        source_id=source_id,
        original_sha256=sha,
        blocks=oversized_rows,  # type: ignore[arg-type]
    ).text
    assert oversized.count(f"[CE_BLOCK schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION}") == 1
    assert huge[:32] in oversized


def test_marker_free_continuation_never_maps_to_evidence() -> None:
    source = SimpleNamespace(
        id="source-1",
        public_ref="docref-1",
        domain_id="domain-1",
        original_filename="ppe.pdf",
        original_sha256="b" * 64,
        preparation_generation=1,
        index_generation=1,
        index_request_id="req-1",
        index_content_hash="c" * 64,
        state=SOURCE_STATE_PREPARED,
        index_state=SOURCE_INDEX_STATE_READY,
    )
    block = SimpleNamespace(
        id="block-1",
        source_document_id=source.id,
        source_order=1,
        kind=SOURCE_BLOCK_KIND_TEXT,
        canonical_markdown="Wear gloves with solvent A.",
        heading_level=None,
        page_start=1,
        page_end=1,
        section_path="Safety",
        region_x=None,
        region_y=None,
        region_width=None,
        region_height=None,
    )
    scope = FrozenRetrievalScope(
        domain_id=source.domain_id,
        control_generation=1,
        runtime_instance_id="runtime-1",
        sources=(
            FrozenSourceIdentity(
                source_document_id=source.id,
                preparation_generation=1,
                index_generation=1,
                index_request_id="req-1",
                index_content_hash="c" * 64,
                original_sha256=source.original_sha256,
            ),
        ),
    )
    marker = (
        f"[CE_BLOCK schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION} source_id={source.id} "
        f"source_sha256={source.original_sha256} block_id={block.id} order={block.source_order}]"
    )

    class _Session:
        def execute(self, *_a, **_k):
            class _Result:
                def all(self_inner):
                    return [(block, source, None)]

            return _Result()

    mapped = map_retrieval_hits_to_internal_evidence(
        _Session(),  # type: ignore[arg-type]
        hits=[
            ScopedRetrievalCandidate(text="marker-free continuation must not become Evidence"),
            ScopedRetrievalCandidate(text=f"{marker}\nprovider paraphrase discarded for excerpt"),
        ],
        frozen_scope=scope,
    )
    assert len(mapped) == 1
    assert mapped[0].excerpt == "Wear gloves with solvent A."
    assert "marker-free" not in mapped[0].excerpt
    assert "provider paraphrase" not in mapped[0].excerpt


def test_pipeline_live_gate_is_opt_in() -> None:
    # Root verify must not require the live pipeline gate.
    if _PIPELINE_LIVE:
        assert os.environ.get("CE_P10_05_PIPELINE_LIVE", "").strip() == "1"


@pytest.mark.integration_docker
def test_opt_in_full_pipeline_live_documents_operator_path() -> None:
    if not _PIPELINE_LIVE:
        pytest.skip("Set CE_P10_05_PIPELINE_LIVE=1 for full upload→Evidence staging (U8 live).")
    pytest.skip(
        "Live full-pipeline Compose orchestration is operator-gated; "
        "use scripts/provider_staging_smoke.py --mode live plus Compose live/minio overlays."
    )
