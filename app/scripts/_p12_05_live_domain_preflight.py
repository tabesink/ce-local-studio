#!/usr/bin/env python3
"""One-shot P12-05 operator preflight: seal OpenAI, create/start domain, index a fixture.

Prints only the public domain id and safe status lines. Never prints credentials.
Not part of default verify. Delete or leave as operator helper.
"""

from __future__ import annotations

import http.cookiejar
import json
import mimetypes
import ssl
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

DOMAIN_ID = "p12-05-sse-live"
EMBED_PROFILE = "openai-embedding-default"
SYNTH_PROFILE = "openai-synthesis-default"
FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/documents/doc_safety_bulletin.pdf"


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _cookie(jar: http.cookiejar.CookieJar, name: str) -> str | None:
    for cookie in jar:
        if cookie.name == name:
            return cookie.value
    return None


class Client:
    def __init__(self, base: str, ca_file: Path) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=str(ca_file))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.HTTPCookieProcessor(self.jar),
        )

    def json(
        self,
        method: str,
        path: str,
        *,
        origin: str,
        csrf: str | None = None,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict | list | None, dict[str, str]]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        hdrs = {"Accept": "application/json", "Origin": origin}
        if body is not None:
            hdrs["Content-Type"] = "application/json"
        if csrf is not None:
            hdrs["X-CSRF-Token"] = csrf
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(f"{self.base}{path}", data=data, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=120) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode("utf-8")) if raw else None
                return resp.status, parsed, {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else None
            except json.JSONDecodeError:
                parsed = {"raw": raw.decode("utf-8", errors="replace")[:300]}
            return exc.code, parsed, {k.lower(): v for k, v in exc.headers.items()}

    def multipart(
        self,
        path: str,
        *,
        origin: str,
        csrf: str,
        file_path: Path,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict | None]:
        boundary = f"----ce{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/pdf"
        file_bytes = file_path.read_bytes()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
        hdrs = {
            "Accept": "application/json",
            "Origin": origin,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-CSRF-Token": csrf,
        }
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(f"{self.base}{path}", data=body, headers=hdrs, method="POST")
        try:
            with self.opener.open(req, timeout=180) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, {"raw": raw[:400]}


def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env.stack.local"
    env = _load_env(env_path)
    origin = env["CE_STACK_PUBLIC_ORIGIN"].rstrip("/")
    ca = Path(env["CE_STACK_TLS_CERT_DIR"]) / "cert.pem"
    openai_key = env.get("OPENAI_API_KEY") or env.get("CE_OPENAI_API_KEY")
    if not openai_key:
        print("FAIL: OPENAI_API_KEY missing", file=sys.stderr)
        return 1
    if not FIXTURE.is_file():
        print(f"FAIL: fixture missing {FIXTURE}", file=sys.stderr)
        return 1

    client = Client(origin, ca)
    st, body, _ = client.json("GET", "/api/v1/auth/csrf", origin=origin)
    if st != 200 or not isinstance(body, dict):
        print(f"FAIL: csrf {st}", file=sys.stderr)
        return 1
    pre = body["csrfToken"]
    st, _, _ = client.json(
        "POST",
        "/api/v1/auth/login",
        origin=origin,
        csrf=pre,
        body={"username": env["CE_ADMIN_USERNAME"], "password": env["CE_ADMIN_PASSWORD"]},
    )
    if st != 200:
        print(f"FAIL: login {st}", file=sys.stderr)
        return 1
    csrf = _cookie(client.jar, "ce_csrf")
    if not csrf:
        print("FAIL: missing ce_csrf", file=sys.stderr)
        return 1

    st, snap, _ = client.json("GET", "/api/v1/admin/runtime-settings", origin=origin)
    if st != 200 or not isinstance(snap, dict):
        print(f"FAIL: runtime-settings {st}", file=sys.stderr)
        return 1
    openai = next(p for p in snap["providers"] if p["kind"] == "openai")
    if not openai.get("configured"):
        st, body, _ = client.json(
            "PUT",
            "/api/v1/admin/runtime-settings/providers/openai",
            origin=origin,
            csrf=csrf,
            body={"credential": openai_key},
            headers={"If-Match": f'"{openai["version"]}"'},
        )
        if st != 200:
            print(f"FAIL: seal openai {st} {body}", file=sys.stderr)
            return 1
        print("OK: sealed OpenAI provider credential (value never printed)")
    else:
        print("OK: OpenAI provider already configured")

    st, snap, _ = client.json("GET", "/api/v1/admin/runtime-settings", origin=origin)
    assert isinstance(snap, dict)
    rs = snap["runtimeSettings"]
    if rs.get("activeSynthesisProfileId") != SYNTH_PROFILE:
        st, body, _ = client.json(
            "PATCH",
            "/api/v1/admin/runtime-settings",
            origin=origin,
            csrf=csrf,
            body={"activeSynthesisProfileId": SYNTH_PROFILE},
            headers={"If-Match": f'"{rs["version"]}"'},
        )
        if st != 200:
            print(f"FAIL: activate synthesis {st} {body}", file=sys.stderr)
            return 1
        print(f"OK: active synthesis -> {SYNTH_PROFILE}")
    else:
        print(f"OK: active synthesis already {SYNTH_PROFILE}")

    st, listing, _ = client.json("GET", "/api/v1/admin/domains", origin=origin)
    assert isinstance(listing, dict)
    existing = next((d for d in listing.get("domains", []) if d.get("id") == DOMAIN_ID), None)
    if existing is None:
        st, body, _ = client.json(
            "POST",
            "/api/v1/admin/domains",
            origin=origin,
            csrf=csrf,
            body={
                "id": DOMAIN_ID,
                "displayName": "P12-05 SSE Live Domain",
                "embeddingProfileId": EMBED_PROFILE,
                "graphExtractionProfileId": SYNTH_PROFILE,
            },
            headers={"Idempotency-Key": f"p12-05-domain-{DOMAIN_ID}"},
        )
        if st != 201:
            print(f"FAIL: create domain {st} {body}", file=sys.stderr)
            return 1
        print(f"OK: created domain {DOMAIN_ID}")
    else:
        print(f"OK: domain {DOMAIN_ID} already exists state={existing.get('state')}")

    # Start if not running
    st, status_body, _ = client.json(
        "GET", f"/api/v1/admin/domains/{DOMAIN_ID}/status", origin=origin
    )
    if st != 200 or not isinstance(status_body, dict):
        print(f"FAIL: domain status {st}", file=sys.stderr)
        return 1
    domain = status_body["domain"]
    if domain.get("state") != "running":
        st, body, _ = client.json(
            "POST",
            f"/api/v1/admin/domains/{DOMAIN_ID}/start",
            origin=origin,
            csrf=csrf,
            body={},
            headers={"Idempotency-Key": f"p12-05-start-{DOMAIN_ID}-{uuid.uuid4().hex[:8]}"},
        )
        if st not in {202, 200}:
            print(f"FAIL: start domain {st} {body}", file=sys.stderr)
            return 1
        print("OK: start accepted; waiting for running…")
        deadline = time.time() + 300
        while time.time() < deadline:
            st, status_body, _ = client.json(
                "GET", f"/api/v1/admin/domains/{DOMAIN_ID}/status", origin=origin
            )
            if st == 200 and isinstance(status_body, dict):
                state = status_body["domain"].get("state")
                op = status_body.get("activeOperation") or {}
                print(f"  state={state} op={op.get('status')} kind={op.get('kind')}")
                if state == "running":
                    break
            time.sleep(3)
        else:
            print("FAIL: domain did not reach running", file=sys.stderr)
            return 1
    else:
        print("OK: domain already running")

    # Upload + index if no ready source
    st, sources, _ = client.json(
        "GET", f"/api/v1/admin/domains/{DOMAIN_ID}/sources", origin=origin
    )
    if st != 200 or not isinstance(sources, dict):
        print(f"FAIL: list sources {st}", file=sys.stderr)
        return 1
    ready = [
        s
        for s in sources.get("sources", [])
        if s.get("state") == "prepared" and s.get("indexState") == "ready"
    ]
    if not ready:
        existing = sources.get("sources") or []
        source_id = None
        need_prepare_wait = True
        if existing:
            source_id = existing[0]["id"]
            state = existing[0].get("state")
            if state == "prepared":
                print(f"OK: using prepared source id={source_id} (index not ready yet)")
                need_prepare_wait = False
            elif state == "pending":
                st, body, _ = client.json(
                    "POST",
                    f"/api/v1/admin/domains/{DOMAIN_ID}/sources/{source_id}/retry",
                    origin=origin,
                    csrf=csrf,
                    body={},
                    headers={"Idempotency-Key": f"p12-05-prep-retry-{source_id}-{uuid.uuid4().hex[:8]}"},
                )
                if st not in {200, 202}:
                    print(f"FAIL: prepare retry {st} {body}", file=sys.stderr)
                    return 1
                print(f"OK: retried preparation for source id={source_id}")
            else:
                print(f"FAIL: source state={state} not usable for preflight", file=sys.stderr)
                return 1
        else:
            st, body = client.multipart(
                f"/api/v1/admin/domains/{DOMAIN_ID}/sources",
                origin=origin,
                csrf=csrf,
                file_path=FIXTURE,
                headers={"Idempotency-Key": f"p12-05-upload-{DOMAIN_ID}-{uuid.uuid4().hex[:8]}"},
            )
            if st != 201:
                print(f"FAIL: upload {st} {body}", file=sys.stderr)
                return 1
            assert isinstance(body, dict)
            source_id = body["source"]["id"]
            print(f"OK: uploaded source id={source_id} (public ref only logged if present)")

        if need_prepare_wait:
            deadline = time.time() + 300
            while time.time() < deadline:
                st, detail, _ = client.json(
                    "GET",
                    f"/api/v1/admin/domains/{DOMAIN_ID}/sources/{source_id}",
                    origin=origin,
                )
                if st == 200 and isinstance(detail, dict):
                    src = detail["source"]
                    print(f"  prepare state={src.get('state')} index={src.get('indexState')}")
                    if src.get("state") == "prepared":
                        break
                st_ops, ops_body, _ = client.json(
                    "GET",
                    f"/api/v1/admin/domains/{DOMAIN_ID}/sources/{source_id}/operations",
                    origin=origin,
                )
                if st_ops == 200 and isinstance(ops_body, dict):
                    latest_prep = next(
                        (
                            op
                            for op in (ops_body.get("operations") or [])
                            if op.get("operationType") == "prepare"
                        ),
                        None,
                    )
                    if latest_prep and latest_prep.get("status") == "failed":
                        err = latest_prep.get("error") or {}
                        code = err.get("code") or "unknown"
                        print(
                            f"FAIL: preparation failed code={code} "
                            f"op={latest_prep.get('operationType')}",
                            file=sys.stderr,
                        )
                        return 1
                time.sleep(3)
            else:
                print("FAIL: source not prepared", file=sys.stderr)
                return 1

        st, body, _ = client.json(
            "POST",
            f"/api/v1/admin/domains/{DOMAIN_ID}/sources/{source_id}/index/retry",
            origin=origin,
            csrf=csrf,
            body={},
            headers={"Idempotency-Key": f"p12-05-index-{source_id}"},
        )
        if st not in {202, 200}:
            print(f"FAIL: index retry {st} {body}", file=sys.stderr)
            return 1
        print("OK: index retry accepted; waiting for ready…")
        deadline = time.time() + 600
        while time.time() < deadline:
            st, detail, _ = client.json(
                "GET",
                f"/api/v1/admin/domains/{DOMAIN_ID}/sources/{source_id}",
                origin=origin,
            )
            if st == 200 and isinstance(detail, dict):
                src = detail["source"]
                print(f"  index={src.get('indexState')}")
                if src.get("indexState") == "ready":
                    break
                if src.get("indexState") == "failed":
                    print(f"FAIL: index failed {src}", file=sys.stderr)
                    return 1
            time.sleep(5)
        else:
            print("FAIL: index not ready", file=sys.stderr)
            return 1
    else:
        print(f"OK: domain already has {len(ready)} ready source(s)")

    # Member-visible domains list should include it
    st, member_domains, _ = client.json("GET", "/api/v1/domains", origin=origin)
    if st != 200 or not isinstance(member_domains, dict):
        print(f"FAIL: member domains {st}", file=sys.stderr)
        return 1
    ids = [d.get("id") for d in member_domains.get("domains", [])]
    if DOMAIN_ID not in ids:
        print(f"FAIL: domain not query-eligible in GET /domains ({ids})", file=sys.stderr)
        return 1
    print(f"OK: query-eligible domainId={DOMAIN_ID}")
    print(f"DOMAIN_ID={DOMAIN_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
