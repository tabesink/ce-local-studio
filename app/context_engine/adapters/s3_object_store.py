from __future__ import annotations

import hashlib
from typing import Any

from context_engine.adapters.object_storage import (
    ObjectStorageError,
    StoredObject,
    new_object_key,
)
from context_engine.config import Settings


def _validate_object_key(key: str) -> str:
    if not key or key.strip() != key:
        raise ObjectStorageError("Object key is invalid.")
    if "/" in key or "\\" in key or ".." in key or key in {".", ".."}:
        raise ObjectStorageError("Object key is invalid.")
    return key


def _error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            code = error.get("Code")
            if isinstance(code, str):
                return code
    return ""


def _map_storage_error(exc: BaseException) -> ObjectStorageError:
    """Map any S3/client failure to a closed ObjectStorageError (no leak)."""
    del exc
    return ObjectStorageError("Object unavailable.")


class S3ObjectStore:
    """S3-compatible governed object store (MinIO / S3 API)."""

    def __init__(
        self,
        *,
        bucket: str,
        client: Any,
    ) -> None:
        if not bucket or not bucket.strip():
            raise ValueError("s3_bucket is required.")
        self._bucket = bucket.strip()
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings, *, client: Any | None = None) -> S3ObjectStore:
        if client is not None:
            return cls(bucket=settings.s3_bucket or "", client=client)
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ValueError(
                "boto3 is required for object_store_kind='s3'; install the object-store extra."
            ) from exc
        endpoint = (settings.s3_endpoint or "").strip()
        bucket = (settings.s3_bucket or "").strip()
        access_key = (settings.s3_access_key or "").strip()
        secret_key = (settings.s3_secret_key or "").strip()
        if not endpoint or not bucket or not access_key or not secret_key:
            raise ValueError("S3 object store settings are incomplete.")
        config = Config(s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"})
        boto_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=settings.s3_region,
            config=config,
        )
        return cls(bucket=bucket, client=boto_client)

    def put(self, data: bytes, *, content_type: str | None = None) -> StoredObject:
        return self.put_key(new_object_key(), data, content_type=content_type)

    def put_key(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredObject:
        safe_key = _validate_object_key(key)
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        try:
            self._client.put_object(Bucket=self._bucket, Key=safe_key, Body=data, **extra)
        except Exception as exc:
            raise _map_storage_error(exc) from None
        return StoredObject(
            key=safe_key,
            size_bytes=len(data),
            content_sha256=hashlib.sha256(data).hexdigest(),
        )

    def get(self, key: str) -> bytes:
        safe_key = _validate_object_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=safe_key)
            body = response["Body"].read()
        except Exception as exc:
            raise _map_storage_error(exc) from None
        if not isinstance(body, (bytes, bytearray)):
            raise ObjectStorageError("Object unavailable.")
        return bytes(body)

    def get_range(self, key: str, start: int, end: int | None = None) -> bytes:
        if start < 0:
            raise ObjectStorageError("Object range is invalid.")
        if end is not None and end < start:
            raise ObjectStorageError("Object range is invalid.")
        safe_key = _validate_object_key(key)
        range_header = f"bytes={start}-" if end is None else f"bytes={start}-{end}"
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=safe_key, Range=range_header)
            body = response["Body"].read()
        except Exception as exc:
            code = _error_code(exc)
            if code in {"InvalidRange", "RequestedRangeNotSatisfiable"}:
                raise ObjectStorageError("Object range is unsatisfiable.") from None
            raise _map_storage_error(exc) from None
        if not isinstance(body, (bytes, bytearray)):
            raise ObjectStorageError("Object unavailable.")
        data = bytes(body)
        if not data and start > 0:
            raise ObjectStorageError("Object range is unsatisfiable.")
        return data

    def delete(self, key: str) -> None:
        safe_key = _validate_object_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=safe_key)
        except Exception as exc:
            if _error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
                return
            raise ObjectStorageError("Object could not be removed.") from None

    def exists(self, key: str) -> bool:
        safe_key = _validate_object_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=safe_key)
            return True
        except Exception:
            return False
