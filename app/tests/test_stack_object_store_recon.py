from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.stack_object_store_recon import (
    ReferencedObject,
    build_export_manifest,
    export_entries,
    find_orphan_keys,
    load_referenced_objects,
    main,
    manifest_object_tree_digest,
    verify_referenced_objects,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_verify_happy_and_failures() -> None:
    store = {"obj_a": b"alpha", "obj_b": b"beta"}

    def fetch(key: str) -> bytes:
        if key not in store:
            raise KeyError(key)
        return store[key]

    refs = [
        ReferencedObject("obj_a", _sha(b"alpha"), size_bytes=5),
        ReferencedObject("obj_b", _sha(b"beta"), size_bytes=4),
    ]
    assert verify_referenced_objects(refs, fetch=fetch) == []

    assert "missing:obj_missing" in verify_referenced_objects(
        [ReferencedObject("obj_missing", _sha(b"x"))],
        fetch=fetch,
    )
    assert "hash_mismatch:obj_a" in verify_referenced_objects(
        [ReferencedObject("obj_a", _sha(b"wrong"), size_bytes=5)],
        fetch=fetch,
    )
    assert "size_mismatch:obj_a" in verify_referenced_objects(
        [ReferencedObject("obj_a", _sha(b"alpha"), size_bytes=99)],
        fetch=fetch,
    )


def test_export_manifest_digest_stable(tmp_path: Path) -> None:
    store = {"obj_z": b"z", "obj_a": b"a"}

    def fetch(key: str) -> bytes:
        return store[key]

    entries = export_entries(
        [ReferencedObject("obj_z", _sha(b"z")), ReferencedObject("obj_a", _sha(b"a"))],
        fetch=fetch,
    )
    assert [row["key"] for row in entries] == ["obj_a", "obj_z"]
    digest = manifest_object_tree_digest(entries)
    manifest = build_export_manifest(store_kind="s3", entries=entries)
    assert manifest["schemaVersion"] == 1
    assert manifest["storeKind"] == "s3"
    assert manifest["objectCount"] == 2
    assert manifest["objectTreeDigest"] == digest
    assert digest == manifest_object_tree_digest(list(reversed(entries)))


def test_orphan_warn_only() -> None:
    orphans = find_orphan_keys({"obj_a"}, ["obj_a", "obj_orphan"])
    assert orphans == ["obj_orphan"]
    assert find_orphan_keys({"obj_a"}, ["obj_a"]) == []


def test_load_refs_and_cli_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"hello"
    refs_path = tmp_path / "refs.json"
    refs_path.write_text(
        json.dumps([{"key": "obj_hello", "sha256": _sha(data), "sizeBytes": len(data)}]),
        encoding="utf-8",
    )
    loaded = load_referenced_objects(refs_path)
    assert loaded[0].key == "obj_hello"

    monkeypatch.setattr(
        "scripts.stack_object_store_recon._fetch_via_product_store",
        lambda key: data if key == "obj_hello" else (_ for _ in ()).throw(KeyError(key)),
    )
    assert main(["--mode", "verify", "--refs", str(refs_path)]) == 0
    assert main(["--mode", "verify", "--refs", str(refs_path.with_name("missing.json"))]) == 2


def test_cli_export_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"export-me"
    refs_path = tmp_path / "refs.json"
    out_path = tmp_path / "exports" / "manifest.json"
    refs_path.write_text(
        json.dumps([{"key": "obj_export", "sha256": _sha(data)}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.stack_object_store_recon._fetch_via_product_store",
        lambda key: data,
    )
    monkeypatch.setattr("scripts.stack_object_store_recon._head_meta", lambda key: {"etag": "abc", "versionId": None})
    assert main(["--mode", "export", "--refs", str(refs_path), "--output", str(out_path), "--store-kind", "s3"]) == 0
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["objectCount"] == 1
    assert manifest["objects"][0]["key"] == "obj_export"
    assert "objectTreeDigest" in manifest


def test_cli_errors_are_closed(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    code = main(["--mode", "verify", "--refs", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert "Object store recon failed." in captured.err
    assert "CE_S3" not in captured.err
    assert "traceback" not in captured.err.lower()
