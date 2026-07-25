from __future__ import annotations

from pathlib import Path

import pytest

from context_engine.adapters.object_storage import (
    FilesystemObjectStore,
    ObjectStorageError,
    new_object_key,
)


def test_filesystem_object_store_put_get_range_delete(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path / "objects")
    stored = store.put(b"hello-world-bytes", content_type="application/pdf")

    assert stored.key.startswith("obj_")
    assert stored.size_bytes == len(b"hello-world-bytes")
    assert len(stored.content_sha256) == 64
    assert store.get(stored.key) == b"hello-world-bytes"
    assert store.get_range(stored.key, 0, 4) == b"hello"
    assert store.get_range(stored.key, 6, None) == b"world-bytes"
    assert store.exists(stored.key) is True

    store.delete(stored.key)
    assert store.exists(stored.key) is False
    store.delete(stored.key)  # idempotent


def test_filesystem_object_store_rejects_path_escape(tmp_path: Path) -> None:
    store = FilesystemObjectStore(tmp_path / "objects")
    with pytest.raises(ObjectStorageError):
        store.get("../escape")
    with pytest.raises(ObjectStorageError):
        store.put_key("a/../b", b"x")


def test_new_object_key_is_opaque_and_url_safe() -> None:
    key = new_object_key()
    assert key.startswith("obj_")
    assert "/" not in key
    assert "\\" not in key
    assert key == key.strip()
    assert len(key) >= 16
