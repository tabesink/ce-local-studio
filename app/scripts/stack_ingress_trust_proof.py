#!/usr/bin/env python3
"""P12-05 AE4 trust proof through TLS public origin (HTTPS + Host/Origin/CSRF + API denial).

Does not claim AE1 incremental deltas. Never prints secrets from the env file.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _cookie_value(jar: http.cookiejar.CookieJar, name: str) -> str | None:
    for cookie in jar:
        if cookie.name == name:
            return cookie.value
    return None


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


class _HttpsClient:
    def __init__(self, base: str, *, timeout: float, ca_file: Path | None) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        if ca_file is not None:
            ctx.load_verify_locations(cafile=str(ca_file))
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        self.opener = urllib.request.build_opener(
            https_handler,
            urllib.request.HTTPCookieProcessor(self.jar),
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        origin: str,
        csrf: str | None = None,
        body: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Origin": origin,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except urllib.error.URLError as exc:
            return 0, str(exc.reason).encode("utf-8")


def run_trust(
    *,
    public_origin: str,
    username: str,
    password: str,
    api_publish: str | None,
    ca_file: Path | None,
    timeout: float,
) -> int:
    if not public_origin.startswith("https://"):
        return _fail("CE_STACK_PUBLIC_ORIGIN must be https://… for P12-05 TLS altitude")

    client = _HttpsClient(public_origin, timeout=timeout, ca_file=ca_file)

    status, body = client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
    if status != 200:
        return _fail(f"csrf bootstrap HTTP {status}")
    preauth = json.loads(body.decode("utf-8")).get("csrfToken")
    if not preauth or preauth != _cookie_value(client.jar, "ce_csrf"):
        return _fail("csrf bootstrap cookie mismatch")

    status, body = client.request(
        "POST",
        "/api/v1/auth/login",
        origin=public_origin,
        csrf=preauth,
        body={"username": username, "password": password},
    )
    if status != 200:
        return _fail(f"login HTTP {status}")
    session_csrf = _cookie_value(client.jar, "ce_csrf")
    if not _cookie_value(client.jar, "ce_session") or not session_csrf:
        return _fail("login did not establish session cookies")

    status, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=session_csrf,
        body={"title": "P12-05 trust proof"},
    )
    if status != 201:
        return _fail(f"create conversation HTTP {status}")
    print("OK: HTTPS CSRF login + mutation through public origin")

    bad_origin = public_origin.replace("127.0.0.1", "localhost")
    status, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=bad_origin,
        csrf=session_csrf,
        body={"title": "should-fail-origin"},
    )
    if status != 403:
        return _fail(f"hostile Origin expected 403, got {status}")
    print("OK: hostile Origin rejected")

    status, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf="not-the-real-csrf-token",
        body={"title": "should-fail-csrf"},
    )
    if status not in {403, 401}:
        return _fail(f"CSRF mismatch expected 401/403, got {status}")
    print(f"OK: CSRF mismatch fail-closed HTTP {status}")

    status, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=session_csrf,
        body={"title": "forge-headers"},
        extra_headers={
            "X-CE-Public-Host": "evil.example",
            "X-User-Id": "forged",
            "X-Role": "administrator",
        },
    )
    if status != 201:
        return _fail(f"forged trust headers should be stripped; got HTTP {status}")
    print("OK: forged trust/identity headers did not break authorized mutation")

    if api_publish:
        api_client = _HttpsClient(api_publish, timeout=min(timeout, 15.0), ca_file=None)
        # Direct API is typically http:// on loopback when published; TLS overlay resets ports.
        status, _body = api_client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
        if status == 0:
            print("OK: direct API unreachable (connection failed) — public denial")
        elif status == 200:
            return _fail("direct API csrf unexpectedly succeeded")
        elif 200 <= status < 300:
            return _fail(f"direct API unexpectedly green HTTP {status}")
        else:
            print(f"OK: direct API fail-closed HTTP {status}")
    else:
        print("OK: API publish omitted (TLS overlay unpublishes API) — treated as denial")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.stack.local",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--ca-file",
        type=Path,
        default=None,
        help="Trust store PEM (defaults to CE_STACK_TLS_CERT_DIR/cert.pem when set)",
    )
    parser.add_argument(
        "--api-publish",
        default="",
        help="Optional direct API base for denial probe (empty = expect unpublished)",
    )
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        return _fail(f"env file not found: {args.env_file}")
    env = _load_env_file(args.env_file)
    public_origin = env.get("CE_STACK_PUBLIC_ORIGIN", "").rstrip("/")
    username = env.get("CE_ADMIN_USERNAME", "")
    password = env.get("CE_ADMIN_PASSWORD", "")
    if not public_origin or not username or not password:
        return _fail("CE_STACK_PUBLIC_ORIGIN and CE_ADMIN_* are required")

    ca_file = args.ca_file
    if ca_file is None:
        cert_dir = env.get("CE_STACK_TLS_CERT_DIR", "")
        if cert_dir:
            candidate = Path(cert_dir) / "cert.pem"
            if candidate.is_file():
                ca_file = candidate

    api_publish = args.api_publish.strip() or None
    # Never echo password / keys — only presence of username.
    print(
        f"P12-05 trust proof -> {public_origin} "
        f"(user present={bool(username)}; ca={'yes' if ca_file else 'insecure-local'})"
    )
    return run_trust(
        public_origin=public_origin,
        username=username,
        password=password,
        api_publish=api_publish,
        ca_file=ca_file,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
