#!/usr/bin/env python3
"""P12-04 PG→refs census for governed object-store backup/restore recon.

Emits a JSON array compatible with stack_object_store_recon.py --refs:
  [{ "key", "sha256", "sizeBytes"? }, ...]

Covers source_documents (original + preview + page-map) and source_images.
When preview_reuses_original is true, the preview object key is omitted (deduped
onto the original). Duplicate keys across rows keep the first entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class DocumentObjectRefs:
    original_object_key: str
    original_sha256: str
    original_size_bytes: int | None = None
    preview_object_key: str | None = None
    preview_sha256: str | None = None
    preview_size_bytes: int | None = None
    preview_page_map_object_key: str | None = None
    preview_page_map_sha256: str | None = None
    preview_reuses_original: bool = False


@dataclass(frozen=True)
class ImageObjectRef:
    object_key: str
    content_hash: str


def _normalize_sha(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_key(value: str) -> str:
    return str(value or "").strip()


def add_ref(
    by_key: dict[str, dict[str, Any]],
    *,
    key: str | None,
    sha256: str | None,
    size_bytes: int | None = None,
) -> None:
    """Insert a ref keyed by object key; first write wins (dedupe)."""
    safe_key = _normalize_key(key or "")
    safe_sha = _normalize_sha(sha256 or "")
    if not safe_key or not safe_sha:
        return
    if safe_key in by_key:
        return
    entry: dict[str, Any] = {"key": safe_key, "sha256": safe_sha}
    if size_bytes is not None:
        entry["sizeBytes"] = int(size_bytes)
    by_key[safe_key] = entry


def build_census_refs(
    documents: Iterable[DocumentObjectRefs],
    images: Iterable[ImageObjectRef] = (),
) -> list[dict[str, Any]]:
    """Build sorted, deduped refs for recon/export/byte-archive capture."""
    by_key: dict[str, dict[str, Any]] = {}
    for doc in documents:
        add_ref(
            by_key,
            key=doc.original_object_key,
            sha256=doc.original_sha256,
            size_bytes=doc.original_size_bytes,
        )
        if doc.preview_object_key and doc.preview_sha256 and not doc.preview_reuses_original:
            add_ref(
                by_key,
                key=doc.preview_object_key,
                sha256=doc.preview_sha256,
                size_bytes=doc.preview_size_bytes,
            )
        if doc.preview_page_map_object_key and doc.preview_page_map_sha256:
            add_ref(
                by_key,
                key=doc.preview_page_map_object_key,
                sha256=doc.preview_page_map_sha256,
            )
    for image in images:
        add_ref(by_key, key=image.object_key, sha256=image.content_hash)
    return sorted(by_key.values(), key=lambda row: str(row["key"]))


def document_refs_from_mapping(row: dict[str, Any]) -> DocumentObjectRefs:
    return DocumentObjectRefs(
        original_object_key=str(row.get("original_object_key") or ""),
        original_sha256=str(row.get("original_sha256") or ""),
        original_size_bytes=(
            int(row["original_size_bytes"]) if row.get("original_size_bytes") is not None else None
        ),
        preview_object_key=row.get("preview_object_key"),
        preview_sha256=row.get("preview_sha256"),
        preview_size_bytes=(
            int(row["preview_size_bytes"]) if row.get("preview_size_bytes") is not None else None
        ),
        preview_page_map_object_key=row.get("preview_page_map_object_key"),
        preview_page_map_sha256=row.get("preview_page_map_sha256"),
        preview_reuses_original=bool(row.get("preview_reuses_original") or False),
    )


def image_ref_from_mapping(row: dict[str, Any]) -> ImageObjectRef:
    return ImageObjectRef(
        object_key=str(row.get("object_key") or ""),
        content_hash=str(row.get("content_hash") or ""),
    )


def census_from_row_mappings(
    documents: Sequence[dict[str, Any]],
    images: Sequence[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    return build_census_refs(
        [document_refs_from_mapping(row) for row in documents],
        [image_ref_from_mapping(row) for row in images],
    )


def census_from_session(session: Any) -> list[dict[str, Any]]:
    """Query source_documents / source_images via a SQLAlchemy Session."""
    from context_engine.models import SourceDocument, SourceImage

    documents = [
        DocumentObjectRefs(
            original_object_key=doc.original_object_key,
            original_sha256=doc.original_sha256,
            original_size_bytes=doc.original_size_bytes,
            preview_object_key=doc.preview_object_key,
            preview_sha256=doc.preview_sha256,
            preview_size_bytes=doc.preview_size_bytes,
            preview_page_map_object_key=doc.preview_page_map_object_key,
            preview_page_map_sha256=doc.preview_page_map_sha256,
            preview_reuses_original=bool(doc.preview_reuses_original),
        )
        for doc in session.query(SourceDocument).all()
    ]
    images = [
        ImageObjectRef(object_key=img.object_key, content_hash=img.content_hash)
        for img in session.query(SourceImage).all()
    ]
    return build_census_refs(documents, images)


def write_census_json(refs: Sequence[dict[str, Any]], output: Any) -> None:
    payload = json.dumps(list(refs), indent=2, sort_keys=True) + "\n"
    if hasattr(output, "write"):
        output.write(payload)
    else:
        path = output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit PG→object-store refs census JSON for recon/backup (operator-only)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output path or '-' for stdout (default: stdout)",
    )
    parser.add_argument(
        "--from-json",
        type=str,
        help="Offline fixture: JSON object with documents[] and images[] row mappings",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default="",
        help="Optional SQLAlchemy URL; defaults to CONTEXT_ENGINE_DATABASE_URL",
    )
    args = parser.parse_args(argv)

    try:
        if args.from_json:
            from pathlib import Path

            raw = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("from-json must be an object with documents/images")
            refs = census_from_row_mappings(
                list(raw.get("documents") or []),
                list(raw.get("images") or []),
            )
        else:
            import os

            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            url = (args.database_url or os.environ.get("CONTEXT_ENGINE_DATABASE_URL") or "").strip()
            if not url:
                print("PG object refs census failed.", file=sys.stderr)
                return 2
            engine = create_engine(url)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                refs = census_from_session(session)
    except Exception:
        print("PG object refs census failed.", file=sys.stderr)
        return 2

    try:
        if args.output == "-":
            write_census_json(refs, sys.stdout)
        else:
            from pathlib import Path

            write_census_json(refs, Path(args.output))
            print(f"census:ok count={len(refs)}")
    except Exception:
        print("PG object refs census failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
