from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ObjectStorageError(Exception):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_sha256: str


def new_object_key() -> str:
    return f"obj_{secrets.token_urlsafe(24)}"


class ObjectStorage(Protocol):
    def put(self, data: bytes, *, content_type: str | None = None) -> StoredObject: ...

    def put_key(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject: ...

    def get(self, key: str) -> bytes: ...

    def get_range(self, key: str, start: int, end: int | None = None) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


class FilesystemObjectStore:
    """Development-only filesystem implementation of the governed object-store port."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _safe_path(self, key: str) -> Path:
        if not key or key.strip() != key:
            raise ObjectStorageError("Object key is invalid.")
        if "/" in key or "\\" in key or ".." in key or key in {".", ".."}:
            raise ObjectStorageError("Object key is invalid.")
        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ObjectStorageError("Object key escaped storage root.")
        return candidate

    def put(self, data: bytes, *, content_type: str | None = None) -> StoredObject:
        del content_type
        return self.put_key(new_object_key(), data)

    def put_key(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject:
        del content_type
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            key=key,
            size_bytes=len(data),
            content_sha256=hashlib.sha256(data).hexdigest(),
        )

    def get(self, key: str) -> bytes:
        path = self._safe_path(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ObjectStorageError("Object unavailable.") from exc

    def get_range(self, key: str, start: int, end: int | None = None) -> bytes:
        """Return bytes for an inclusive start/end range (HTTP Range semantics)."""
        if start < 0:
            raise ObjectStorageError("Object range is invalid.")
        data = self.get(key)
        if start >= len(data):
            raise ObjectStorageError("Object range is unsatisfiable.")
        if end is None:
            return data[start:]
        if end < start:
            raise ObjectStorageError("Object range is invalid.")
        return data[start : end + 1]

    def delete(self, key: str) -> None:
        path = self._safe_path(key)
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise ObjectStorageError("Object could not be removed.") from exc

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()


def object_store_from_root(root: str | Path) -> FilesystemObjectStore:
    return FilesystemObjectStore(Path(root) / "objects")
