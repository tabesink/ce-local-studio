#!/usr/bin/env python3
"""P12-05 AE4 trust proof through TLS public origin (HTTPS + Host/Origin/CSRF + API denial).

Does not claim AE1 incremental deltas. Never prints secrets from the env file.
Requires verified CA (ca=yes) and positive unpublished-API evidence (KTD13).
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import ssl
import subprocess
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
            # Only for optional direct-API HTTP denial probes — AE4 public origin requires ca=yes.
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


def _assert_api_unpublished(env_file: Path, compose_dir: Path, *, include_live: bool) -> int:
    """Positive unpublished-API evidence from compose config (no secret env dump)."""
    files = ["-f", "compose.stack.yml"]
    if include_live:
        files.extend(["-f", "compose.stack.live.yml"])
    files.extend(["-f", "compose.stack.tls.yml"])
    proc = subprocess.run(
        ["docker", "compose", "--env-file", str(env_file), *files, "config", "--format", "json"],
        cwd=compose_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return _fail(f"compose config failed: {proc.stderr or proc.stdout}")
    try:
        cfg = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _fail("compose config JSON parse failed")
    services = cfg.get("services") or {}
    for name in ("api", "frontend"):
        svc = services.get(name)
        if not isinstance(svc, dict):
            return _fail(f"compose config missing service {name}")
        ports = svc.get("ports") or []
        if ports:
            return _fail(f"service {name} still publishes ports={ports!r} — AE4 requires unpublished")
    print("OK: compose config shows api/frontend ports unpublished")
    return 0


def run_trust(
    *,
    public_origin: str,
    username: str,
    password: str,
    api_publish: str | None,
    ca_file: Path,
    timeout: float,
    env_file: Path,
    compose_dir: Path,
    include_live: bool,
) -> int:
    if not public_origin.startswith("https://"):
        return _fail("CE_STACK_PUBLIC_ORIGIN must be https://… for P12-05 TLS altitude")

    unpublished = _assert_api_unpublished(env_file, compose_dir, include_live=include_live)
    if unpublished != 0:
        return unpublished

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

    # Missing CSRF header on unsafe mutation.
    status, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=None,
        body={"title": "should-fail-csrf-missing"},
    )
    if status not in {403, 401}:
        return _fail(f"CSRF missing expected 401/403, got {status}")
    print(f"OK: CSRF missing fail-closed HTTP {status}")

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
        # Optional extra negative — direct probe must not be green.
        api_client = _HttpsClient(api_publish, timeout=min(timeout, 15.0), ca_file=None)
        status, _body = api_client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
        if status == 0:
            print("OK: direct API unreachable (connection failed) — extra denial probe")
        elif status == 200:
            return _fail("direct API csrf unexpectedly succeeded")
        elif 200 <= status < 300:
            return _fail(f"direct API unexpectedly green HTTP {status}")
        else:
            print(f"OK: direct API fail-closed HTTP {status}")
    else:
        print("OK: AE4 unpublished evidence from compose config (no --api-publish vacuous pass)")

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
        help="Optional extra direct API base probe (compose unpublished evidence is always required)",
    )
    parser.add_argument(
        "--compose-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--skip-live-overlay",
        action="store_true",
        help="Compose config check uses stack+tls only",
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
    if ca_file is None:
        return _fail(
            "ca=insecure-local forbidden for AE4 — set CE_STACK_TLS_CERT_DIR/cert.pem or --ca-file"
        )

    api_publish = args.api_publish.strip() or None
    # Never echo password / keys — only presence of username.
    print(
        f"P12-05 trust proof -> {public_origin} "
        f"(user present={bool(username)}; ca=yes)"
    )
    return run_trust(
        public_origin=public_origin,
        username=username,
        password=password,
        api_publish=api_publish,
        ca_file=ca_file,
        timeout=args.timeout,
        env_file=args.env_file,
        compose_dir=args.compose_dir,
        include_live=not args.skip_live_overlay,
    )


if __name__ == "__main__":
    sys.exit(main())
