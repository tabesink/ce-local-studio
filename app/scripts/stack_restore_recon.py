#!/usr/bin/env python3
"""P12-04 isolated restore + ETag/sha256 recon for S3 key-centric byte archives.

Restores census object bytes via PutObject, then hard-fails on missing object,
contentSha256 mismatch, or capture-time ETag mismatch. Optional Fernet decrypt
proof uses a companion key path/env (never read from inside the archive).

Refuse restore onto live project resolved volume names when --refuse-live-project.
Orphan store keys warn only. Metadata-only export JSON is not a restore archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from scripts.stack_object_store_recon import find_orphan_keys, manifest_object_tree_digest


def load_consistency_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest must be an object")
    objects = raw.get("objects")
    if not isinstance(objects, list):
        raise ValueError("manifest.objects must be a list")
    return raw


def assert_byte_archive(archive_dir: Path) -> list[str]:
    """Hard-fail reasons when archive is metadata-only (export JSON without bytes)."""
    failures: list[str] = []
    objects_dir = archive_dir / "objects"
    manifest_path = archive_dir / "consistency-manifest.json"
    export_only = list(archive_dir.glob("*.object-store-export.json"))
    if not objects_dir.is_dir():
        failures.append("missing_objects_dir")
    else:
        bins = [p for p in objects_dir.iterdir() if p.is_file()]
        if not bins:
            failures.append("empty_objects_dir")
    if not manifest_path.is_file() and export_only:
        failures.append("metadata_only_export")
    if not manifest_path.is_file() and "missing_objects_dir" not in failures and "empty_objects_dir" in failures:
        failures.append("metadata_only_export")
    if not manifest_path.is_file() and not failures:
        failures.append("missing_manifest")
    return failures


def refuse_live_project_volumes(
    target_resolved_volumes: Iterable[str],
    live_resolved_volumes: Iterable[str],
    *,
    refuse_live_project: bool,
) -> list[str]:
    """Refuse overlapping resolved volume names with the live Compose project."""
    if not refuse_live_project:
        return []
    target = {str(v).strip() for v in target_resolved_volumes if str(v).strip()}
    live = {str(v).strip() for v in live_resolved_volumes if str(v).strip()}
    overlap = sorted(target & live)
    return [f"live_volume_overlap:{name}" for name in overlap]


def normalize_etag(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip('"')
    return text or None


def verify_restored_objects(
    manifest_objects: Sequence[dict[str, Any]],
    *,
    fetch: Callable[[str], bytes],
    head: Callable[[str], dict[str, Any]] | None = None,
    require_etag: bool = True,
) -> list[str]:
    """Hard-fail on missing/hash/size/ETag mismatch vs capture manifest."""
    failures: list[str] = []
    for entry in manifest_objects:
        key = str(entry.get("key") or "").strip()
        expected_sha = str(entry.get("contentSha256") or "").strip().lower()
        expected_etag = normalize_etag(entry.get("etag"))
        expected_size = entry.get("sizeBytes")
        if not key or not expected_sha:
            failures.append("invalid_manifest_entry")
            continue
        try:
            data = fetch(key)
        except Exception:
            failures.append(f"missing:{key}")
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha:
            failures.append(f"hash_mismatch:{key}")
        if expected_size is not None and len(data) != int(expected_size):
            failures.append(f"size_mismatch:{key}")
        if require_etag:
            if expected_etag is None:
                failures.append(f"etag_missing_in_manifest:{key}")
            elif head is None:
                failures.append(f"etag_head_unavailable:{key}")
            else:
                meta = head(key) or {}
                actual_etag = normalize_etag(meta.get("etag"))
                if actual_etag is None:
                    failures.append(f"etag_missing:{key}")
                elif actual_etag != expected_etag:
                    failures.append(f"etag_mismatch:{key}")
    return failures


def restore_objects_from_archive(
    manifest_objects: Sequence[dict[str, Any]],
    *,
    archive_objects_dir: Path,
    put: Callable[[str, bytes], Any],
) -> list[str]:
    """PutObject each archived byte file under its census key. Return failures."""
    failures: list[str] = []
    for entry in manifest_objects:
        key = str(entry.get("key") or "").strip()
        archive_file = str(entry.get("archiveFile") or "").strip()
        if not key or not archive_file:
            failures.append("invalid_manifest_entry")
            continue
        path = archive_objects_dir / archive_file
        if not path.is_file():
            failures.append(f"archive_missing:{key}")
            continue
        data = path.read_bytes()
        expected_sha = str(entry.get("contentSha256") or "").strip().lower()
        if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
            failures.append(f"archive_hash_mismatch:{key}")
            continue
        try:
            put(key, data)
        except Exception:
            failures.append(f"put_failed:{key}")
    return failures


def prove_encryption_key_recoverable(
    *,
    ciphertext: str,
    key_material: str,
    expected_plaintext: str | None = None,
) -> list[str]:
    """Fernet decrypt-proof using companion key material. Empty list = pass."""
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:
        return ["fernet_unavailable"]
    key = (key_material or "").strip()
    if not key:
        return ["encryption_key_missing"]
    try:
        fernet = Fernet(key.encode("utf-8"))
    except Exception:
        return ["encryption_key_invalid"]
    try:
        plaintext = fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ["decrypt_failed"]
    except Exception:
        return ["decrypt_failed"]
    if expected_plaintext is not None and plaintext != expected_plaintext:
        return ["decrypt_plaintext_mismatch"]
    return []


def shred_file(path: Path) -> None:
    """Best-effort overwrite + unlink for companion key material."""
    if not path.is_file():
        return
    try:
        size = path.stat().st_size
        with path.open("wb") as handle:
            handle.write(b"\x00" * max(size, 1))
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        pass
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def verify_object_tree_digest(manifest: dict[str, Any]) -> list[str]:
    expected = str(manifest.get("objectTreeDigest") or "").strip().lower()
    if not expected:
        return ["object_tree_digest_missing"]
    actual = manifest_object_tree_digest(list(manifest.get("objects") or []))
    if actual != expected:
        return ["object_tree_digest_mismatch"]
    return []


def _closed_fail(message: str = "Restore recon failed.") -> int:
    print(message, file=sys.stderr)
    return 2


def _put_via_product_store(key: str, data: bytes) -> None:
    from context_engine.config import Settings
    from context_engine.adapters.object_storage import object_store_from_settings

    store = object_store_from_settings(Settings())
    put_key = getattr(store, "put_key", None)
    if callable(put_key):
        put_key(key, data)
        return
    # Filesystem adapter may only expose put(); restore drill requires S3 put_key.
    raise RuntimeError("put_key_unavailable")


def _fetch_via_product_store(key: str) -> bytes:
    from scripts.stack_object_store_recon import _fetch_via_product_store as fetch

    return fetch(key)


def _head_meta(key: str) -> dict[str, Any]:
    from scripts.stack_object_store_recon import _head_meta as head

    return head(key)


def _list_keys_via_recon_client() -> list[str]:
    from scripts.stack_object_store_recon import _list_keys_via_recon_client as list_keys

    return list_keys()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore object byte archive + ETag/sha256 recon (P12-04 / operator-only)"
    )
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument(
        "--skip-put",
        action="store_true",
        help="Verify only against an already-restored store (unit/offline)",
    )
    parser.add_argument(
        "--refuse-live-project",
        action="store_true",
        help="Fail if --target-volumes overlaps --live-volumes",
    )
    parser.add_argument(
        "--target-volumes",
        default="",
        help="Comma-separated resolved target volume names",
    )
    parser.add_argument(
        "--live-volumes",
        default="",
        help="Comma-separated resolved live project volume names",
    )
    parser.add_argument(
        "--decrypt-proof-ciphertext",
        default="",
        help="Optional Fernet ciphertext to prove companion key recoverability",
    )
    parser.add_argument(
        "--decrypt-proof-plaintext",
        default="",
        help="Optional expected plaintext for decrypt proof",
    )
    parser.add_argument(
        "--companion-key",
        type=Path,
        help="Path to raw CONFIG_ENCRYPTION_KEY companion file (shredded after use)",
    )
    parser.add_argument(
        "--encryption-key",
        default="",
        help="Override key material; defaults to companion file or CONFIG_ENCRYPTION_KEY",
    )
    parser.add_argument(
        "--shred-companion",
        action="store_true",
        help="Overwrite+unlink companion key path after decrypt proof (success or fail)",
    )
    parser.add_argument(
        "--orphan-warn",
        action="store_true",
        help="Warn on store keys not in the manifest set (requires List creds)",
    )
    parser.add_argument(
        "--require-etag",
        action="store_true",
        default=True,
        help="Hard-fail on ETag mismatch (default: true)",
    )
    parser.add_argument(
        "--no-require-etag",
        action="store_false",
        dest="require_etag",
        help="Disable ETag hard-fail (not AE3)",
    )
    args = parser.parse_args(argv)

    archive_dir: Path = args.archive_dir
    archive_failures = assert_byte_archive(archive_dir)
    if archive_failures:
        for reason in archive_failures:
            print(reason, file=sys.stderr)
        return 1

    volume_failures = refuse_live_project_volumes(
        [part.strip() for part in str(args.target_volumes).split(",") if part.strip()],
        [part.strip() for part in str(args.live_volumes).split(",") if part.strip()],
        refuse_live_project=bool(args.refuse_live_project),
    )
    if volume_failures:
        for reason in volume_failures:
            print(reason, file=sys.stderr)
        return 1

    try:
        manifest = load_consistency_manifest(archive_dir / "consistency-manifest.json")
    except Exception:
        return _closed_fail()

    digest_failures = verify_object_tree_digest(manifest)
    if digest_failures:
        for reason in digest_failures:
            print(reason, file=sys.stderr)
        return 1

    objects = list(manifest.get("objects") or [])
    if not args.skip_put:
        put_failures = restore_objects_from_archive(
            objects,
            archive_objects_dir=archive_dir / "objects",
            put=_put_via_product_store,
        )
        if put_failures:
            for reason in put_failures:
                print(reason, file=sys.stderr)
            return 1

    try:
        recon_failures = verify_restored_objects(
            objects,
            fetch=_fetch_via_product_store,
            head=_head_meta,
            require_etag=bool(args.require_etag),
        )
    except Exception:
        return _closed_fail()
    if recon_failures:
        for reason in recon_failures:
            print(reason, file=sys.stderr)
        return 1

    companion_path: Path | None = args.companion_key
    key_material = (args.encryption_key or "").strip()
    if not key_material and companion_path is not None and companion_path.is_file():
        key_material = companion_path.read_text(encoding="utf-8").strip()
    if not key_material:
        key_material = (os.environ.get("CONFIG_ENCRYPTION_KEY") or "").strip()

    decrypt_failures: list[str] = []
    if args.decrypt_proof_ciphertext:
        decrypt_failures = prove_encryption_key_recoverable(
            ciphertext=args.decrypt_proof_ciphertext,
            key_material=key_material,
            expected_plaintext=args.decrypt_proof_plaintext or None,
        )
        if args.shred_companion and companion_path is not None:
            shred_file(companion_path)
        if decrypt_failures:
            for reason in decrypt_failures:
                print(reason, file=sys.stderr)
            return 1
    elif args.shred_companion and companion_path is not None:
        shred_file(companion_path)

    if args.orphan_warn:
        try:
            orphans = find_orphan_keys(
                {str(entry.get("key") or "") for entry in objects},
                _list_keys_via_recon_client(),
            )
        except Exception:
            return _closed_fail()
        if orphans:
            for key in orphans:
                print(f"orphan:{key}", file=sys.stderr)
            print(f"orphan-warn:count={len(orphans)}")
        else:
            print("orphan-warn:ok")

    print(
        f"restore-recon:ok objects={len(objects)} "
        f"objectTreeDigest={manifest.get('objectTreeDigest')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
