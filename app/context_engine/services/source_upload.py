from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass

MAX_SOURCE_FILE_SIZE_BYTES = 25 * 1024 * 1024
ALLOWED_SOURCE_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"
_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_CHUNK_SIZE = 64 * 1024
_MAX_ZIP_ENTRIES = 10_000
_MAX_COMPRESSION_RATIO = 100.0


class UploadValidationError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ValidatedUpload:
    data: bytes
    content_type: str
    sha256: str
    size_bytes: int


def sniff_source_content_type(data: bytes, *, filename: str | None) -> str:
    if not data:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    if data.startswith(_PDF_MAGIC):
        return "application/pdf"
    if data.startswith(_ZIP_MAGIC):
        if _looks_like_docx(data):
            return _DOCX_CONTENT_TYPE
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    if b"\x00" in data[:8192]:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.") from exc
    name = (filename or "").lower()
    if name.endswith((".md", ".markdown")):
        return "text/markdown"
    return "text/plain"


def _looks_like_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(name.startswith("word/") for name in names)


def assert_safe_container(data: bytes, content_type: str) -> None:
    if content_type != _DOCX_CONTENT_TYPE:
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.") from exc
    if len(infos) > _MAX_ZIP_ENTRIES:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    total_uncompressed = 0
    for info in infos:
        if info.file_size < 0 or info.compress_size < 0:
            raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
        if info.file_size > MAX_SOURCE_FILE_SIZE_BYTES:
            raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_SOURCE_FILE_SIZE_BYTES:
            raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > _MAX_COMPRESSION_RATIO and info.file_size > 1024 * 1024:
                raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    if not _looks_like_docx(data):
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")


def validate_upload_bytes(
    data: bytes,
    *,
    filename: str | None,
    declared_content_type: str | None = None,
) -> ValidatedUpload:
    del declared_content_type  # never authoritative
    if len(data) > MAX_SOURCE_FILE_SIZE_BYTES:
        raise UploadValidationError(413, "content_rejected", "Uploaded content was rejected.")
    content_type = sniff_source_content_type(data, filename=filename)
    if content_type not in ALLOWED_SOURCE_CONTENT_TYPES:
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    assert_safe_container(data, content_type)
    digest = hashlib.sha256(data).hexdigest()
    return ValidatedUpload(data=data, content_type=content_type, sha256=digest, size_bytes=len(data))


async def read_upload_stream(
    chunks: AsyncIterator[bytes],
    *,
    filename: str | None,
    max_bytes: int = MAX_SOURCE_FILE_SIZE_BYTES,
) -> ValidatedUpload:
    hasher = hashlib.sha256()
    parts: list[bytes] = []
    total = 0
    async for chunk in chunks:
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise UploadValidationError(413, "content_rejected", "Uploaded content was rejected.")
        hasher.update(chunk)
        parts.append(chunk)
    data = b"".join(parts)
    validated = validate_upload_bytes(data, filename=filename)
    if validated.sha256 != hasher.hexdigest():
        raise UploadValidationError(422, "content_rejected", "Uploaded content was rejected.")
    return validated


async def iter_upload_file(upload) -> AsyncIterator[bytes]:  # noqa: ANN001
    while True:
        chunk = await upload.read(_CHUNK_SIZE)
        if not chunk:
            break
        yield chunk
