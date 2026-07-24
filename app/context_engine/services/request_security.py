from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

from fastapi import Request

from context_engine.config import Settings
from context_engine.security import hash_session_token
from context_engine.services.csrf import CSRF_PREAUTH_BINDING, CsrfTokenError, verify_csrf_token


PUBLIC_HOST_HEADER = "X-CE-Public-Host"
PUBLIC_PROTO_HEADER = "X-CE-Public-Proto"
CLIENT_BUCKET_HEADER = "X-CE-Client-Bucket"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestSecurityError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.status_code = 403
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RequestSecurityPolicy:
    enabled: bool
    public_origin: str = ""
    public_host: str = ""
    public_proto: str = ""
    internal_hosts: tuple[str, ...] = ()
    trusted_peers: tuple[str, ...] = ()


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


def build_request_security_policy(settings: Settings) -> RequestSecurityPolicy:
    configured = any(
        value is not None
        for value in (
            settings.public_origin,
            settings.internal_hosts,
            settings.trusted_bff_peers,
            settings.csrf_signing_key,
        )
    )
    if settings.testing and not configured:
        return RequestSecurityPolicy(enabled=False)
    if not all((settings.public_origin, settings.internal_hosts, settings.trusted_bff_peers, settings.csrf_signing_key)):
        raise ValueError("Trusted ingress and CSRF settings are required.")

    parsed = urlsplit(settings.public_origin)
    if parsed.scheme not in ({"http", "https"} if settings.testing else {"https"}):
        raise ValueError("public_origin must use an approved scheme.")
    if not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("public_origin must be one canonical origin.")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    internal_hosts = _csv(settings.internal_hosts)
    trusted_peers = _csv(settings.trusted_bff_peers)
    if not internal_hosts or any("*" in host for host in internal_hosts):
        raise ValueError("internal_hosts must be a non-wildcard allowlist.")
    if not trusted_peers:
        raise ValueError("trusted_bff_peers must not be empty.")
    for peer in trusted_peers:
        try:
            ip_network(peer, strict=False)
        except ValueError:
            if not settings.testing:
                raise ValueError("trusted_bff_peers must contain only IP/CIDR values.")
    if len(settings.csrf_signing_key.encode("utf-8")) < 32:
        raise ValueError("csrf_signing_key must contain at least 32 bytes.")
    return RequestSecurityPolicy(
        enabled=True,
        public_origin=origin,
        public_host=parsed.netloc,
        public_proto=parsed.scheme,
        internal_hosts=internal_hosts,
        trusted_peers=trusted_peers,
    )


def _trusted_peer(host: str | None, policy: RequestSecurityPolicy) -> bool:
    if not host:
        return False
    for peer in policy.trusted_peers:
        if host == peer:
            return True
        try:
            if ip_address(host) in ip_network(peer, strict=False):
                return True
        except ValueError:
            continue
    return False


def enforce_request_security(request: Request, settings: Settings, policy: RequestSecurityPolicy) -> None:
    if not request.url.path.startswith("/api/v1"):
        return
    if not policy.enabled:
        request.state.client_bucket = "test-bypass"
        return
    if request.headers.get("host", "").split(":", 1)[0] not in policy.internal_hosts:
        raise RequestSecurityError("forbidden", "Forbidden.")
    if not _trusted_peer(request.client.host if request.client else None, policy):
        raise RequestSecurityError("forbidden", "Forbidden.")
    if request.headers.get(PUBLIC_HOST_HEADER) != policy.public_host or request.headers.get(PUBLIC_PROTO_HEADER) != policy.public_proto:
        raise RequestSecurityError("forbidden", "Forbidden.")

    if request.method not in UNSAFE_METHODS:
        return
    if request.headers.get("origin") != policy.public_origin:
        raise RequestSecurityError("csrf_invalid", "CSRF validation failed.")
    client_bucket = request.headers.get(CLIENT_BUCKET_HEADER, "")
    if not 1 <= len(client_bucket) <= 128:
        raise RequestSecurityError("forbidden", "Forbidden.")
    request.state.client_bucket = client_bucket

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise RequestSecurityError("csrf_invalid", "CSRF validation failed.")
    if request.url.path == "/api/v1/auth/login":
        binding = CSRF_PREAUTH_BINDING
    else:
        session_token = request.cookies.get(settings.session_cookie_name)
        if not session_token:
            raise RequestSecurityError("csrf_invalid", "CSRF validation failed.")
        binding = hash_session_token(session_token)
    try:
        verify_csrf_token(settings, cookie_token, binding=binding)
    except CsrfTokenError as exc:
        raise RequestSecurityError("csrf_invalid", "CSRF validation failed.") from exc
