"""P8-03 focused capacity shed matrix — execute existing paths; no new limiters."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from context_engine.api.errors import ApiError
from context_engine.api.routes import MAX_SOURCE_FILE_SIZE_BYTES, _content_length_too_large, admin_upload_source
from context_engine.config import Settings
from context_engine.models import ROLE_ADMINISTRATOR, User
from context_engine.services.source_upload import UploadValidationError, validate_upload_bytes


def test_content_length_gate_rejects_oversize_envelope() -> None:
    request = MagicMock()
    request.headers = {"content-length": str(MAX_SOURCE_FILE_SIZE_BYTES + (1024 * 1024) + 1)}
    assert _content_length_too_large(request) is True

    request.headers = {"content-length": str(MAX_SOURCE_FILE_SIZE_BYTES)}
    assert _content_length_too_large(request) is False


def test_oversize_upload_bytes_is_content_rejected() -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload_bytes(
            b"x" * (MAX_SOURCE_FILE_SIZE_BYTES + 1),
            filename="big.txt",
            declared_content_type="text/plain",
        )
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "content_rejected"


def test_admin_upload_content_length_gate_raises_413_content_rejected() -> None:
    request = MagicMock()
    request.headers = {
        "content-length": str(MAX_SOURCE_FILE_SIZE_BYTES + (1024 * 1024) + 1),
        "content-type": "multipart/form-data; boundary=x",
    }
    admin = User(
        username="admin-413@example.test",
        password_hash="synthetic",
        role=ROLE_ADMINISTRATOR,
    )
    settings = Settings(testing=True)

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(
            admin_upload_source(
                request,
                "domain-413",
                admin,
                MagicMock(),
                settings,
            )
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "content_rejected"
    assert exc_info.value.fields in (None, {})
    assert "Traceback" not in str(exc_info.value)
