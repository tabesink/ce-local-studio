"""P10-06 U5: preview derivative cleanup on source delete (AE6)."""

from __future__ import annotations

from pathlib import Path

from context_engine.services.sources import SourceStorage


def test_delete_source_files_removes_preview_and_page_map_not_reused(tmp_path: Path) -> None:
    storage = SourceStorage(str(tmp_path / "root"))
    original = storage.put_original(b"%PDF-1.4 original", content_type="application/pdf")
    preview = storage.store.put(b"%PDF-1.4 generated", content_type="application/pdf").key
    page_map = storage.store.put(b'{"version":1}', content_type="application/json").key
    assert storage.store.exists(preview)
    assert storage.store.exists(page_map)

    storage.delete_source_files(
        "domain_a",
        "source_a",
        original_object_key=original,
        preview_object_key=preview,
        preview_page_map_object_key=page_map,
        preview_reuses_original=False,
    )
    assert not storage.store.exists(original)
    assert not storage.store.exists(preview)
    assert not storage.store.exists(page_map)


def test_delete_source_files_keeps_single_delete_when_preview_reuses_original(tmp_path: Path) -> None:
    storage = SourceStorage(str(tmp_path / "root"))
    original = storage.put_original(b"%PDF-1.4 original", content_type="application/pdf")
    page_map = storage.store.put(b'{"version":1,"pages":[]}', content_type="application/json").key

    storage.delete_source_files(
        "domain_a",
        "source_b",
        original_object_key=original,
        preview_object_key=original,
        preview_page_map_object_key=page_map,
        preview_reuses_original=True,
    )
    assert not storage.store.exists(original)
    assert not storage.store.exists(page_map)


def test_delete_source_files_is_idempotent_for_missing_preview_keys(tmp_path: Path) -> None:
    storage = SourceStorage(str(tmp_path / "root"))
    storage.delete_source_files(
        "domain_a",
        "source_c",
        original_object_key=None,
        preview_object_key="obj_already_gone_preview",
        preview_page_map_object_key="obj_already_gone_map",
        preview_reuses_original=False,
    )
