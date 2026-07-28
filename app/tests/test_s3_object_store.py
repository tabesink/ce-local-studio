from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from context_engine.adapters.object_storage import (
    ObjectStorageError,
    object_store_from_settings,
)
from context_engine.adapters.s3_object_store import S3ObjectStore
from context_engine.config import Settings
from context_engine.services import readiness as readiness_module
from context_engine.services.readiness import ReadinessError, check_object_store_ready, probe_object_store
from context_engine.services.sources import storage_from_settings


@dataclass
class _FakeBody:
    data: bytes

    def read(self) -> bytes:
        return self.data


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_with: Exception | None = None
        self.last_range: str | None = None

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **kwargs: Any) -> dict[str, Any]:
        del Bucket, kwargs
        if self.fail_with is not None:
            raise self.fail_with
        self.objects[Key] = Body
        return {}

    def get_object(self, *, Bucket: str, Key: str, Range: str | None = None, **kwargs: Any) -> dict[str, Any]:
        del Bucket, kwargs
        if self.fail_with is not None:
            raise self.fail_with
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        data = self.objects[Key]
        if Range is None:
            return {"Body": _FakeBody(data)}
        self.last_range = Range
        assert Range.startswith("bytes=")
        spec = Range.removeprefix("bytes=")
        start_s, _, end_s = spec.partition("-")
        start = int(start_s)
        if start < 0:
            raise _ClientError("InvalidRange")
        if start >= len(data):
            raise _ClientError("InvalidRange")
        end = int(end_s) if end_s else len(data) - 1
        if end < start:
            raise _ClientError("InvalidRange")
        return {"Body": _FakeBody(data[start : end + 1])}

    def delete_object(self, *, Bucket: str, Key: str, **kwargs: Any) -> dict[str, Any]:
        del Bucket, kwargs
        if self.fail_with is not None:
            raise self.fail_with
        self.objects.pop(Key, None)
        return {}

    def head_object(self, *, Bucket: str, Key: str, **kwargs: Any) -> dict[str, Any]:
        del Bucket, kwargs
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"ContentLength": len(self.objects[Key])}


class _ClientError(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code, "Message": f"sentinel-{code}-endpoint-bucket-key"}}
        super().__init__(f"An error occurred ({code}) when calling the operation")


def _s3_settings(**overrides: Any) -> Settings:
    base = dict(
        testing=True,
        object_store_kind="s3",
        s3_endpoint="http://minio.internal:9000",
        s3_bucket="ce-objects",
        s3_access_key="test-access",
        s3_secret_key="test-secret",
        source_storage_root=".data/source-storage",
    )
    base.update(overrides)
    return Settings(**base)


def test_s3_object_store_put_get_range_delete() -> None:
    client = _FakeS3Client()
    store = S3ObjectStore(bucket="ce-objects", client=client)
    stored = store.put(b"hello-world-bytes", content_type="application/pdf")

    assert stored.key.startswith("obj_")
    assert stored.size_bytes == len(b"hello-world-bytes")
    assert len(stored.content_sha256) == 64
    assert "/" not in stored.key
    assert store.get(stored.key) == b"hello-world-bytes"
    assert store.get_range(stored.key, 0, 4) == b"hello"
    assert client.last_range == "bytes=0-4"
    assert store.get_range(stored.key, 6, None) == b"world-bytes"
    assert store.exists(stored.key) is True

    store.delete(stored.key)
    assert store.exists(stored.key) is False
    store.delete(stored.key)


def test_s3_object_store_rejects_path_escape_before_remote() -> None:
    client = _FakeS3Client()
    store = S3ObjectStore(bucket="ce-objects", client=client)
    with pytest.raises(ObjectStorageError, match="Object key is invalid"):
        store.get("../escape")
    with pytest.raises(ObjectStorageError, match="Object key is invalid"):
        store.put_key("a/../b", b"x")
    assert client.objects == {}


def test_s3_object_store_missing_object_is_closed() -> None:
    store = S3ObjectStore(bucket="ce-objects", client=_FakeS3Client())
    with pytest.raises(ObjectStorageError, match="Object unavailable"):
        store.get("obj_missing_key_value_here")


def test_s3_object_store_sanitizes_client_errors() -> None:
    client = _FakeS3Client()
    client.fail_with = _ClientError("AccessDenied")
    store = S3ObjectStore(bucket="ce-objects", client=client)
    with pytest.raises(ObjectStorageError) as exc_info:
        store.put(b"x")
    message = str(exc_info.value)
    assert message == "Object unavailable."
    assert "AccessDenied" not in message
    assert "sentinel" not in message
    assert "minio" not in message


def test_s3_object_store_unsatisfiable_range() -> None:
    client = _FakeS3Client()
    store = S3ObjectStore(bucket="ce-objects", client=client)
    stored = store.put(b"abcd")
    with pytest.raises(ObjectStorageError, match="unsatisfiable"):
        store.get_range(stored.key, 10, 20)
    with pytest.raises(ObjectStorageError, match="invalid"):
        store.get_range(stored.key, -1, 1)


def test_object_store_from_settings_filesystem_default(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    store = object_store_from_settings(settings)
    stored = store.put(b"probe")
    assert (tmp_path / "source-storage" / "objects" / stored.key).is_file()


def test_object_store_from_settings_s3_uses_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _s3_settings()
    fake = _FakeS3Client()

    monkeypatch.setattr(
        "context_engine.adapters.s3_object_store.S3ObjectStore.from_settings",
        classmethod(
            lambda cls, cfg, *, client=None: S3ObjectStore(
                bucket=cfg.s3_bucket or "",
                client=client or fake,
            )
        ),
    )
    store = object_store_from_settings(settings)
    assert isinstance(store, S3ObjectStore)
    stored = store.put(b"via-factory")
    assert stored.key.startswith("obj_")
    assert stored.key in fake.objects


def test_settings_s3_requires_env() -> None:
    with pytest.raises(ValueError, match="s3_endpoint"):
        Settings(testing=True, object_store_kind="s3", s3_bucket="b", s3_access_key="a", s3_secret_key="s")


def test_storage_from_settings_injects_composed_store(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    storage = storage_from_settings(settings)
    key = storage.put_original(b"original-bytes")
    assert storage.store.get(key) == b"original-bytes"


def test_probe_object_store_uses_settings_factory(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    probe_object_store(settings)
    assert (tmp_path / "source-storage" / "objects").is_dir()


def test_check_object_store_ready_maps_s3_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _s3_settings()

    def _fail(_settings: object) -> None:
        raise ObjectStorageError("Object unavailable.")

    monkeypatch.setattr(readiness_module, "probe_object_store", _fail)
    with pytest.raises(ReadinessError) as exc_info:
        check_object_store_ready(settings)
    assert exc_info.value.reason == "object_store_unavailable"
