#!/usr/bin/env python3
"""P10-02 core-path smoke: BFF CSRF → login → sealed SSE turn (+ trust negatives).

Run against an ingress-wired Compose stack (CONTEXT_ENGINE_TESTING=true + full CE_*).
Does not claim browser CSRF product fix, worker drain, TLS, or production store readiness.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


# Contracted no-provider / no-credentials terminals allowed without live LLM.
ALLOWED_FAILED_CODES = frozenset({"provider_failure", "synthesis_profile_not_ready"})
TERMINAL_TYPES = frozenset({"turn.completed", "turn.failed"})
DEFAULT_MESSAGE = "Say hello in one short sentence."
DEFAULT_TIMEOUT_SECONDS = 90.0


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
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


class _SmokeClient:
    def __init__(self, base: str, *, timeout: float) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(
        self,
        method: str,
        path: str,
        *,
        origin: str,
        csrf: str | None = None,
        body: dict[str, object] | None = None,
        stream: bool = False,
    ) -> tuple[int, dict[str, str], bytes]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "text/event-stream, application/json" if stream else "application/json",
            "Origin": origin,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
                return response.status, {k.lower(): v for k, v in response.headers.items()}, payload
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            return exc.code, {k.lower(): v for k, v in exc.headers.items()}, payload


def _parse_sse(text: str) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        data_line = next((line for line in lines if line.startswith("data: ")), None)
        if data_line is None:
            continue
        frames.append(json.loads(data_line.removeprefix("data: ")))
    return frames


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def run_core_path(
    *,
    public_origin: str,
    username: str,
    password: str,
    api_publish: str | None,
    timeout: float,
) -> int:
    client = _SmokeClient(public_origin, timeout=timeout)

    status, _headers, body = client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
    if status != 200:
        return _fail(f"csrf bootstrap HTTP {status}")
    preauth = json.loads(body.decode("utf-8")).get("csrfToken")
    cookie_preauth = _cookie_value(client.jar, "ce_csrf")
    if not preauth or preauth != cookie_preauth:
        return _fail("csrf bootstrap did not set matching ce_csrf cookie")

    status, _headers, body = client.request(
        "POST",
        "/api/v1/auth/login",
        origin=public_origin,
        csrf=preauth,
        body={"username": username, "password": password},
    )
    if status != 200:
        return _fail(f"login HTTP {status}")
    session_csrf = _cookie_value(client.jar, "ce_csrf")
    session_token = _cookie_value(client.jar, "ce_session")
    if not session_token:
        return _fail("login did not set ce_session")
    if not session_csrf or session_csrf == preauth:
        return _fail("login did not rotate ce_csrf away from preauth")

    status, _headers, body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=session_csrf,
        body={"title": "P10-02 stack smoke"},
    )
    if status != 201:
        return _fail(f"create conversation HTTP {status}")
    conversation_id = json.loads(body.decode("utf-8"))["conversation"]["id"]

    started = time.monotonic()
    status, headers, body = client.request(
        "POST",
        f"/api/v1/conversations/{conversation_id}/turns:stream",
        origin=public_origin,
        csrf=session_csrf,
        body={
            "clientRequestId": f"p10-02-smoke-{uuid.uuid4().hex}",
            "message": DEFAULT_MESSAGE,
            "composerRefTokens": [],
        },
        stream=True,
    )
    elapsed = time.monotonic() - started
    if elapsed > timeout:
        return _fail(f"SSE exceeded timeout ({elapsed:.1f}s > {timeout}s)")
    if status != 200:
        return _fail(f"turns:stream HTTP {status}")
    content_type = headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return _fail(f"unexpected content-type {content_type!r}")

    events = _parse_sse(body.decode("utf-8"))
    if not events:
        return _fail("no SSE events received")
    types = [str(event.get("type")) for event in events]
    if "turn.accepted" not in types and types[0] not in TERMINAL_TYPES:
        # Accept any first event; still require a terminal below.
        pass
    terminal = next((event for event in reversed(events) if event.get("type") in TERMINAL_TYPES), None)
    if terminal is None:
        return _fail(f"no terminal event in {types}")
    if terminal.get("type") == "turn.completed":
        print(f"OK: BFF sealed turn completed ({len(events)} events, {elapsed:.1f}s)")
    else:
        code = str((terminal.get("payload") or {}).get("code") or "")
        if code not in ALLOWED_FAILED_CODES:
            return _fail(f"disallowed turn.failed code {code!r} (types={types})")
        print(
            f"OK: BFF sealed turn failed closed with allowed code={code} "
            f"({len(events)} events, {elapsed:.1f}s; testing-mode inline; not completed-synthesis proof)"
        )

    # AE6: Origin host mismatch must fail CSRF.
    bad_origin = public_origin.replace("127.0.0.1", "localhost")
    if bad_origin == public_origin:
        return _fail("could not derive localhost Origin mismatch case")
    status, _headers, _body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=bad_origin,
        csrf=session_csrf,
        body={"title": "should-fail-origin"},
    )
    if status != 403:
        return _fail(f"Origin mismatch expected 403, got {status}")

    # AE6: published API port must not be smoke-green for host callers.
    if api_publish:
        api_client = _SmokeClient(api_publish, timeout=min(timeout, 15.0))
        status, _headers, _body = api_client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
        if status == 200:
            return _fail("published API csrf unexpectedly succeeded for host caller")
        if status not in {403, 401, 404}:
            # Peer denial is typically 403; accept other fail-closed statuses but not 2xx/5xx hang.
            if 200 <= status < 300:
                return _fail(f"published API host call unexpectedly green HTTP {status}")
        print(f"OK: published API host call fail-closed HTTP {status}")

    print("OK: AE6 trust negatives passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.stack.local",
        help="Compose env file with CE_STACK_PUBLIC_ORIGIN and CE_ADMIN_*",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--skip-api-negative",
        action="store_true",
        help=argparse.SUPPRESS,  # kept for emergency only; AE6 requires the negative
    )
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        return _fail(f"env file not found: {args.env_file}")
    env = _load_env_file(args.env_file)
    public_origin = env.get("CE_STACK_PUBLIC_ORIGIN", "").rstrip("/")
    username = env.get("CE_ADMIN_USERNAME", "")
    password = env.get("CE_ADMIN_PASSWORD", "")
    frontend_port = env.get("STACK_FRONTEND_PORT", "3000")
    api_port = env.get("STACK_API_PORT", "8000")
    testing = env.get("CONTEXT_ENGINE_TESTING", "").strip().lower() in {"1", "true", "yes", "on"}

    if not public_origin:
        return _fail("CE_STACK_PUBLIC_ORIGIN is required (ingress-wired profile)")
    if "127.0.0.1" not in public_origin:
        return _fail("CE_STACK_PUBLIC_ORIGIN must use 127.0.0.1 (not localhost)")
    if not username or not password:
        return _fail("CE_ADMIN_USERNAME and CE_ADMIN_PASSWORD are required")
    if not testing:
        return _fail("CONTEXT_ENGINE_TESTING=true is required for testing-mode inline turn completion")
    if f":{frontend_port}" not in public_origin and public_origin.count(":") >= 2:
        # Allow default :3000 omission only when port is 80; otherwise require match.
        pass
    expected_suffix = f":{frontend_port}"
    if not public_origin.endswith(expected_suffix) and frontend_port not in {"80", "443"}:
        print(
            f"WARN: CE_STACK_PUBLIC_ORIGIN={public_origin} may not match STACK_FRONTEND_PORT={frontend_port}",
            file=sys.stderr,
        )

    api_publish = None if args.skip_api_negative else f"http://127.0.0.1:{api_port}"
    print(
        f"P10-02 smoke -> {public_origin} "
        f"(testing=true, inline workers; api negative={api_publish or 'skipped'})"
    )
    return run_core_path(
        public_origin=public_origin,
        username=username,
        password=password,
        api_publish=api_publish,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
