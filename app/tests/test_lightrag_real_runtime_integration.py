"""P5-04 live-lane proofs for per-domain Docker LightRAG (opt-in).

Default CI / root verify skip this module unless CE_P5_04_LIVE=1.
Requires Docker daemon and CE_DOMAIN_CONTROLLER_IMAGE (default
context-engine-live:local built with CE_STACK_LIVE_IMAGE=1).

P10-05 owns parser/provider semantic end-to-end proof (CE_P10_05_PIPELINE_LIVE /
provider_staging_smoke); this module remains topology credit from handcrafted handoffs.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import pytest

from context_engine.adapters.domain_runtime_controller import (
    CONTROLLER_OUTCOME_SUCCEEDED,
    DockerDomainRuntimeController,
)
from context_engine.adapters.lightrag_http_client import (
    HttpTransportResponse,
    PrivateHttpLightRAGClient,
)
from context_engine.config import Settings
from context_engine.models import (
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.indexing import render_blocks_to_lightrag_handoff

pytestmark = pytest.mark.integration_docker

_LIVE = os.environ.get("CE_P5_04_LIVE", "").strip() == "1"
_IMAGE = os.environ.get("CE_DOMAIN_CONTROLLER_IMAGE", "context-engine-live:local").strip()
_NETWORK = os.environ.get("CE_DOMAIN_CONTROLLER_NETWORK", "ce-domain-runtimes").strip()
_PORT = int(os.environ.get("CE_DOMAIN_LIGHTRAG_PORT", "9621"))


def _require_live() -> None:
    if not _LIVE:
        pytest.skip("Set CE_P5_04_LIVE=1 to run the P5-04 real-runtime lane.")
    probe = subprocess.run(["docker", "image", "inspect", _IMAGE], capture_output=True, check=False)
    if probe.returncode != 0:
        pytest.skip(f"Live image {_IMAGE} missing; build with CE_STACK_LIVE_IMAGE=1.")


class _DockerExecLoopbackTransport:
    """Reach private (no host-publish) runtime via docker exec → 127.0.0.1."""

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float,
    ) -> HttpTransportResponse:
        parsed = urlparse(url)
        runtime_name = parsed.hostname or ""
        if not runtime_name:
            raise AssertionError(f"missing runtime host in {url}")
        loopback = f"http://127.0.0.1:{parsed.port or _PORT}{parsed.path}"
        if parsed.query:
            loopback = f"{loopback}?{parsed.query}"
        body_literal = "None" if json_body is None else repr(json.dumps(json_body))
        script = (
            "import json,urllib.error,urllib.request\n"
            f"data={body_literal}\n"
            "headers={'Accept':'application/json'}\n"
            "if data is not None:\n"
            "    data=data.encode('utf-8'); headers['Content-Type']='application/json'\n"
            f"req=urllib.request.Request({loopback!r}, data=data, headers=headers, method={method!r})\n"
            "try:\n"
            f"    with urllib.request.urlopen(req, timeout={max(1.0, timeout)!r}) as resp:\n"
            "        body=resp.read(); code=int(resp.status)\n"
            "except urllib.error.HTTPError as exc:\n"
            "    body=exc.read() if hasattr(exc,'read') else b''; code=int(exc.code)\n"
            "print(code); print(body.decode('utf-8', errors='replace'))\n"
        )
        result = subprocess.run(
            ["docker", "exec", runtime_name, "python", "-c", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=max(5.0, timeout + 5.0),
        )
        if result.returncode != 0:
            raise TimeoutError(result.stderr or "docker exec transport failed")
        lines = result.stdout.splitlines()
        if not lines:
            raise TimeoutError("empty docker exec transport response")
        status = int(lines[0])
        body = "\n".join(lines[1:]).encode("utf-8")
        return HttpTransportResponse(status_code=status, body=body)


def _controller_command() -> str:
    app_root = Path(__file__).resolve().parents[1]
    python = app_root / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else "python3")
    return f"{exe} -m context_engine.tools.domain_runtime_controller"


def _domain(domain_id: str) -> Domain:
    return Domain(
        id=domain_id,
        display_name=domain_id,
        state=DOMAIN_STATE_RUNNING,
        embedding_profile_id="embed-live",
        runtime_instance_id=uuid4().hex,
        control_generation=1,
        version=1,
    )


def _handoff(*, domain_id: str, marker: str, block_id: str) -> tuple[str, str]:
    source = SourceDocument(
        id=str(uuid4()),
        public_ref=f"ref-{marker}",
        domain_id=domain_id,
        original_filename=f"{marker}.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=10,
        original_object_key=f"obj/{marker}",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
    )
    block = SourceBlock(
        id=block_id,
        source_document_id=source.id,
        domain_id=domain_id,
        source_order=1,
        kind=SOURCE_BLOCK_KIND_TEXT,
        canonical_markdown=f"Unique corpus token {marker} for isolation proof.",
    )
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=[block],
    )
    return rendered.text, hashlib.sha256(rendered.text.encode("utf-8")).hexdigest()


def _wait_healthy(controller: DockerDomainRuntimeController, domain: Domain, *, seconds: float = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        health = controller.health(domain)
        if health.healthy:
            return
        time.sleep(0.5)
    raise AssertionError(f"domain {domain.id} never became healthy")


def _wait_ready(client: PrivateHttpLightRAGClient, domain: Domain, request_id: str, *, seconds: float = 90) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        readiness = client.readiness(domain, request_id=request_id)
        if readiness.ready:
            return
        if readiness.failed:
            raise AssertionError(f"index failed: {readiness.error_code}")
        time.sleep(0.5)
    raise AssertionError(f"index not ready for {request_id}")


def _host_ports(runtime_name: str) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "inspect", runtime_name, "--format", "{{json .NetworkSettings.Ports}}"],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_dual_lane_default_skips_without_live_env() -> None:
    assert os.environ.get("CE_P5_04_LIVE", "").strip() != "1" or _LIVE
    # Always-on: this module is opt-in; root verify must not require CE_P5_04_LIVE.
    verify = Path(__file__).resolve().parents[2] / "scripts" / "verify.sh"
    text = verify.read_text(encoding="utf-8")
    assert "CE_P5_04_LIVE" not in text
    assert "compose.stack.live.yml" not in text


@pytest.fixture
def live_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _require_live()
    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_IMAGE", _IMAGE)
    monkeypatch.setenv("CE_DOMAIN_CONTROLLER_NETWORK", _NETWORK)
    monkeypatch.setenv("CE_DOMAIN_LIGHTRAG_PORT", str(_PORT))
    settings = Settings(
        testing=True,
        domain_runtime_root=str(tmp_path / "runtimes"),
        domain_runtime_controller_kind="docker",
        domain_controller_command=_controller_command(),
        domain_controller_timeout_seconds=60,
        domain_controller_image=_IMAGE,
        domain_controller_network=_NETWORK,
        domain_lightrag_port=_PORT,
        lightrag_client_kind="native",
        lightrag_inprocess_synthetic=False,
        source_index_timeout_seconds=60,
    )
    controller = DockerDomainRuntimeController(settings)
    domains: list[Domain] = []

    def start_domain(domain_id: str) -> Domain:
        domain = _domain(domain_id)
        domains.append(domain)
        assert controller.provision(domain, operation_key=f"p-{domain_id}", control_generation=1).outcome == (
            CONTROLLER_OUTCOME_SUCCEEDED
        )
        assert controller.start(domain, operation_key=f"s-{domain_id}", control_generation=1).outcome == (
            CONTROLLER_OUTCOME_SUCCEEDED
        )
        _wait_healthy(controller, domain)
        ports = _host_ports(controller.runtime_name(domain))
        assert all(not binding for binding in ports.values()), ports
        return domain

    yield settings, controller, start_domain

    for domain in domains:
        controller.delete(domain, operation_key=f"d-{domain.id}", control_generation=domain.control_generation)


def test_submit_ready_retrieve_delete_two_domain_isolation(live_env) -> None:
    settings, controller, start_domain = live_env
    domain_a = start_domain("domain-a")
    domain_b = start_domain("domain-b")
    client = PrivateHttpLightRAGClient(settings, transport=_DockerExecLoopbackTransport())

    marker_a = f"ALPHA-{uuid4().hex[:8]}"
    marker_b = f"BRAVO-{uuid4().hex[:8]}"
    text_a, hash_a = _handoff(domain_id=domain_a.id, marker=marker_a, block_id=f"block-a-{uuid4().hex[:8]}")
    text_b, hash_b = _handoff(domain_id=domain_b.id, marker=marker_b, block_id=f"block-b-{uuid4().hex[:8]}")
    assert "CE_BLOCK schema=2" in text_a and "CE_BLOCK schema=2" in text_b
    req_a = f"req-a-{uuid4().hex[:8]}"
    req_b = f"req-b-{uuid4().hex[:8]}"

    def _index(domain: Domain, request_id: str, content_hash: str, rendered: str) -> None:
        client.submit(domain, request_id=request_id, content_hash=content_hash, rendered_text=rendered)
        _wait_ready(client, domain, request_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_index, domain_a, req_a, hash_a, text_a),
            pool.submit(_index, domain_b, req_b, hash_b, text_b),
        ]
        for future in futures:
            future.result(timeout=120)

    retrieved_a = client.retrieve(domain_a, question=marker_a)
    retrieved_b = client.retrieve(domain_b, question=marker_b)
    joined_a = "\n".join(candidate.text for candidate in retrieved_a.candidates)
    joined_b = "\n".join(candidate.text for candidate in retrieved_b.candidates)
    assert marker_a in joined_a
    assert marker_b in joined_b
    assert marker_b not in joined_a
    assert marker_a not in joined_b
    assert "CE_BLOCK schema=2" in joined_a
    assert "CE_BLOCK schema=2" in joined_b

    client.delete(domain_a, request_id=req_a)
    assert client.is_absent(domain_a, request_id=req_a) is True
    gone = client.retrieve(domain_a, question=marker_a)
    assert marker_a not in "\n".join(candidate.text for candidate in gone.candidates)

    # Warm restart preserves bind-mount state for domain B.
    domain_b.state = DOMAIN_STATE_STOPPED
    assert controller.stop(domain_b, operation_key="stop-b", control_generation=2).outcome == CONTROLLER_OUTCOME_SUCCEEDED
    assert controller.health(domain_b).healthy is False
    domain_b.state = DOMAIN_STATE_RUNNING
    domain_b.control_generation = 3
    assert controller.start(domain_b, operation_key="restart-b", control_generation=3).outcome == (
        CONTROLLER_OUTCOME_SUCCEEDED
    )
    _wait_healthy(controller, domain_b)
    after_restart = client.retrieve(domain_b, question=marker_b)
    assert marker_b in "\n".join(candidate.text for candidate in after_restart.candidates)
