from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet

from scripts.stack_backup_capture import (
    archive_filename_for_key,
    assert_ae_store_kind,
    assert_write_fence,
    build_consistency_manifest,
    capture_object_bytes,
    fingerprint_encryption_key,
    parse_compose_ps_names,
    write_companion_key_files,
)
from scripts.stack_object_store_recon import ReferencedObject, manifest_object_tree_digest
from scripts.stack_pg_object_refs_census import (
    DocumentObjectRefs,
    ImageObjectRef,
    build_census_refs,
    census_from_row_mappings,
    main as census_main,
)
from scripts.stack_restore_recon import (
    assert_byte_archive,
    prove_encryption_key_recoverable,
    refuse_live_project_volumes,
    restore_objects_from_archive,
    verify_restored_objects,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_census_dedupes_preview_reuses_original() -> None:
    docs = [
        DocumentObjectRefs(
            original_object_key="obj_original",
            original_sha256=_sha(b"pdf"),
            original_size_bytes=3,
            preview_object_key="obj_original",
            preview_sha256=_sha(b"pdf"),
            preview_reuses_original=True,
            preview_page_map_object_key="obj_page_map",
            preview_page_map_sha256=_sha(b"map"),
        ),
        DocumentObjectRefs(
            original_object_key="obj_other",
            original_sha256=_sha(b"docx"),
            preview_object_key="obj_preview",
            preview_sha256=_sha(b"preview"),
            preview_size_bytes=7,
            preview_reuses_original=False,
        ),
    ]
    images = [ImageObjectRef(object_key="obj_image", content_hash=_sha(b"img"))]
    refs = build_census_refs(docs, images)
    keys = [row["key"] for row in refs]
    assert keys == sorted(keys)
    assert keys.count("obj_original") == 1
    assert "obj_other" in keys
    assert "obj_preview" in keys
    assert "obj_page_map" in keys
    assert "obj_image" in keys
    # preview_reuses_original must not emit a duplicate preview key for the original
    assert len(refs) == 5


def test_census_from_row_mappings_and_cli(tmp_path: Path) -> None:
    fixture = {
        "documents": [
            {
                "original_object_key": "k1",
                "original_sha256": _sha(b"a"),
                "original_size_bytes": 1,
                "preview_object_key": "k1",
                "preview_sha256": _sha(b"a"),
                "preview_reuses_original": True,
            }
        ],
        "images": [{"object_key": "kimg", "content_hash": _sha(b"i")}],
    }
    src = tmp_path / "rows.json"
    out = tmp_path / "refs.json"
    src.write_text(json.dumps(fixture), encoding="utf-8")
    assert census_from_row_mappings(fixture["documents"], fixture["images"])[0]["key"] == "k1"
    assert census_main(["--from-json", str(src), "--output", str(out)]) == 0
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert {row["key"] for row in loaded} == {"k1", "kimg"}


def test_manifest_object_tree_digest_stable() -> None:
    entries = [
        {"key": "b", "contentSha256": _sha(b"b"), "etag": "e2"},
        {"key": "a", "contentSha256": _sha(b"a"), "etag": "e1"},
    ]
    digest = manifest_object_tree_digest(entries)
    manifest = build_consistency_manifest(
        store_kind="s3",
        object_entries=entries,
        encryption_key_fingerprint="abc",
        pg_digest="pgdigest",
        alembic_head="rev1",
    )
    assert manifest["objectTreeDigest"] == digest
    assert manifest["pgDigest"] == "pgdigest"
    assert manifest["alembicHead"] == "rev1"
    assert manifest["encryptionKeyFingerprint"] == "abc"
    assert "CONFIG_ENCRYPTION_KEY" not in json.dumps(manifest)


def test_etag_mismatch_hard_fails() -> None:
    store = {"obj_a": b"alpha"}
    etags = {"obj_a": "etag-capture"}

    def fetch(key: str) -> bytes:
        if key not in store:
            raise KeyError(key)
        return store[key]

    def head(key: str) -> dict[str, object]:
        return {"etag": etags.get(key)}

    objects = [
        {
            "key": "obj_a",
            "contentSha256": _sha(b"alpha"),
            "sizeBytes": 5,
            "etag": "etag-capture",
        }
    ]
    assert verify_restored_objects(objects, fetch=fetch, head=head, require_etag=True) == []

    etags["obj_a"] = "etag-other"
    failures = verify_restored_objects(objects, fetch=fetch, head=head, require_etag=True)
    assert "etag_mismatch:obj_a" in failures

    # sha256/size-only path would miss this — ETag hard-fail is required for AE3
    from scripts.stack_object_store_recon import verify_referenced_objects

    assert (
        verify_referenced_objects(
            [ReferencedObject("obj_a", _sha(b"alpha"), size_bytes=5)],
            fetch=fetch,
        )
        == []
    )


def test_key_fingerprint_not_raw_key(tmp_path: Path) -> None:
    key = Fernet.generate_key().decode("utf-8")
    fingerprint = fingerprint_encryption_key(key)
    assert fingerprint == hashlib.sha256(key.encode("utf-8")).hexdigest()
    assert fingerprint != key

    companion = tmp_path / "companion" / "config.key"
    archive = tmp_path / "drill.backup-archive"
    archive.mkdir()
    fp = write_companion_key_files(
        companion_key_path=companion,
        key_material=key,
        fingerprint_sidecar=None,
    )
    assert fp == fingerprint
    assert companion.read_text(encoding="utf-8").strip() == key
    # Archive must not receive the raw key from this helper
    assert list(archive.iterdir()) == []


def test_refuse_live_project_volumes() -> None:
    assert refuse_live_project_volumes(
        ["proj_live_stack-postgres-data", "proj_live_stack-minio-data"],
        ["proj_live_stack-postgres-data"],
        refuse_live_project=True,
    ) == ["live_volume_overlap:proj_live_stack-postgres-data"]
    assert (
        refuse_live_project_volumes(
            ["proj_drill_stack-postgres-data"],
            ["proj_live_stack-postgres-data"],
            refuse_live_project=True,
        )
        == []
    )
    assert (
        refuse_live_project_volumes(
            ["proj_live_stack-postgres-data"],
            ["proj_live_stack-postgres-data"],
            refuse_live_project=False,
        )
        == []
    )
    assert refuse_live_project_volumes([], [], refuse_live_project=True) == [
        "live_volume_lists_required"
    ]
    assert refuse_live_project_volumes(
        ["proj_drill_stack-minio-data"],
        [],
        refuse_live_project=True,
    ) == ["live_volume_lists_required"]


def test_metadata_only_not_enough(tmp_path: Path) -> None:
    archive = tmp_path / "meta-only"
    archive.mkdir()
    (archive / "export.object-store-export.json").write_text(
        json.dumps({"objectTreeDigest": "x", "objects": []}),
        encoding="utf-8",
    )
    failures = assert_byte_archive(archive)
    assert "missing_objects_dir" in failures or "metadata_only_export" in failures

    objects = archive / "objects"
    objects.mkdir()
    failures_empty = assert_byte_archive(archive)
    assert "empty_objects_dir" in failures_empty


def test_capture_and_restore_roundtrip_with_mocks(tmp_path: Path) -> None:
    store = {"obj_a": b"alpha", "obj_b": b"beta"}
    heads = {"obj_a": {"etag": "e-a", "versionId": None}, "obj_b": {"etag": "e-b", "versionId": None}}

    def fetch(key: str) -> bytes:
        return store[key]

    def head(key: str) -> dict[str, object]:
        return heads[key]

    refs = [
        ReferencedObject("obj_a", _sha(b"alpha"), size_bytes=5),
        ReferencedObject("obj_b", _sha(b"beta"), size_bytes=4),
    ]
    archive = tmp_path / "roundtrip.backup-archive"
    objects_dir = archive / "objects"
    entries = capture_object_bytes(refs, archive_objects_dir=objects_dir, fetch=fetch, head=head)
    assert len(entries) == 2
    assert (objects_dir / archive_filename_for_key("obj_a")).read_bytes() == b"alpha"

    restored: dict[str, bytes] = {}

    def put(key: str, data: bytes) -> None:
        restored[key] = data

    assert restore_objects_from_archive(entries, archive_objects_dir=objects_dir, put=put) == []
    assert restored == store

    # Corrupt ETag after restore → hard-fail
    heads["obj_a"] = {"etag": "wrong", "versionId": None}
    failures = verify_restored_objects(
        entries,
        fetch=lambda key: restored[key],
        head=head,
        require_etag=True,
    )
    assert "etag_mismatch:obj_a" in failures


def test_write_fence_and_require_s3() -> None:
    assert assert_write_fence(["postgres", "minio", "frontend"]) == []
    assert "writer_running:api" in assert_write_fence(["api", "postgres"])
    assert "writer_running:worker" in assert_write_fence(["worker"])
    assert "writer_running:bootstrap" in assert_write_fence(["bootstrap"])

    assert assert_ae_store_kind("s3", require_s3=True) == []
    assert assert_ae_store_kind("minio", require_s3=True) == []
    assert "store_kind_refused:filesystem" in assert_ae_store_kind("filesystem", require_s3=True)
    assert assert_ae_store_kind("filesystem", require_s3=False) == []


def test_parse_compose_ps_and_decrypt_proof() -> None:
    payload = "\n".join(
        [
            json.dumps({"Service": "postgres", "State": "running"}),
            json.dumps({"Service": "api", "State": "exited"}),
            json.dumps({"Service": "worker", "State": "running"}),
        ]
    )
    names = parse_compose_ps_names(payload)
    assert names == {"postgres", "worker"}

    key = Fernet.generate_key().decode("utf-8")
    token = Fernet(key.encode("utf-8")).encrypt(b"drill-secret").decode("utf-8")
    assert prove_encryption_key_recoverable(
        ciphertext=token,
        key_material=key,
        expected_plaintext="drill-secret",
    ) == []
    assert "decrypt_failed" in prove_encryption_key_recoverable(
        ciphertext=token,
        key_material=Fernet.generate_key().decode("utf-8"),
    )
    assert "encryption_key_missing" in prove_encryption_key_recoverable(
        ciphertext=token,
        key_material="",
    )


def test_require_s3_blocks_ae_green_claim() -> None:
    """Filesystem adapter is development-only — not AE2/AE3 green."""
    reasons = assert_ae_store_kind("filesystem", require_s3=True)
    assert reasons
    assert all("filesystem" in reason for reason in reasons)
