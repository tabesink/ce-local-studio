"""P12-07 U9: bounded graph projection, opaque refs, generation fence, admission."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

import context_engine.services.graphs as graphs
from context_engine.config import Settings
from context_engine.models import DOMAIN_STATE_RUNNING, Domain
from context_engine.services.evidence import EvidenceRetrievalError
from context_engine.services.graphs import (
    GraphServiceError,
    get_domain_graph_snapshot,
    opaque_graph_ref,
    sanitize_graph_label,
    search_domain_graph_labels,
)


@dataclass
class _FixtureGraphClient:
    snapshot: dict[str, Any]
    labels: dict[str, Any] | None = None
    snapshot_calls: int = 0
    label_calls: int = 0

    def graph_snapshot(self, domain: Domain, **_kwargs: object) -> dict[str, Any]:
        self.snapshot_calls += 1
        return self.snapshot

    def graph_label_search(self, domain: Domain, *, q: str, limit: int = 50, **_kwargs: object) -> dict[str, Any]:
        self.label_calls += 1
        assert q
        assert 1 <= limit <= 50
        return self.labels or {"items": []}


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "testing": True,
        "graph_ref_key": "unit-test-graph-ref-key-32bytes!!",
        "graph_timeout_seconds": 2,
        "graph_global_concurrency": 4,
        "graph_per_domain_concurrency": 2,
        "graph_per_principal_concurrency": 1,
    }
    values.update(overrides)
    return Settings(**values)


def _domain(**overrides: object) -> Domain:
    values: dict[str, object] = {
        "id": "domain-graph-001",
        "display_name": "Graph Domain",
        "runtime_instance_id": "runtime-graph-1",
        "embedding_profile_id": "openai-embedding-default",
        "state": DOMAIN_STATE_RUNNING,
        "control_generation": 1,
        "graph_desired_generation": 1,
        "graph_applied_generation": 1,
    }
    values.update(overrides)
    return Domain(**values)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _clean_admission_gates() -> None:
    graphs.reset_graph_admission_for_tests()
    yield
    graphs.reset_graph_admission_for_tests()


def test_sanitize_graph_label_rejects_control_and_unsafe_chars() -> None:
    assert sanitize_graph_label("Relief valve") == "Relief valve"
    assert sanitize_graph_label("  Entity-A  ") == "Entity-A"
    assert sanitize_graph_label("bad\x00label") is None
    assert sanitize_graph_label("<script>") is None
    assert sanitize_graph_label("") is None
    assert sanitize_graph_label(None) is None


def test_opaque_graph_ref_is_stable_purpose_derived_and_domain_scoped() -> None:
    key = "unit-test-graph-ref-key-32bytes!!"
    a = opaque_graph_ref(key=key, domain_id="domain-a", kind="node", private_id="ent-1")
    b = opaque_graph_ref(key=key, domain_id="domain-a", kind="node", private_id="ent-1")
    c = opaque_graph_ref(key=key, domain_id="domain-b", kind="node", private_id="ent-1")
    d = opaque_graph_ref(key=key, domain_id="domain-a", kind="edge", private_id="ent-1")
    assert a == b
    assert a.startswith("gn_")
    assert d.startswith("ge_")
    assert a != c
    assert a != d
    assert all(ch.isalnum() or ch in {"_", "-"} for ch in a)


def test_project_snapshot_strips_raw_ids_properties_and_unsafe_labels() -> None:
    domain = _domain()
    projected = graphs._project_snapshot(
        settings=_settings(),
        domain=domain,
        raw={
            "nodes": [
                {
                    "id": "raw-node-1",
                    "label": "Pump A",
                    "kind": "equipment",
                    "degree": 2,
                    "properties": {"path": "/secret", "prompt": "PRIVATE"},
                },
                {"id": "raw-node-2", "label": "<bad>", "kind": "x", "degree": 1},
                {"id": "raw-node-3", "label": "Valve B", "kind": "bad\x00", "degree": -3},
            ],
            "edges": [
                {
                    "id": "raw-edge-1",
                    "source": "raw-node-1",
                    "target": "raw-node-3",
                    "label": "feeds",
                    "properties": {"weight": 9},
                },
                {"id": "raw-edge-2", "source": "raw-node-1", "target": "raw-node-2", "label": "x"},
            ],
            "truncated": False,
        },
    )
    assert projected["domain"] == {"ref": "domain-graph-001", "name": "Graph Domain"}
    assert len(projected["nodes"]) == 2
    assert all("id" not in node and "properties" not in node for node in projected["nodes"])
    assert projected["nodes"][1]["kind"] is None
    assert projected["nodes"][1]["degree"] == 0
    assert len(projected["edges"]) == 1
    assert "id" not in projected["edges"][0]
    assert projected["edges"][0]["sourceRef"].startswith("gn_")
    assert projected["edges"][0]["targetRef"].startswith("gn_")


def test_snapshot_generation_fence_before_runtime_call(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain(graph_desired_generation=2, graph_applied_generation=1)
    client = _FixtureGraphClient(snapshot={"nodes": [], "edges": []})
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )
    db = MagicMock()
    with pytest.raises(GraphServiceError) as failure:
        get_domain_graph_snapshot(
            db,
            settings=_settings(),
            domain_id=domain.id,
            principal_id="user-1",
            client=client,
        )
    assert failure.value.code == "graph_refreshing"
    assert client.snapshot_calls == 0


def test_snapshot_generation_fence_after_runtime_call(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain(graph_desired_generation=1, graph_applied_generation=1)
    client = _FixtureGraphClient(
        snapshot={
            "nodes": [{"id": "n1", "label": "Pump", "kind": "equipment", "degree": 1}],
            "edges": [],
            "appliedGeneration": 1,
        }
    )
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )

    def reauth(*_a, **_k):
        raise GraphServiceError(409, "graph_refreshing", "The knowledge graph is refreshing after a corpus change.")

    monkeypatch.setattr(graphs, "_reauthorize_after_call", reauth)
    db = MagicMock()
    with pytest.raises(GraphServiceError) as failure:
        get_domain_graph_snapshot(
            db,
            settings=_settings(),
            domain_id=domain.id,
            principal_id="user-1",
            client=client,
        )
    assert failure.value.code == "graph_refreshing"
    assert client.snapshot_calls == 1


def test_snapshot_success_projects_closed_dto_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain()
    client = _FixtureGraphClient(
        snapshot={
            "nodes": [
                {"id": "n1", "label": "Pump", "kind": "equipment", "degree": 1},
                {"id": "n2", "label": "Valve", "kind": "equipment", "degree": 1},
            ],
            "edges": [{"id": "e1", "source": "n1", "target": "n2", "label": "feeds"}],
            "appliedGeneration": 1,
        }
    )
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )
    monkeypatch.setattr(graphs, "_reauthorize_after_call", lambda *_a, **_k: domain)
    db = MagicMock()
    result = get_domain_graph_snapshot(
        db,
        settings=_settings(),
        domain_id=domain.id,
        principal_id="user-1",
        client=client,
    )
    assert result["truncated"] is False
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
    assert result["nodes"][0]["ref"].startswith("gn_")


def test_label_search_validation_and_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain()
    client = _FixtureGraphClient(
        snapshot={"nodes": [], "edges": []},
        labels={"items": [{"id": "n1", "label": "Pump", "kind": "equipment"}]},
    )
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )
    monkeypatch.setattr(graphs, "_reauthorize_after_call", lambda *_a, **_k: domain)
    db = MagicMock()
    with pytest.raises(GraphServiceError) as short_q:
        search_domain_graph_labels(
            db,
            settings=_settings(),
            domain_id=domain.id,
            principal_id="user-1",
            q="a",
            client=client,
        )
    assert short_q.value.code == "validation_error"

    result = search_domain_graph_labels(
        db,
        settings=_settings(),
        domain_id=domain.id,
        principal_id="user-1",
        q="pu",
        limit=10,
        client=client,
    )
    assert result == {
        "items": [
            {
                "nodeRef": opaque_graph_ref(
                    key="unit-test-graph-ref-key-32bytes!!",
                    domain_id=domain.id,
                    kind="node",
                    private_id="n1",
                ),
                "label": "Pump",
                "kind": "equipment",
            }
        ]
    }


def test_map_unknown_domain_to_identical_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (_ for _ in ()).throw(
            EvidenceRetrievalError(404, "domain_not_found", "Domain not found.")
        ),
    )
    db = MagicMock()
    with pytest.raises(GraphServiceError) as failure:
        get_domain_graph_snapshot(
            db,
            settings=_settings(),
            domain_id="missing",
            principal_id="user-1",
            client=_FixtureGraphClient({}),
        )
    assert failure.value.status_code == 404
    assert failure.value.code == "not_found"


def test_per_principal_admission_returns_429_before_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain()
    entered = threading.Event()
    release = threading.Event()

    class BlockingClient(_FixtureGraphClient):
        def graph_snapshot(self, domain: Domain, **_kwargs: object) -> dict[str, Any]:
            self.snapshot_calls += 1
            entered.set()
            release.wait(timeout=2)
            return {"nodes": [], "edges": [], "appliedGeneration": 1}

    client = BlockingClient(snapshot={})
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )
    monkeypatch.setattr(graphs, "_reauthorize_after_call", lambda *_a, **_k: domain)
    settings = _settings(graph_per_principal_concurrency=1, graph_per_domain_concurrency=4)
    db = MagicMock()

    first = threading.Thread(
        target=lambda: get_domain_graph_snapshot(
            db,
            settings=settings,
            domain_id=domain.id,
            principal_id="user-1",
            client=client,
        )
    )
    first.start()
    assert entered.wait(timeout=2)

    with pytest.raises(GraphServiceError) as failure:
        get_domain_graph_snapshot(
            db,
            settings=settings,
            domain_id=domain.id,
            principal_id="user-1",
            client=client,
        )
    assert failure.value.status_code == 429
    assert failure.value.code == "rate_limited"
    assert failure.value.retry_after == 1
    assert client.snapshot_calls == 1

    release.set()
    first.join(timeout=2)


def test_global_admission_returns_503_before_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    domain = _domain()
    entered = threading.Event()
    release = threading.Event()

    class BlockingClient(_FixtureGraphClient):
        def graph_snapshot(self, domain: Domain, **_kwargs: object) -> dict[str, Any]:
            self.snapshot_calls += 1
            entered.set()
            release.wait(timeout=2)
            return {"nodes": [], "edges": [], "appliedGeneration": 1}

    client = BlockingClient(snapshot={})
    monkeypatch.setattr(
        graphs,
        "resolve_available_domain",
        lambda *_a, **_k: (domain, MagicMock()),
    )
    monkeypatch.setattr(graphs, "_reauthorize_after_call", lambda *_a, **_k: domain)
    settings = _settings(
        graph_per_principal_concurrency=4,
        graph_per_domain_concurrency=4,
        graph_global_concurrency=1,
    )
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
    first.start()
    assert entered.wait(timeout=2)

    with pytest.raises(GraphServiceError) as failure:
        get_domain_graph_snapshot(
            db,
            settings=settings,
            domain_id=domain.id,
            principal_id="user-b",
            client=client,
        )
    assert failure.value.status_code == 503
    assert failure.value.code == "capacity_unavailable"
    assert client.snapshot_calls == 1

    release.set()
    first.join(timeout=2)


def test_projection_truncates_to_server_owned_caps() -> None:
    domain = _domain()
    nodes = [{"id": f"n{i}", "label": f"Node {i}", "kind": "equipment", "degree": 0} for i in range(520)]
    edges = [
        {"id": f"e{i}", "source": f"n{i}", "target": f"n{(i + 1) % 520}", "label": "link"}
        for i in range(2100)
    ]
    projected = graphs._project_snapshot(
        settings=_settings(),
        domain=domain,
        raw={"nodes": nodes, "edges": edges, "truncated": False},
    )
    assert projected["truncated"] is True
    assert len(projected["nodes"]) == 500
    assert len(projected["edges"]) <= 2000


def test_oversized_upstream_payload_is_dependency_unavailable() -> None:
    domain = _domain()
    with pytest.raises(GraphServiceError) as failure:
        graphs._project_snapshot(
            settings=_settings(),
            domain=domain,
            raw={
                "nodes": [{"id": "n1", "label": "Pump", "kind": "equipment", "blob": "Z" * (2 * 1024 * 1024)}],
                "edges": [],
            },
        )
    assert failure.value.code == "dependency_unavailable"
