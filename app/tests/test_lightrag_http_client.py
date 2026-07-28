from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from context_engine.adapters.lightrag_http_client import (
    HttpTransportResponse,
    PrivateHttpLightRAGClient,
)
from context_engine.config import Settings
from context_engine.models import DOMAIN_STATE_RUNNING, Domain
from context_engine.services.indexing import (
    SourceIndexError,
    index_client_from_settings,
    render_blocks_to_lightrag_handoff,
)
from context_engine.models import SOURCE_BLOCK_KIND_TEXT, SourceBlock, SourceDocument, SOURCE_STATE_PREPARED
from context_engine.services.indexing import LightRAGClient


class _ScriptedTransport:
    def __init__(self, responses: list[HttpTransportResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float,
    ) -> HttpTransportResponse:
        self.calls.append((method, url, json_body))
        if not self.responses:
            raise AssertionError("unexpected transport call")
        return self.responses.pop(0)


def _domain(tmp_path: Path) -> Domain:
    domain = Domain(
        id="domain-http",
        display_name="HTTP Domain",
        state=DOMAIN_STATE_RUNNING,
        embedding_profile_id="embed-1",
        runtime_instance_id=str(uuid4()),
        control_generation=1,
        version=1,
    )
    runtime_dir = tmp_path / domain.id / domain.runtime_instance_id
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "endpoint.json").write_text(
        json.dumps({"baseUrl": "http://ce_domain_http_test:9621", "port": 9621, "healthPath": "/health"}),
        encoding="utf-8",
    )
    return domain


def _handoff() -> tuple[str, str]:
    source = SourceDocument(
        id=str(uuid4()),
        public_ref="ref-http",
        domain_id="domain-http",
        original_filename="a.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=10,
        original_object_key="obj/a",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
    )
    block = SourceBlock(
        id="block-1",
        source_document_id=source.id,
        domain_id=source.domain_id,
        source_order=1,
        kind=SOURCE_BLOCK_KIND_TEXT,
        canonical_markdown="Hello evidence",
    )
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=[block],
    )
    return rendered.text, hashlib.sha256(rendered.text.encode("utf-8")).hexdigest()


def test_factory_native_defaults_to_private_http() -> None:
    client = index_client_from_settings(Settings(testing=True, lightrag_client_kind="native"))
    assert isinstance(client, PrivateHttpLightRAGClient)


def test_factory_native_inprocess_synthetic_opt_in() -> None:
    client = index_client_from_settings(
        Settings(testing=True, lightrag_client_kind="native", lightrag_inprocess_synthetic=True)
    )
    assert isinstance(client, LightRAGClient)


def test_http_submit_readiness_delete_round_trip(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    text, content_hash = _handoff()
    request_id = "req-" + uuid4().hex[:8]
    transport = _ScriptedTransport(
        [
            HttpTransportResponse(200, json.dumps({"remote_document_id": f"lightrag:{request_id}"}).encode()),
            HttpTransportResponse(200, json.dumps({"ready": True, "failed": False}).encode()),
            HttpTransportResponse(200, b'{"ok":true}'),
            HttpTransportResponse(200, b'{"absent":true}'),
        ]
    )
    client = PrivateHttpLightRAGClient(
        Settings(testing=True, domain_runtime_root=str(tmp_path), source_index_timeout_seconds=5),
        transport=transport,
        embedding_dimensions=1536,
    )
    submitted = client.submit(domain, request_id=request_id, content_hash=content_hash, rendered_text=text)
    assert submitted.remote_document_id == f"lightrag:{request_id}"
    assert client.readiness(domain, request_id=request_id).ready is True
    client.delete(domain, request_id=request_id)
    assert client.is_absent(domain, request_id=request_id) is True
    assert transport.calls[0][0] == "POST"
    assert transport.calls[0][1].endswith("/v1/index/submit")
    assert "CE_BLOCK schema=2" in (transport.calls[0][2] or {}).get("rendered_text", "")


def test_http_submit_rejects_hash_conflict_without_transport(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    text, _ = _handoff()
    client = PrivateHttpLightRAGClient(
        Settings(testing=True, domain_runtime_root=str(tmp_path)),
        transport=_ScriptedTransport([]),
    )
    with pytest.raises(SourceIndexError) as raised:
        client.submit(domain, request_id="req-1", content_hash="0" * 64, rendered_text=text)
    assert raised.value.code == "source_index_conflict"


def test_http_submit_timeout_maps_safe_code(tmp_path: Path) -> None:
    domain = _domain(tmp_path)
    text, content_hash = _handoff()

    class _TimeoutTransport:
        def request(self, method, url, *, json_body=None, timeout: float):
            raise TimeoutError

    client = PrivateHttpLightRAGClient(
        Settings(testing=True, domain_runtime_root=str(tmp_path), source_index_timeout_seconds=2),
        transport=_TimeoutTransport(),
    )
    with pytest.raises(SourceIndexError) as raised:
        client.submit(domain, request_id="req-timeout", content_hash=content_hash, rendered_text=text)
    assert raised.value.code == "source_index_timeout"
