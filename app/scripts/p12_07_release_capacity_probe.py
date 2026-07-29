#!/usr/bin/env python3
"""P12-07 U4 gated @release capacity / budget freeze probe.

Never wired into scripts/verify.sh or the PR Playwright job.

Modes:
  check   — refuse/allow gate + freeze configured budgets to JSON (no stack)
  unit    — in-process graph L/L+1 admission proof (deterministic; no Docker)
  live    — optional HTTP probe against a running stack (requires CE_P12_07_RELEASE_LIVE=1)

Gate: CE_P12_07_RELEASE=1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

GATE_ENV = "CE_P12_07_RELEASE"
LIVE_ENV = "CE_P12_07_RELEASE_LIVE"
CLOSED = frozenset({"gate_refused", "probe_failed", "budget_refused", "live_refused"})


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _fail(code: str, message: str, exit_code: int = 1) -> int:
    if code not in CLOSED:
        code = "probe_failed"
    print(f"FAIL: {code}: {message}", file=sys.stderr)
    return exit_code


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def require_gate() -> str | None:
    if not _truthy(os.environ.get(GATE_ENV)):
        return f"set {GATE_ENV}=1 to allow the P12-07 @release capacity probe"
    return None


def freeze_budgets() -> dict[str, Any]:
    """Capture configured release budgets for the U5 evidence record (not a product API)."""
    return {
        "graphTimeoutSeconds": int(os.environ.get("CE_GRAPH_TIMEOUT_SECONDS", "10")),
        "graphGlobalConcurrency": int(os.environ.get("CE_GRAPH_GLOBAL_CONCURRENCY", "8")),
        "graphPerDomainConcurrency": int(os.environ.get("CE_GRAPH_PER_DOMAIN_CONCURRENCY", "2")),
        "graphPerPrincipalConcurrency": int(os.environ.get("CE_GRAPH_PER_PRINCIPAL_CONCURRENCY", "2")),
        "graphWaitQueueDepth": 0,
        "retrievalTimeoutSeconds": int(os.environ.get("CE_RETRIEVAL_TIMEOUT_SECONDS", "30")),
        "retrievalGlobalConcurrency": int(os.environ.get("CE_RETRIEVAL_GLOBAL_CONCURRENCY", "8")),
        "retrievalPerDomainConcurrency": int(os.environ.get("CE_RETRIEVAL_PER_DOMAIN_CONCURRENCY", "2")),
        "synthesisTimeoutSeconds": int(os.environ.get("CE_SYNTHESIS_TIMEOUT_SECONDS", "60")),
        "turnLeaseSeconds": int(os.environ.get("CE_TURN_LEASE_SECONDS", "180")),
        "workerIdleSeconds": os.environ.get("CE_WORKER_IDLE_SECONDS", "2"),
        "notes": [
            "Budgets are private harness/config evidence for AE5; not a browser metric API.",
            "Zero graph wait-queue depth is contractually fixed by U9 admission.",
        ],
    }


def run_unit_graph_admission() -> dict[str, Any]:
    """Prove principal 429 and global 503 before a second runtime call (L saturated, L+1 shed)."""
    app_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(app_dir))

    import context_engine.services.graphs as graphs
    from context_engine.config import Settings
    from context_engine.models import DOMAIN_STATE_RUNNING, Domain
    from context_engine.services.graphs import GraphServiceError, get_domain_graph_snapshot

    graphs._global_gate = None
    graphs._global_limit = None
    graphs._domain_gates.clear()
    graphs._principal_gates.clear()

    domain = Domain(
        id="domain-release-capacity",
        display_name="Release Capacity",
        runtime_instance_id="runtime-release-1",
        embedding_profile_id="openai-embedding-default",
        state=DOMAIN_STATE_RUNNING,
        control_generation=1,
        graph_desired_generation=1,
        graph_applied_generation=1,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    class BlockingClient:
        def graph_snapshot(self, _domain: Domain, **_kwargs: object) -> dict[str, Any]:
            calls["n"] += 1
            entered.set()
            release.wait(timeout=3)
            return {"nodes": [], "edges": [], "appliedGeneration": 1}

        def graph_label_search(self, _domain: Domain, **_kwargs: object) -> dict[str, Any]:
            return {"items": []}

    client = BlockingClient()
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        testing=True,
        graph_ref_key="release-capacity-graph-ref-key-32b!!",
        graph_timeout_seconds=2,
        graph_global_concurrency=1,
        graph_per_domain_concurrency=4,
        graph_per_principal_concurrency=4,
    )
    graphs.resolve_available_domain = lambda *_a, **_k: (domain, MagicMock())  # type: ignore[assignment]
    graphs._reauthorize_after_call = lambda *_a, **_k: domain  # type: ignore[assignment]
    db = MagicMock()

    first = threading.Thread(
        target=lambda: get_domain_graph_snapshot(
            db,
            settings=settings,
            domain_id=domain.id,
            principal_id="user-a",
            client=client,
        )
    )
    started = time.monotonic()
    first.start()
    assert entered.wait(timeout=2), "first graph call did not enter runtime"

    shed_started = time.monotonic()
    try:
        get_domain_graph_snapshot(
            db,
            settings=settings,
            domain_id=domain.id,
            principal_id="user-b",
            client=client,
        )
        raise AssertionError("expected capacity shed")
    except GraphServiceError as exc:
        shed_ms = (time.monotonic() - shed_started) * 1000
        if exc.status_code != 503 or exc.code != "capacity_unavailable":
            raise AssertionError(f"unexpected shed: {exc.status_code} {exc.code}") from exc
        if shed_ms > 1000:
            raise AssertionError(f"L+1 shed took {shed_ms:.0f}ms (>1000ms)") from exc
        if calls["n"] != 1:
            raise AssertionError(f"runtime invoked {calls['n']} times before shed") from None

    release.set()
    first.join(timeout=3)

    # Post-shed recovery: a new call must succeed after permits return.
    recovery_client_calls = {"n": 0}

    class FastClient:
        def graph_snapshot(self, _domain: Domain, **_kwargs: object) -> dict[str, Any]:
            recovery_client_calls["n"] += 1
            return {
                "nodes": [{"id": "pump", "label": "Pump", "kind": "equipment", "degree": 0}],
                "edges": [],
                "appliedGeneration": 1,
            }

        def graph_label_search(self, _domain: Domain, **_kwargs: object) -> dict[str, Any]:
            return {"items": []}

    recovered = get_domain_graph_snapshot(
        db,
        settings=settings,
        domain_id=domain.id,
        principal_id="user-c",
        client=FastClient(),
    )
    if recovery_client_calls["n"] != 1 or not recovered.get("nodes"):
        raise AssertionError("post-shed recovery probe failed")

    return {
        "mode": "unit",
        "L": 1,
        "Lplus1": {"status": 503, "code": "capacity_unavailable", "shedMs": round(shed_ms, 1)},
        "runtimeCallsDuringShed": calls["n"],
        "recovery": "ok",
        "elapsedMs": round((time.monotonic() - started) * 1000, 1),
        "budgets": freeze_budgets(),
    }


def run_live_http_probe(base_url: str, domain_id: str) -> dict[str, Any]:
    if not _truthy(os.environ.get(LIVE_ENV)):
        raise RuntimeError(f"set {LIVE_ENV}=1 for live HTTP capacity probe")
    try:
        import urllib.error
        import urllib.request
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("urllib unavailable") from exc

    url = f"{base_url.rstrip('/')}/api/v1/domains/{domain_id}/graph"
    # Live probe is intentionally shallow: reachability + closed error envelope only.
    # Full L/L+1 with real cookies requires the Playwright @release suite.
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:  # noqa: S310 — operator-controlled base
            status = response.status
            body = response.read(2048).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read(2048).decode("utf-8", errors="replace")
    if "traceback" in body.lower() or "working_dir" in body.lower():
        raise RuntimeError("live probe response leaked private failure detail")
    return {
        "mode": "live",
        "url": url,
        "status": status,
        "note": "Cookie-authenticated L/L+1 shed is owned by Playwright @release specs.",
        "budgets": freeze_budgets(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P12-07 U4 @release capacity probe")
    parser.add_argument(
        "mode",
        choices=("check", "unit", "live"),
        help="check=gate+budget freeze; unit=in-process L/L+1; live=HTTP smoke",
    )
    parser.add_argument("--base-url", default=os.environ.get("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--domain-id", default=os.environ.get("CE_P12_07_DOMAIN_ID", "e2e"))
    args = parser.parse_args(argv)

    refused = require_gate()
    if refused:
        return _fail("gate_refused", refused, exit_code=2)

    if args.mode == "check":
        budgets = freeze_budgets()
        if budgets["graphWaitQueueDepth"] != 0:
            return _fail("budget_refused", "graph wait queue depth must be 0")
        return _ok({"mode": "check", "gate": GATE_ENV, "budgets": budgets})

    try:
        if args.mode == "unit":
            return _ok(run_unit_graph_admission())
        return _ok(run_live_http_probe(args.base_url, args.domain_id))
    except Exception as exc:  # noqa: BLE001 — closed probe boundary
        return _fail("probe_failed" if args.mode == "unit" else "live_refused", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
