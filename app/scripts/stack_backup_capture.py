#!/usr/bin/env python3
"""P12-04 write-fenced consistency capture (S3 key-centric byte archive).

Ordered under one fence episode (no api/worker writers):
  1) confirm write-fence (api/worker stopped; fail if writers detectable)
  2) PG→refs census
  3) GetObject each census key into a portable archive directory
  4) pg_dump path hook (provided dump or subprocess command)
  5) consistency manifest (PG digest, objectTreeDigest, ETags, key fingerprint)

Never writes raw CONFIG_ENCRYPTION_KEY into the archive. Companion key material
is written only to an explicit separate path when requested.

Filesystem-only store kind is refused when --require-s3 (AE2 green gate).
Metadata-only recon export is not a byte archive — this script GetObject bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from scripts.stack_object_store_recon import (
    ReferencedObject,
    load_referenced_objects,
    manifest_object_tree_digest,
)
from scripts.stack_pg_object_refs_census import write_census_json


BACKUP_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_WRITER_SERVICES = frozenset({"api", "worker"})
# One-shot putters that must not be mid-flight during capture.
DEFAULT_EXTRA_WRITER_SERVICES = frozenset({"bootstrap"})


def fingerprint_encryption_key(key_material: str) -> str:
    """SHA-256 fingerprint of CONFIG_ENCRYPTION_KEY (never store the raw key)."""
    raw = (key_material or "").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def archive_filename_for_key(object_key: str) -> str:
    """Stable key-safe archive filename (opaque keys may still be awkward on disk)."""
    digest = hashlib.sha256(object_key.encode("utf-8")).hexdigest()
    return f"{digest}.bin"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_ae_store_kind(store_kind: str, *, require_s3: bool) -> list[str]:
    """Refuse filesystem-only as AE green when require_s3 is set."""
    kind = str(store_kind or "").strip().lower()
    if not require_s3:
        return []
    if kind not in {"s3", "minio"}:
        return [f"store_kind_refused:{kind or 'missing'}"]
    return []


def assert_write_fence(
    running_services: Iterable[str],
    *,
    writer_services: frozenset[str] = DEFAULT_WRITER_SERVICES,
    extra_writer_services: frozenset[str] = DEFAULT_EXTRA_WRITER_SERVICES,
) -> list[str]:
    """Return hard-fail reasons if put/publish-capable services remain up."""
    running = {str(name).strip() for name in running_services if str(name).strip()}
    blocked = writer_services | extra_writer_services
    still_up = sorted(running & blocked)
    return [f"writer_running:{name}" for name in still_up]


def parse_compose_ps_names(payload: str) -> set[str]:
    """Parse `docker compose ps --format json` (one object per line or JSON array)."""
    text = (payload or "").strip()
    if not text:
        return set()
    names: set[str] = set()
    if text.startswith("["):
        rows = json.loads(text)
        if not isinstance(rows, list):
            raise ValueError("compose ps JSON must be a list")
        for row in rows:
            if isinstance(row, dict):
                svc = row.get("Service") or row.get("service") or row.get("Name")
                state = str(row.get("State") or row.get("state") or "").lower()
                if svc and state and state not in {"exited", "dead", "removed"}:
                    names.add(str(svc))
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        svc = row.get("Service") or row.get("service") or row.get("Name")
        state = str(row.get("State") or row.get("state") or "").lower()
        if svc and state and state not in {"exited", "dead", "removed"}:
            names.add(str(svc))
    return names


def build_consistency_manifest(
    *,
    store_kind: str,
    object_entries: list[dict[str, Any]],
    encryption_key_fingerprint: str,
    pg_digest: str | None = None,
    alembic_head: str | None = None,
    image_digests: dict[str, str] | None = None,
) -> dict[str, Any]:
    entries = sorted(object_entries, key=lambda row: str(row.get("key") or ""))
    manifest: dict[str, Any] = {
        "schemaVersion": BACKUP_MANIFEST_SCHEMA_VERSION,
        "storeKind": str(store_kind).strip().lower(),
        "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "objectCount": len(entries),
        "objectTreeDigest": manifest_object_tree_digest(entries),
        "encryptionKeyFingerprint": encryption_key_fingerprint,
        "objects": entries,
    }
    if pg_digest:
        manifest["pgDigest"] = pg_digest
    if alembic_head:
        manifest["alembicHead"] = alembic_head
    if image_digests:
        manifest["imageDigests"] = dict(sorted(image_digests.items()))
    return manifest


def capture_object_bytes(
    refs: Sequence[ReferencedObject],
    *,
    archive_objects_dir: Path,
    fetch: Callable[[str], bytes],
    head: Callable[[str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """GetObject each ref into archive_objects_dir; return manifest object entries."""
    archive_objects_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for ref in refs:
        data = fetch(ref.key)
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref.sha256:
            raise ValueError(f"hash_mismatch:{ref.key}")
        if ref.size_bytes is not None and len(data) != ref.size_bytes:
            raise ValueError(f"size_mismatch:{ref.key}")
        filename = archive_filename_for_key(ref.key)
        (archive_objects_dir / filename).write_bytes(data)
        meta = head(ref.key) if head is not None else {}
        etag = meta.get("etag")
        if isinstance(etag, str):
            etag = etag.strip().strip('"') or None
        entries.append(
            {
                "key": ref.key,
                "contentSha256": digest,
                "sizeBytes": len(data),
                "etag": etag,
                "versionId": meta.get("versionId"),
                "archiveFile": filename,
            }
        )
    entries.sort(key=lambda row: row["key"])
    return entries


def run_pg_dump_hook(
    *,
    dump_output: Path,
    pg_dump_command: str | None,
    existing_dump: Path | None,
) -> str:
    """Return sha256 of the dump file. Prefer an existing dump; else run command."""
    if existing_dump is not None:
        if not existing_dump.is_file():
            raise FileNotFoundError("pg dump missing")
        if existing_dump.resolve() != dump_output.resolve():
            dump_output.parent.mkdir(parents=True, exist_ok=True)
            dump_output.write_bytes(existing_dump.read_bytes())
        return file_sha256(dump_output)
    if not pg_dump_command:
        raise ValueError("pg dump path or command required")
    dump_output.parent.mkdir(parents=True, exist_ok=True)
    # Documented subprocess hook — operator supplies the full pg_dump invocation.
    # Output must land at dump_output (redirect or -f).
    env = os.environ.copy()
    completed = subprocess.run(
        shlex.split(pg_dump_command),
        check=False,
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError("pg_dump_failed")
    if not dump_output.is_file():
        # Some operators pipe stdout; accept stdout bytes when file absent.
        if completed.stdout:
            dump_output.write_bytes(completed.stdout)
        else:
            raise RuntimeError("pg_dump_missing_output")
    return file_sha256(dump_output)


def write_companion_key_files(
    *,
    companion_key_path: Path | None,
    key_material: str,
    fingerprint_sidecar: Path | None,
) -> str:
    """Write raw key only to companion_key_path; fingerprint may be sidecared.

    Returns the fingerprint string (also belongs in the consistency manifest).
    """
    fingerprint = fingerprint_encryption_key(key_material)
    if companion_key_path is not None:
        companion_key_path.parent.mkdir(parents=True, exist_ok=True)
        companion_key_path.write_text(key_material.strip() + "\n", encoding="utf-8")
    if fingerprint_sidecar is not None:
        fingerprint_sidecar.parent.mkdir(parents=True, exist_ok=True)
        fingerprint_sidecar.write_text(fingerprint + "\n", encoding="utf-8")
    return fingerprint


def _closed_fail(message: str = "Backup capture failed.") -> int:
    print(message, file=sys.stderr)
    return 2


def _docker_compose_stop_writers(
    *,
    compose_files: Sequence[str],
    project: str | None,
    env_file: str | None,
) -> None:
    """Documented fence: docker compose stop api worker (subprocess)."""
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    if project:
        cmd.extend(["-p", project])
    for compose_file in compose_files:
        cmd.extend(["-f", compose_file])
    cmd.extend(["stop", "api", "worker"])
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("compose_stop_failed")


def _docker_compose_ps_running(
    *,
    compose_files: Sequence[str],
    project: str | None,
    env_file: str | None,
) -> set[str]:
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    if project:
        cmd.extend(["-p", project])
    for compose_file in compose_files:
        cmd.extend(["-f", compose_file])
    cmd.extend(["ps", "--format", "json"])
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("compose_ps_failed")
    return parse_compose_ps_names(completed.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write-fenced PG+object byte archive capture (P12-04 / operator-only)"
    )
    parser.add_argument("--archive-dir", type=Path, required=True, help="Portable archive directory")
    parser.add_argument("--refs", type=Path, help="Prebuilt refs JSON (skips DB census)")
    parser.add_argument("--census-from-json", type=Path, help="Offline census fixture for --from-json")
    parser.add_argument(
        "--store-kind",
        default=os.environ.get("CE_OBJECT_STORE_KIND", "filesystem"),
        help="filesystem|s3|minio recorded in manifest",
    )
    parser.add_argument(
        "--require-s3",
        action="store_true",
        help="Refuse filesystem-only store kind (AE2 green gate)",
    )
    parser.add_argument(
        "--skip-fence",
        action="store_true",
        help="Skip docker compose stop/ps (unit/offline only; not AE2)",
    )
    parser.add_argument("--compose-file", action="append", default=[], help="Compose file (-f); repeatable")
    parser.add_argument("--compose-project", default="", help="Compose project name (-p)")
    parser.add_argument("--compose-env-file", default="", help="Compose --env-file")
    parser.add_argument("--pg-dump", type=Path, help="Existing pg_dump file to copy into archive")
    parser.add_argument(
        "--pg-dump-command",
        default="",
        help="Optional subprocess pg_dump command; stdout or --archive-dir/pg.dump",
    )
    parser.add_argument("--alembic-head", default="", help="Optional alembic head recorded in manifest")
    parser.add_argument(
        "--companion-key-out",
        type=Path,
        help="Separate gitignored path for raw CONFIG_ENCRYPTION_KEY (never inside archive)",
    )
    parser.add_argument(
        "--encryption-key",
        default="",
        help="Override; defaults to CONFIG_ENCRYPTION_KEY env (never printed)",
    )
    args = parser.parse_args(argv)

    store_kind = str(args.store_kind).strip().lower()
    refused = assert_ae_store_kind(store_kind, require_s3=bool(args.require_s3))
    if refused:
        for reason in refused:
            print(reason, file=sys.stderr)
        return _closed_fail()

    archive_dir: Path = args.archive_dir
    objects_dir = archive_dir / "objects"
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return _closed_fail()

    key_material = (args.encryption_key or os.environ.get("CONFIG_ENCRYPTION_KEY") or "").strip()
    if not key_material:
        return _closed_fail()

    # Companion key MUST NOT land under archive_dir.
    if args.companion_key_out is not None:
        try:
            if args.companion_key_out.resolve().is_relative_to(archive_dir.resolve()):
                print("companion_key_inside_archive", file=sys.stderr)
                return _closed_fail()
        except Exception:
            return _closed_fail()

    compose_files = list(args.compose_file) or [
        "compose.stack.yml",
        "compose.stack.minio.yml",
        "compose.stack.live.yml",
    ]

    if not args.skip_fence:
        try:
            _docker_compose_stop_writers(
                compose_files=compose_files,
                project=args.compose_project or None,
                env_file=args.compose_env_file or None,
            )
            running = _docker_compose_ps_running(
                compose_files=compose_files,
                project=args.compose_project or None,
                env_file=args.compose_env_file or None,
            )
        except Exception:
            return _closed_fail()
        fence_failures = assert_write_fence(running)
        if fence_failures:
            for reason in fence_failures:
                print(reason, file=sys.stderr)
            return 1

    # Census → refs.json
    refs_path = archive_dir / "refs.json"
    try:
        if args.refs is not None:
            refs = load_referenced_objects(args.refs)
            write_census_json(
                [
                    {
                        "key": ref.key,
                        "sha256": ref.sha256,
                        **({"sizeBytes": ref.size_bytes} if ref.size_bytes is not None else {}),
                    }
                    for ref in refs
                ],
                refs_path,
            )
        elif args.census_from_json is not None:
            from scripts.stack_pg_object_refs_census import census_from_row_mappings

            raw = json.loads(args.census_from_json.read_text(encoding="utf-8"))
            census = census_from_row_mappings(
                list(raw.get("documents") or []),
                list(raw.get("images") or []),
            )
            write_census_json(census, refs_path)
            refs = load_referenced_objects(refs_path)
        else:
            from scripts.stack_pg_object_refs_census import census_from_session
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            url = (os.environ.get("CONTEXT_ENGINE_DATABASE_URL") or "").strip()
            if not url:
                return _closed_fail()
            engine = create_engine(url)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                census = census_from_session(session)
            write_census_json(census, refs_path)
            refs = load_referenced_objects(refs_path)
    except Exception:
        return _closed_fail()

    # GetObject bytes
    try:
        from scripts.stack_object_store_recon import _fetch_via_product_store, _head_meta

        entries = capture_object_bytes(
            refs,
            archive_objects_dir=objects_dir,
            fetch=_fetch_via_product_store,
            head=_head_meta,
        )
    except Exception:
        return _closed_fail()

    # pg_dump hook (optional for offline unit paths — AE2 requires a dump)
    pg_digest: str | None = None
    dump_path = archive_dir / "pg.dump"
    if args.pg_dump is not None or args.pg_dump_command:
        try:
            pg_digest = run_pg_dump_hook(
                dump_output=dump_path,
                pg_dump_command=args.pg_dump_command or None,
                existing_dump=args.pg_dump,
            )
        except Exception:
            return _closed_fail()

    try:
        fingerprint = write_companion_key_files(
            companion_key_path=args.companion_key_out,
            key_material=key_material,
            fingerprint_sidecar=None,  # fingerprint lives in manifest only
        )
        # Ensure raw key never appears under archive_dir
        for path in archive_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.name in {"refs.json", "consistency-manifest.json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if key_material and key_material in text:
                    print("secret_in_archive", file=sys.stderr)
                    return _closed_fail()

        manifest = build_consistency_manifest(
            store_kind=store_kind,
            object_entries=entries,
            encryption_key_fingerprint=fingerprint,
            pg_digest=pg_digest,
            alembic_head=args.alembic_head or None,
        )
        manifest_path = archive_dir / "consistency-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        return _closed_fail()

    print(
        f"capture:ok objects={manifest['objectCount']} "
        f"objectTreeDigest={manifest['objectTreeDigest']}"
        + (f" pgDigest={pg_digest}" if pg_digest else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
