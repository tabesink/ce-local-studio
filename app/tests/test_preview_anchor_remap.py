"""P10-06 U4: Evidence anchor remapping through committed page maps (AE4)."""

from __future__ import annotations

from context_engine.services.evidence import remap_anchor_through_page_map


def test_identity_map_keeps_region() -> None:
    anchor = {
        "pageNumber": 18,
        "region": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
        "sectionLabel": "4.2 Relief valve",
        "fallback": "region",
    }
    page_map = {
        "version": 1,
        "rendererVersion": "ce-preview-pdf-passthrough-v1",
        "pageCount": 24,
        "pages": [{"pageNumber": i, "identity": True} for i in range(1, 25)],
    }
    out = remap_anchor_through_page_map(anchor, page_map=page_map, page_count=24)
    assert out is not None
    assert out["pageNumber"] == 18
    assert out["fallback"] == "region"
    assert out["region"] == anchor["region"]


def test_non_identity_map_degrades_region_to_section() -> None:
    anchor = {
        "pageNumber": 2,
        "region": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
        "sectionLabel": "Checklist",
        "fallback": "region",
    }
    page_map = {
        "version": 1,
        "rendererVersion": "ce-preview-text-v1",
        "pageCount": 3,
        "pages": [
            {"pageNumber": 1, "charStart": 0, "charEnd": 10},
            {"pageNumber": 2, "charStart": 10, "charEnd": 20},
            {"pageNumber": 3, "charStart": 20, "charEnd": 30},
        ],
    }
    out = remap_anchor_through_page_map(anchor, page_map=page_map, page_count=3)
    assert out is not None
    assert out["pageNumber"] == 2
    assert out["region"] is None
    assert out["fallback"] == "section"
    assert out["sectionLabel"] == "Checklist"


def test_out_of_range_page_opens_at_page_one_without_fabricated_region() -> None:
    anchor = {"pageNumber": 99, "region": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}, "fallback": "region"}
    out = remap_anchor_through_page_map(anchor, page_map=None, page_count=3)
    assert out == {"pageNumber": 1, "region": None, "fallback": "page"}
