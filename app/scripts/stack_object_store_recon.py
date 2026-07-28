#!/usr/bin/env python3
"""P10-04 operator recon/export hooks for governed object store (P12-04 consumer).

Modes:
  verify       — hard-fail missing/hash/size mismatch for SQL-derived referenced keys
  export       — write versioned manifest (operator-confidential; do not commit)
  orphan-warn  — warn on store keys not in the referenced set (requires List creds)

PostgreSQL keys+hashes remain inventory authority. This script never exposes an HTTP
route. Export manifests are secret-class — evidence may cite digests/counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReferencedObject:
    key: str
    sha256: str
    size_bytes: int | None = None


def load_referenced_objects(path: Path) -> list[ReferencedObject]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("refs file must be a JSON array")
    out: list[ReferencedObject] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each ref must be an object")
        key = str(item.get("key") or "").strip()
        sha = str(item.get("sha256") or item.get("contentSha256") or "").strip().lower()
        if not key or not sha:
            raise ValueError("each ref requires key and sha256")
        size_raw = item.get("sizeBytes", item.get("size_bytes"))
        size = int(size_raw) if size_raw is not None else None
        out.append(ReferencedObject(key=key, sha256=sha, size_bytes=size))
    return out


def verify_referenced_objects(
    refs: Iterable[ReferencedObject],
    *,
    fetch: Callable[[str], bytes],
) -> list[str]:
    """Return hard-fail reasons (empty list means pass)."""
    failures: list[str] = []
    for ref in refs:
        try:
            data = fetch(ref.key)
        except Exception:
            failures.append(f"missing:{ref.key}")
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref.sha256:
            failures.append(f"hash_mismatch:{ref.key}")
        if ref.size_bytes is not None and len(data) != ref.size_bytes:
            failures.append(f"size_mismatch:{ref.key}")
    return failures


def export_entries(
    refs: Iterable[ReferencedObject],
    *,
    fetch: Callable[[str], bytes],
    head: Callable[[str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for ref in refs:
        data = fetch(ref.key)
        digest = hashlib.sha256(data).hexdigest()
        meta = head(ref.key) if head is not None else {}
        entries.append(
            {
                "key": ref.key,
                "contentSha256": digest,
                "sizeBytes": len(data),
                "etag": meta.get("etag"),
                "versionId": meta.get("versionId"),
            }
        )
    entries.sort(key=lambda row: row["key"])
    return entries


def manifest_object_tree_digest(entries: Iterable[dict[str, Any]]) -> str:
    lines = []
    for entry in sorted(entries, key=lambda row: str(row.get("key") or "")):
        key = str(entry.get("key") or "")
        sha = str(entry.get("contentSha256") or "").lower()
        lines.append(f"{key}:{sha}")
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_export_manifest(
    *,
    store_kind: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "storeKind": store_kind,
        "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "objectCount": len(entries),
        "objectTreeDigest": manifest_object_tree_digest(entries),
        "objects": entries,
    }


def find_orphan_keys(
    referenced_keys: set[str],
    store_keys: Iterable[str],
) -> list[str]:
    orphans = sorted(key for key in store_keys if key not in referenced_keys)
    return orphans


def _closed_error(message: str = "Object store recon failed.") -> SystemExit:
    return SystemExit(message)


def _fetch_via_product_store(key: str) -> bytes:
    # Import inside so unit tests can exercise pure helpers without app boot.
    from context_engine.config import Settings
    from context_engine.adapters.object_storage import object_store_from_settings

    store = object_store_from_settings(Settings())
    return store.get(key)


def _list_keys_via_recon_client() -> list[str]:
    """List bucket keys using operator recon credentials (not runtime app policy)."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("boto3 required for orphan-warn; install object-store extra") from exc

    endpoint = os.environ.get("CE_S3_ENDPOINT", "").strip()
    bucket = os.environ.get("CE_S3_BUCKET", "").strip()
    access = (
        os.environ.get("CE_S3_RECON_ACCESS_KEY") or os.environ.get("CE_S3_ACCESS_KEY") or ""
    ).strip()
    secret = (
        os.environ.get("CE_S3_RECON_SECRET_KEY") or os.environ.get("CE_S3_SECRET_KEY") or ""
    ).strip()
    region = os.environ.get("CE_S3_REGION", "us-east-1").strip() or "us-east-1"
    if not endpoint or not bucket or not access or not secret:
        raise RuntimeError("recon list settings incomplete")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(s3={"addressing_style": "path"}),
    )
    keys: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents") or []:
            key = item.get("Key")
            if isinstance(key, str) and key:
                keys.append(key)
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
    return keys


def _head_meta(key: str) -> dict[str, Any]:
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        return {}
    endpoint = os.environ.get("CE_S3_ENDPOINT", "").strip()
    bucket = os.environ.get("CE_S3_BUCKET", "").strip()
    access = (
        os.environ.get("CE_S3_RECON_ACCESS_KEY") or os.environ.get("CE_S3_ACCESS_KEY") or ""
    ).strip()
    secret = (
        os.environ.get("CE_S3_RECON_SECRET_KEY") or os.environ.get("CE_S3_SECRET_KEY") or ""
    ).strip()
    region = os.environ.get("CE_S3_REGION", "us-east-1").strip() or "us-east-1"
    if not endpoint or not bucket or not access or not secret:
        return {}
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(s3={"addressing_style": "path"}),
    )
    try:
        response = client.head_object(Bucket=bucket, Key=key)
    except Exception:
        return {}
    return {
        "etag": str(response.get("ETag") or "").strip('"') or None,
        "versionId": response.get("VersionId"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governed object-store recon/export (operator-only)")
    parser.add_argument("--mode", choices=("verify", "export", "orphan-warn"), required=True)
    parser.add_argument("--refs", type=Path, required=True, help="JSON array of {key, sha256, sizeBytes?}")
    parser.add_argument("--output", type=Path, help="export manifest path (required for export)")
    parser.add_argument(
        "--store-kind",
        default=os.environ.get("CE_OBJECT_STORE_KIND", "filesystem"),
        help="filesystem|s3 (recorded in export manifest)",
    )
    args = parser.parse_args(argv)

    try:
        refs = load_referenced_objects(args.refs)
    except Exception:
        print("Object store recon failed.", file=sys.stderr)
        return 2

    store_kind = str(args.store_kind).strip().lower()
    if store_kind not in {"filesystem", "s3", "minio"}:
        print("Object store recon failed.", file=sys.stderr)
        return 2

    if args.mode == "verify":
        try:
            failures = verify_referenced_objects(refs, fetch=_fetch_via_product_store)
        except Exception:
            print("Object store recon failed.", file=sys.stderr)
            return 2
        if failures:
            for reason in failures:
                # Reasons cite opaque keys only — never credentials/endpoints.
                print(reason, file=sys.stderr)
            return 1
        print("verify:ok")
        return 0

    if args.mode == "export":
        if args.output is None:
            print("Object store recon failed.", file=sys.stderr)
            return 2
        try:
            entries = export_entries(refs, fetch=_fetch_via_product_store, head=_head_meta)
            manifest = build_export_manifest(store_kind=store_kind, entries=entries)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception:
            print("Object store recon failed.", file=sys.stderr)
            return 2
        print(f"export:ok digest={manifest['objectTreeDigest']} count={manifest['objectCount']}")
        return 0

    # orphan-warn
    if store_kind == "filesystem":
        print("orphan-warn:skipped storeKind=filesystem", file=sys.stderr)
        return 0
    try:
        orphans = find_orphan_keys({ref.key for ref in refs}, _list_keys_via_recon_client())
    except Exception:
        print("Object store recon failed.", file=sys.stderr)
        return 2
    if orphans:
        for key in orphans:
            print(f"orphan:{key}", file=sys.stderr)
        print(f"orphan-warn:count={len(orphans)}")
        return 0  # warn-only
    print("orphan-warn:ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
