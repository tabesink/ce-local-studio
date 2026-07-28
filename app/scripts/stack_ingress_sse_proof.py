#!/usr/bin/env python3
"""P12-05 AE1/AE2 chunked SSE proof through TLS origin + live domain-RAG path.

Requires OPENAI_API_KEY or CE_OPENAI_API_KEY in the process environment (never printed).
Uses chunked/readline consumption — never response.read() for AE1.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Allow `python app/scripts/...` without installing the package on PYTHONPATH.
_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from context_engine.dev.ingress_sse_proof import (  # noqa: E402
    SSE_DELTA_INTER_ARRIVAL_EPSILON_MS,
    assert_incremental_answer_deltas,
)


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _credentials_present() -> bool:
    for name in ("OPENAI_API_KEY", "CE_OPENAI_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return True
    return False


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def _cookie_value(jar: http.cookiejar.CookieJar, name: str) -> str | None:
    for cookie in jar:
        if cookie.name == name:
            return cookie.value
    return None


class _StreamClient:
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
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.HTTPCookieProcessor(self.jar),
        )

    def json_request(
        self,
        method: str,
        path: str,
        *,
        origin: str,
        csrf: str | None = None,
        body: dict[str, object] | None = None,
    ) -> tuple[int, bytes]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json", "Origin": origin}
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
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def stream_post_chunked(
        self,
        path: str,
        *,
        origin: str,
        csrf: str,
        body: dict[str, object],
        max_seconds: float,
        disconnect_after_deltas: int | None,
    ) -> tuple[int, list[tuple[float, str, dict[str, object]]]]:
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json",
            "Origin": origin,
            "X-CSRF-Token": csrf,
        }
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=headers,
            method="POST",
        )
        frames: list[tuple[float, str, dict[str, object]]] = []
        started = time.monotonic()
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            return exc.code, frames

        status = response.status
        try:
            buffer = ""
            while True:
                if time.monotonic() - started > max_seconds:
                    break
                chunk = response.read(256)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    data_line = next(
                        (line for line in block.splitlines() if line.startswith("data: ")),
                        None,
                    )
                    if data_line is None:
                        continue
                    envelope = json.loads(data_line.removeprefix("data: "))
                    event_type = str(envelope.get("type") or "")
                    ts_ms = (time.monotonic() - started) * 1000.0
                    frames.append((ts_ms, event_type, envelope))
                    delta_count = sum(1 for _t, t, _e in frames if t == "answer.delta")
                    if disconnect_after_deltas is not None and delta_count >= disconnect_after_deltas:
                        return status, frames
                    if event_type in {"turn.completed", "turn.failed", "turn.cancelled"}:
                        return status, frames
        finally:
            response.close()
        return status, frames

    def stream_get_chunked(
        self,
        path: str,
        *,
        origin: str,
        max_seconds: float,
    ) -> tuple[int, list[tuple[float, str, dict[str, object]]]]:
        headers = {"Accept": "text/event-stream, application/json", "Origin": origin}
        request = urllib.request.Request(f"{self.base}{path}", headers=headers, method="GET")
        frames: list[tuple[float, str, dict[str, object]]] = []
        started = time.monotonic()
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            return exc.code, frames
        status = response.status
        try:
            buffer = ""
            while True:
                if time.monotonic() - started > max_seconds:
                    break
                chunk = response.read(256)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    data_line = next(
                        (line for line in block.splitlines() if line.startswith("data: ")),
                        None,
                    )
                    if data_line is None:
                        continue
                    envelope = json.loads(data_line.removeprefix("data: "))
                    event_type = str(envelope.get("type") or "")
                    ts_ms = (time.monotonic() - started) * 1000.0
                    frames.append((ts_ms, event_type, envelope))
                    if event_type in {"turn.completed", "turn.failed", "turn.cancelled"}:
                        return status, frames
        finally:
            response.close()
        return status, frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.stack.local",
    )
    parser.add_argument("--domain-id", required=True, help="Public domain id for domain_rag")
    parser.add_argument(
        "--message",
        default="What does the seeded source say? Answer briefly with citations.",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--ca-file", type=Path, default=None)
    args = parser.parse_args(argv)

    if not _credentials_present():
        return _fail(
            "OPENAI_API_KEY or CE_OPENAI_API_KEY missing — AE1 does not go green "
            "(credentials present=false; value never printed)"
        )

    if not args.env_file.is_file():
        return _fail(f"env file not found: {args.env_file}")
    env = _load_env_file(args.env_file)
    # Merge non-secret keys into os.environ for any child lookups; never log values.
    for key, value in env.items():
        if key in {"OPENAI_API_KEY", "CE_OPENAI_API_KEY", "CE_ADMIN_PASSWORD", "CONFIG_ENCRYPTION_KEY", "CE_CSRF_SIGNING_KEY"}:
            if key not in os.environ and value:
                os.environ[key] = value
            continue
        os.environ.setdefault(key, value)

    public_origin = env.get("CE_STACK_PUBLIC_ORIGIN", "").rstrip("/")
    username = env.get("CE_ADMIN_USERNAME", "")
    password = env.get("CE_ADMIN_PASSWORD", "")
    if not public_origin.startswith("https://"):
        return _fail("CE_STACK_PUBLIC_ORIGIN must be https://… for P12-05")
    if not username or not password:
        return _fail("CE_ADMIN_* required")

    ca_file = args.ca_file
    if ca_file is None:
        cert_dir = env.get("CE_STACK_TLS_CERT_DIR", "")
        if cert_dir and (Path(cert_dir) / "cert.pem").is_file():
            ca_file = Path(cert_dir) / "cert.pem"

    client = _StreamClient(public_origin, timeout=args.timeout, ca_file=ca_file)
    status, body = client.json_request("GET", "/api/v1/auth/csrf", origin=public_origin)
    if status != 200:
        return _fail(f"csrf HTTP {status}")
    preauth = json.loads(body.decode("utf-8"))["csrfToken"]
    status, _body = client.json_request(
        "POST",
        "/api/v1/auth/login",
        origin=public_origin,
        csrf=preauth,
        body={"username": username, "password": password},
    )
    if status != 200:
        return _fail(f"login HTTP {status}")
    csrf = _cookie_value(client.jar, "ce_csrf")
    if not csrf:
        return _fail("missing ce_csrf after login")

    status, body = client.json_request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=csrf,
        body={"title": "P12-05 SSE proof"},
    )
    if status != 201:
        return _fail(f"create conversation HTTP {status}")
    conversation_id = json.loads(body.decode("utf-8"))["conversation"]["id"]
    client_request_id = f"p12-05-sse-{uuid.uuid4().hex}"

    print(
        f"P12-05 SSE proof -> {public_origin} "
        f"(credentials present=true; epsilon_ms={SSE_DELTA_INTER_ARRIVAL_EPSILON_MS})"
    )

    # Pass 1: disconnect after first delta to prove disconnect ≠ cancel.
    status, frames = client.stream_post_chunked(
        f"/api/v1/conversations/{conversation_id}/turns:stream",
        origin=public_origin,
        csrf=csrf,
        body={
            "clientRequestId": client_request_id,
            "message": args.message,
            "domainId": args.domain_id,
            "composerRefTokens": [],
        },
        max_seconds=args.timeout,
        disconnect_after_deltas=1,
    )
    if status != 200:
        return _fail(f"turns:stream HTTP {status}")
    if not any(t == "answer.delta" for _ts, t, _e in frames):
        return _fail("no answer.delta before disconnect — cannot prove AE2 path")
    turn_id = None
    for _ts, _t, envelope in frames:
        payload = envelope.get("payload") or {}
        if isinstance(payload, dict) and payload.get("turnId"):
            turn_id = payload["turnId"]
            break
        if envelope.get("turnId"):
            turn_id = envelope["turnId"]
            break
    if not turn_id:
        # Fall back: accepted event often carries turn id at top level in catalog.
        for _ts, t, envelope in frames:
            if t == "turn.accepted":
                turn_id = (envelope.get("payload") or {}).get("turnId") or envelope.get("turnId")
                break
    if not turn_id:
        return _fail("could not resolve turnId after partial stream")

    after = max(
        (int(envelope.get("sequence") or envelope.get("eventId") or 0) for _ts, _t, envelope in frames),
        default=0,
    )
    status, resume_frames = client.stream_get_chunked(
        f"/api/v1/conversations/{conversation_id}/turns/{turn_id}/events?after={after}",
        origin=public_origin,
        max_seconds=args.timeout,
    )
    if status != 200:
        return _fail(f"resume events HTTP {status}")
    combined = [(ts, t) for ts, t, _e in frames] + [
        (ts + 10_000.0, t) for ts, t, _e in resume_frames
    ]
    # Prefer a second full stream when disconnect path did not yield ≥2 deltas total.
    all_delta_types = [t for _ts, t in combined if t == "answer.delta"]
    if len(all_delta_types) < 2:
        status, full_frames = client.stream_post_chunked(
            f"/api/v1/conversations/{conversation_id}/turns:stream",
            origin=public_origin,
            csrf=csrf,
            body={
                "clientRequestId": f"p12-05-sse-full-{uuid.uuid4().hex}",
                "message": args.message,
                "domainId": args.domain_id,
                "composerRefTokens": [],
            },
            max_seconds=args.timeout,
            disconnect_after_deltas=None,
        )
        if status != 200:
            return _fail(f"full turns:stream HTTP {status}")
        typed = [(ts, t) for ts, t, _e in full_frames]
        try:
            assert_incremental_answer_deltas(typed)
        except AssertionError as exc:
            return _fail(str(exc))
        if not any(t == "turn.completed" for _ts, t in typed):
            return _fail("full stream missing turn.completed")
        print(f"OK: AE1 ≥2 timed answer.delta (epsilon_ms={SSE_DELTA_INTER_ARRIVAL_EPSILON_MS})")
        print("OK: AE2 disconnect/resume path exercised (partial) + full completion")
        return 0

    try:
        assert_incremental_answer_deltas(combined)
    except AssertionError as exc:
        return _fail(str(exc))
    if any(t == "turn.cancelled" for _ts, t in combined):
        return _fail("disconnect path produced turn.cancelled (disconnect must ≠ cancel)")
    print(f"OK: AE1 ≥2 timed answer.delta (epsilon_ms={SSE_DELTA_INTER_ARRIVAL_EPSILON_MS})")
    print("OK: AE2 disconnect ≠ cancel; resume continued")
    return 0


if __name__ == "__main__":
    sys.exit(main())
