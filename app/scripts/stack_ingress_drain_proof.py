#!/usr/bin/env python3
"""P12-05 AE3 topology drain proof: drain-hold 503 + stop_claim + reclaim.

Sequence:
1. Authenticate through HTTPS public origin (three-file TLS+live matrix).
2. Create a conversation (accepted work surface for resume/tail).
3. SIGUSR1 api → drain-hold while listen socket still serves.
4. Assert new turns:stream → 503 capacity_unavailable.
5. Assert resume/tail path still reachable (events GET not gated).
6. SIGTERM worker → observe stack_worker.stop_claim; restart api/worker.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from stack_ingress_trust_proof import _HttpsClient, _cookie_value, _load_env_file  # noqa: E402


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def _compose_base(env_file: Path, *, include_live: bool) -> list[str]:
    files = ["-f", "compose.stack.yml"]
    if include_live:
        files.extend(["-f", "compose.stack.live.yml"])
    files.extend(["-f", "compose.stack.tls.yml"])
    return [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        *files,
    ]


def _run_compose(compose_base: list[str], compose_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*compose_base, *args],
        cwd=compose_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.stack.local",
    )
    parser.add_argument(
        "--compose-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Directory containing compose.stack.yml",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--ca-file", type=Path, default=None)
    parser.add_argument(
        "--skip-live-overlay",
        action="store_true",
        help="Use stack+tls only (AE3 capacity half); default includes compose.stack.live.yml",
    )
    parser.add_argument(
        "--skip-compose-stop",
        action="store_true",
        help="Only assert 503 against an api already in drain-hold (no SIGUSR1/SIGTERM)",
    )
    args = parser.parse_args(argv)

    if not args.env_file.is_file():
        return _fail(f"env file not found: {args.env_file}")
    env = _load_env_file(args.env_file)
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
    if ca_file is None:
        return _fail("ca=insecure-local forbidden for AE3 — set CE_STACK_TLS_CERT_DIR/cert.pem or --ca-file")

    client = _HttpsClient(public_origin, timeout=args.timeout, ca_file=ca_file)
    status, body = client.request("GET", "/api/v1/auth/csrf", origin=public_origin)
    if status != 200:
        return _fail(f"csrf HTTP {status}")
    preauth = json.loads(body.decode("utf-8"))["csrfToken"]
    status, _body = client.request(
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
        return _fail("missing csrf")

    status, body = client.request(
        "POST",
        "/api/v1/conversations",
        origin=public_origin,
        csrf=csrf,
        body={"title": "P12-05 drain proof"},
    )
    if status != 201:
        return _fail(f"create conversation HTTP {status}")
    conversation_id = json.loads(body.decode("utf-8"))["conversation"]["id"]
    # Opaque synthetic turn id for resume/tail reachability after drain-hold.
    # A missing turn yields 404 — still proves the events route is not gated by drain-hold.
    probe_turn_id = f"turn_{uuid.uuid4().hex}"

    include_live = not args.skip_live_overlay
    compose_base = _compose_base(args.env_file, include_live=include_live)
    print(
        f"P12-05 drain proof -> {public_origin} "
        f"(ca=yes; live_overlay={include_live})"
    )

    if not args.skip_compose_stop:
        print("Sending SIGUSR1 to api (drain-hold; listen socket stays up)…")
        kill = _run_compose(compose_base, args.compose_dir, "kill", "-s", "SIGUSR1", "api")
        if kill.returncode != 0:
            return _fail(f"compose kill SIGUSR1 api failed: {kill.stderr or kill.stdout}")
        time.sleep(1.5)

    status, body = client.request(
        "POST",
        f"/api/v1/conversations/{conversation_id}/turns:stream",
        origin=public_origin,
        csrf=csrf,
        body={
            "clientRequestId": "p12-05-drain-probe",
            "message": "should be rejected",
            "composerRefTokens": [],
        },
    )
    if status != 503:
        return _fail(f"expected 503 during drain-hold, got {status}")
    try:
        code = json.loads(body.decode("utf-8")).get("error", {}).get("code")
    except json.JSONDecodeError:
        code = None
    if code != "capacity_unavailable":
        return _fail(f"expected capacity_unavailable, got {code!r}")
    print("OK: AE3 new turns rejected with 503 capacity_unavailable")

    # Resume/tail must remain reachable (not gated). Unknown turn → 404 is OK.
    status, _body = client.request(
        "GET",
        f"/api/v1/conversations/{conversation_id}/turns/{probe_turn_id}/events?after=0",
        origin=public_origin,
    )
    if status == 503:
        return _fail("events resume/tail incorrectly gated by drain-hold (got 503)")
    if status not in {200, 404}:
        return _fail(f"events resume/tail unexpected HTTP {status}")
    print(f"OK: AE3 resume/tail path still reachable during drain-hold (HTTP {status})")

    if args.skip_compose_stop:
        return 0

    print("Stopping worker (SIGTERM) for stop_claim…")
    stop_w = _run_compose(compose_base, args.compose_dir, "stop", "-t", "60", "worker")
    if stop_w.returncode != 0:
        return _fail(f"compose stop worker failed: {stop_w.stderr or stop_w.stdout}")

    logs = _run_compose(compose_base, args.compose_dir, "logs", "--no-color", "--tail", "200", "worker")
    if "stack_worker.stop_claim" not in (logs.stdout or ""):
        return _fail(
            "stack_worker.stop_claim not observed in worker logs — AE3 incomplete "
            "(cite P10-03 only as prior credit; this matrix must re-prove it)"
        )
    print("OK: observed stack_worker.stop_claim")

    up = _run_compose(compose_base, args.compose_dir, "up", "-d", "api", "worker")
    if up.returncode != 0:
        return _fail(f"compose up api/worker failed: {up.stderr or up.stdout}")
    print("OK: AE3 drain-hold + stop_claim completed; api/worker restarted for recovery")
    return 0


if __name__ == "__main__":
    sys.exit(main())
