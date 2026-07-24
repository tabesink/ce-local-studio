from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
import hmac
import json
import secrets
import time

from context_engine.config import Settings


CSRF_TOKEN_VERSION = 1
CSRF_PREAUTH_BINDING = "preauth"
TEST_CSRF_SIGNING_KEY = "context-engine-test-csrf-signing-key-not-for-production"


class CsrfTokenError(Exception):
    pass


def _signing_key(settings: Settings) -> bytes:
    value = settings.csrf_signing_key
    if value is None and settings.testing:
        value = TEST_CSRF_SIGNING_KEY
    if value is None or len(value.encode("utf-8")) < 32:
        raise CsrfTokenError("CSRF signing key is unavailable.")
    return value.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_csrf_token(settings: Settings, *, binding: str, now_epoch: int | None = None) -> str:
    payload = {
        "v": CSRF_TOKEN_VERSION,
        "iat": int(time.time()) if now_epoch is None else now_epoch,
        "n": secrets.token_urlsafe(24),
        "b": binding,
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _encode(hmac.new(_signing_key(settings), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_csrf_token(
    settings: Settings,
    token: str,
    *,
    binding: str,
    now_epoch: int | None = None,
) -> None:
    try:
        encoded, signature = token.split(".", 1)
        expected = _encode(hmac.new(_signing_key(settings), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise CsrfTokenError("Invalid CSRF token.")
        payload = json.loads(_decode(encoded))
        now = int(time.time()) if now_epoch is None else now_epoch
        issued_at = int(payload["iat"])
        if payload != {
            "v": CSRF_TOKEN_VERSION,
            "iat": issued_at,
            "n": payload["n"],
            "b": binding,
        }:
            raise CsrfTokenError("Invalid CSRF token.")
        if not isinstance(payload["n"], str) or not payload["n"]:
            raise CsrfTokenError("Invalid CSRF token.")
        if issued_at > now + 30 or now - issued_at > settings.session_ttl_seconds:
            raise CsrfTokenError("Expired CSRF token.")
    except (CsrfTokenError, ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        if isinstance(exc, CsrfTokenError):
            raise
        raise CsrfTokenError("Invalid CSRF token.") from exc
