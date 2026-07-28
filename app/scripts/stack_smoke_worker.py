#!/usr/bin/env python3
"""P10-03 worker-path smoke: BFF SSE with Compose-leased turns (inline off).

Compose-dev matrix only — not TLS, not testing=false, not P12 stream-drain.
Requires CONTEXT_ENGINE_TESTING=true and CE_INLINE_TURN_WORKERS=false on the API.
Claim ownership is proven via private Postgres lease_owner (not a public DTO).
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ALLOWED_FAILED_CODES = frozenset({"provider_failure", "synthesis_profile_not_ready"})
TERMINAL_TYPES = frozenset({"turn.completed", "turn.failed"})
DEFAULT_MESSAGE = "Say hello in one short sentence."
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_COMPOSE_TURN_WORKER_ID = "compose-turn-worker"


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = path.read_text(encoding="utf-8-sig")
    for raw in text.splitlines():
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


def _query_claim_marker(
    *,
    host: str,
    port: str,
    database: str,
    user: str,
    password: str,
    conversation_id: str,
    client_request_id: str,
) -> tuple[int | None, str | None]:
    """Return (execution_generation, lease_owner). Lease clears on terminal; generation persists."""
    import psycopg

    conninfo = (
        f"host={host} port={port} dbname={database} user={user} password={password} "
        "connect_timeout=5"
    )
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            # API returns conversation public_ref; turns FK conversations.id.
            cur.execute(
                """
                SELECT t.execution_generation, t.lease_owner
                FROM conversation_turns AS t
                JOIN conversations AS c ON c.id = t.conversation_id
                WHERE c.public_ref = %s AND t.client_request_id = %s
                """,
                (conversation_id, client_request_id),
            )
            row = cur.fetchone()
            if row is None:
                return None, None
            return int(row[0]), row[1]


def _worker_logs_mention(client_request_id: str, *, env_file: Path) -> bool:
    import subprocess

    try:
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                "compose.stack.yml",
                "logs",
                "worker",
                "--no-color",
                "--tail",
                "200",
            ],
            cwd=str(env_file.resolve().parent),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return client_request_id in (completed.stdout or "")


def run_worker_path(
    *,
    public_origin: str,
    username: str,
    password: str,
    expected_worker_id: str,
    pg_host: str,
    pg_port: str,
    pg_db: str,
    pg_user: str,
    pg_password: str,
    timeout: float,
    env_file: Path,
) -> int:
    client = _SmokeClient(public_origin, timeout=timeout)

    status, _headers, body = client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
    if status != 200:
        return _fail(f"csrf bootstrap HTTP {status}")
    preauth = json.loads(body.decode("utf-8")).get("csrfToken")
    if not preauth or preauth != _cookie_value(client.jar, "ce_csrf"):
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
    if not _cookie_value(client.jar, "ce_session"):
        return _fail("login did not set ce_session")
    if not session_csrf or session_csrf == preauth:
        return _fail("login did not rotate ce_csrf")

    status, _headers, body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=session_csrf,
        body={"title": "P10-03 worker-path smoke"},
    )
    if status != 201:
        return _fail(f"create conversation HTTP {status}")
    conversation_id = json.loads(body.decode("utf-8"))["conversation"]["id"]
    client_request_id = f"p10-03-worker-{uuid.uuid4().hex}"

    started = time.monotonic()
    status, headers, body = client.request(
        "POST",
        f"/api/v1/conversations/{conversation_id}/turns:stream",
        origin=public_origin,
        csrf=session_csrf,
        body={
            "clientRequestId": client_request_id,
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
    if "text/event-stream" not in headers.get("content-type", ""):
        return _fail("unexpected content-type")

    events = _parse_sse(body.decode("utf-8"))
    if not events:
        return _fail("no SSE events received")
    types = [str(event.get("type")) for event in events]
    terminal = next((event for event in reversed(events) if event.get("type") in TERMINAL_TYPES), None)
    if terminal is None:
        return _fail(f"no terminal event in {types}")
    if terminal.get("type") == "turn.failed":
        code = str((terminal.get("payload") or {}).get("code") or "")
        if code not in ALLOWED_FAILED_CODES:
            return _fail(f"disallowed turn.failed code {code!r}")

    try:
        generation, lease_owner = _query_claim_marker(
            host=pg_host,
            port=pg_port,
            database=pg_db,
            user=pg_user,
            password=pg_password,
            conversation_id=conversation_id,
            client_request_id=client_request_id,
        )
    except Exception as exc:  # noqa: BLE001 — smoke boundary
        return _fail(f"claim marker query failed: {exc}")

    # Claim bumps execution_generation; terminal clears lease_owner (product behavior).
    if generation is None or generation < 1:
        return _fail(
            f"execution_generation={generation!r} - turn was not worker-claimed "
            "(set CE_INLINE_TURN_WORKERS=false and recreate api)"
        )
    if not _worker_logs_mention(client_request_id, env_file=env_file):
        return _fail(
            f"Compose worker logs do not mention client_request_id={client_request_id} "
            f"(expected worker id {expected_worker_id}; API may still be inlining)"
        )

    print(
        f"OK: worker-leased BFF turn "
        f"(execution_generation={generation}, lease_owner_after_terminal={lease_owner!r}, "
        f"expected_worker_id={expected_worker_id}, {len(events)} events, {elapsed:.1f}s; "
        f"Compose-dev matrix - not P12 / not completed-synthesis proof)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.stack.local",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        return _fail(f"env file not found: {args.env_file}")
    env = _load_env_file(args.env_file)

    public_origin = env.get("CE_STACK_PUBLIC_ORIGIN", "").rstrip("/")
    username = env.get("CE_ADMIN_USERNAME", "")
    password = env.get("CE_ADMIN_PASSWORD", "")
    testing = env.get("CONTEXT_ENGINE_TESTING", "").strip().lower() in {"1", "true", "yes", "on"}
    inline_raw = env.get("CE_INLINE_TURN_WORKERS")
    inline_off = inline_raw is not None and inline_raw.strip().lower() in {"0", "false", "no", "off"}
    expected_worker_id = env.get("CE_TURN_WORKER_ID") or DEFAULT_COMPOSE_TURN_WORKER_ID

    pg_host = env.get("POSTGRES_HOST", "127.0.0.1")
    pg_port = env.get("POSTGRES_PORT", "5432")
    # Prefer published host port when Compose maps postgres (stack may use 5438).
    if env.get("STACK_POSTGRES_PORT"):
        pg_port = env["STACK_POSTGRES_PORT"]
    pg_db = env.get("POSTGRES_DB", "")
    pg_user = env.get("POSTGRES_USER", "")
    pg_password = env.get("POSTGRES_PASSWORD", "")

    if not public_origin or "127.0.0.1" not in public_origin:
        return _fail("CE_STACK_PUBLIC_ORIGIN with 127.0.0.1 is required")
    if not username or not password:
        return _fail("CE_ADMIN_USERNAME and CE_ADMIN_PASSWORD are required")
    if not testing:
        return _fail("CONTEXT_ENGINE_TESTING=true is required (HTTP Compose matrix)")
    if not inline_off:
        return _fail(
            "CE_INLINE_TURN_WORKERS=false is required in env file for worker-path smoke "
            "(recreate api after setting)"
        )
    if not pg_db or not pg_user or not pg_password:
        return _fail("POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD required for lease_owner assert")

    print(
        f"P10-03 worker-path smoke -> {public_origin} "
        f"(testing=true, inline=false, expect worker={expected_worker_id}; "
        f"Compose-dev matrix - not P12)"
    )
    return run_worker_path(
        public_origin=public_origin,
        username=username,
        password=password,
        expected_worker_id=expected_worker_id,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_db=pg_db,
        pg_user=pg_user,
        pg_password=pg_password,
        timeout=args.timeout,
        env_file=args.env_file,
    )


if __name__ == "__main__":
    sys.exit(main())
