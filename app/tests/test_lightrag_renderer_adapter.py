from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from context_engine.config import Settings
from context_engine.models import (
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.evidence import parse_ce_block_marker
from context_engine.services.indexing import (
    LIGHTRAG_HANDOFF_SCHEMA_VERSION,
    LightRAGClient,
    LocalLightRAGIndexClient,
    SourceIndexError,
    _rendered_block_ids,
    render_blocks_to_lightrag_handoff,
    render_lightrag_input,
)


@dataclass
class _HealthyController:
    root: Path

    def runtime_dir(self, domain_id: str, runtime_instance_id: str) -> Path:
        return self.root / domain_id / runtime_instance_id

    def health(self, _domain: Domain):
        return type("Health", (), {"healthy": True})()


class _BlockSession:
    def __init__(self, blocks: list[SourceBlock]) -> None:
        self._blocks = blocks

    def scalars(self, _statement):  # noqa: ANN001
        return self._blocks


def _prepared_source(*, source_id: str | None = None) -> SourceDocument:
    return SourceDocument(
        id=source_id or str(uuid4()),
        public_ref=f"ref-{uuid4().hex[:12]}",
        domain_id="domain-index",
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=128,
        original_object_key=f"obj/{uuid4().hex}",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=1,
    )


def _block(source_id: str, domain_id: str, *, order: int, body: str, block_id: str | None = None) -> SourceBlock:
    return SourceBlock(
        id=block_id or str(uuid4()),
        source_document_id=source_id,
        domain_id=domain_id,
        source_order=order,
        kind=SOURCE_BLOCK_KIND_TEXT,
        canonical_markdown=body,
    )


def test_renderer_emits_versioned_handoff_with_provenance_markers() -> None:
    source = _prepared_source()
    blocks = [
        _block(source.id, source.domain_id, order=1, body="First block", block_id="block-a"),
        _block(source.id, source.domain_id, order=2, body="Second block", block_id="block-b"),
    ]
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=blocks,
    )
    assert LIGHTRAG_HANDOFF_SCHEMA_VERSION == "2"
    marker_a = (
        f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={source.original_sha256} "
        "block_id=block-a order=1]"
    )
    marker_b = (
        f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={source.original_sha256} "
        "block_id=block-b order=2]"
    )
    assert rendered.text.startswith(
        f"[CE_SOURCE schema=2 source_id={source.id} sha256={source.original_sha256}]\n\n"
        f"{marker_a}\nFirst block"
    )
    assert f"{marker_b}\nSecond block" in rendered.text
    assert rendered.block_ids == ("block-a", "block-b")
    assert _rendered_block_ids(rendered.text) == ["block-a", "block-b"]
    assert rendered.content_hash == __import__("hashlib").sha256(rendered.text.encode("utf-8")).hexdigest()

    via_db = render_lightrag_input(_BlockSession(blocks), source)
    assert via_db == rendered


def test_schema_v2_marker_is_anchored_exact_and_rejects_reserved_body_tokens() -> None:
    sha = "b" * 64
    marker = f"[CE_BLOCK schema=2 source_id=source-1 source_sha256={sha} block_id=block-1 order=2]"

    parsed = parse_ce_block_marker(f"{marker}\nCanonical body")

    assert parsed is not None
    assert parsed.source_id == "source-1"
    assert parsed.source_sha256 == sha
    assert parsed.block_id == "block-1"
    assert parsed.source_order == 2
    assert parse_ce_block_marker("[CE_BLOCK id=block-1 order=2]\nlegacy") is None
    assert parse_ce_block_marker(f"prefix\n{marker}\nbody") is None
    assert parse_ce_block_marker(f"{marker}\nbody [CE_SOURCE schema=2]") is None
    assert parse_ce_block_marker(f"{marker}\nbody\n{marker}") is None


def test_renderer_rejects_empty_duplicate_and_blank_blocks() -> None:
    source = _prepared_source()
    with pytest.raises(SourceIndexError) as empty:
        render_blocks_to_lightrag_handoff(
            source_id=source.id,
            original_sha256=source.original_sha256,
            blocks=[],
        )
    assert empty.value.code == "source_index_input_invalid"

    dup_id = "block-dup"
    with pytest.raises(SourceIndexError) as duplicate:
        render_blocks_to_lightrag_handoff(
            source_id=source.id,
            original_sha256=source.original_sha256,
            blocks=[
                _block(source.id, source.domain_id, order=1, body="A", block_id=dup_id),
                _block(source.id, source.domain_id, order=2, body="B", block_id=dup_id),
            ],
        )
    assert duplicate.value.code == "source_index_input_invalid"

    with pytest.raises(SourceIndexError) as blank:
        render_blocks_to_lightrag_handoff(
            source_id=source.id,
            original_sha256=source.original_sha256,
            blocks=[_block(source.id, source.domain_id, order=1, body="   \n")],
        )
    assert blank.value.code == "source_index_input_invalid"


def test_local_adapter_idempotent_submit_readiness_delete_and_provenance(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        testing=True,
        domain_runtime_root=str(tmp_path / "runtimes"),
        lightrag_client_kind="local",
    )
    controller = _HealthyController(tmp_path / "runtimes")
    client = LocalLightRAGIndexClient(settings, controller)
    domain = Domain(
        id="domain-index",
        display_name="Index",
        runtime_instance_id="runtime-1",
        embedding_profile_id="openai-embedding-default",
        state="running",
    )
    source = _prepared_source()
    blocks = [_block(source.id, source.domain_id, order=1, body="Indexed body", block_id="block-1")]
    rendered = render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=blocks,
    )
    request_id = f"{source.id}-1-{rendered.content_hash[:16]}"

    first = client.submit(
        domain,
        request_id=request_id,
        content_hash=rendered.content_hash,
        rendered_text=rendered.text,
    )
    second = client.submit(
        domain,
        request_id=request_id,
        content_hash=rendered.content_hash,
        rendered_text=rendered.text,
    )
    assert first.remote_document_id == second.remote_document_id
    assert client.readiness(domain, request_id=request_id).ready is True
    assert client.preserved_block_ids(domain, request_id=request_id) == ("block-1",)
    retrieved = client.retrieve(domain, question="Where is the indexed body?", deadline=None)
    assert len(retrieved.candidates) == 1
    preserved = parse_ce_block_marker(retrieved.candidates[0].text)
    assert preserved is not None
    assert preserved.source_id == source.id
    assert preserved.source_sha256 == source.original_sha256
    assert preserved.block_id == "block-1"

    with pytest.raises(SourceIndexError) as conflict:
        client.submit(
            domain,
            request_id=request_id,
            content_hash="0" * 64,
            rendered_text=rendered.text,
        )
    assert conflict.value.code == "source_index_conflict"

    client.delete(domain, request_id=request_id)
    assert client.is_absent(domain, request_id=request_id) is True
    assert client.readiness(domain, request_id=request_id).failed is True


def test_native_adapter_timeout_fails_closed() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        testing=True,
        source_index_lease_seconds=30,
        source_index_timeout_seconds=1,
        lightrag_client_kind="native",
    )
    client = LightRAGClient(settings)

    async def slow():
        await asyncio.sleep(5)
        return "never"

    with pytest.raises(SourceIndexError) as timed_out:
        client._run(slow())
    assert timed_out.value.code == "source_index_timeout"
    assert "timed out" in timed_out.value.message.lower()
    assert "traceback" not in timed_out.value.message.lower()


def test_native_retrieval_preserves_schema_v2_candidate_without_rewriting() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        testing=True,
        source_index_lease_seconds=30,
        source_index_timeout_seconds=1,
        lightrag_client_kind="native",
    )
    client = LightRAGClient(settings)
    sha = "b" * 64
    candidate = (
        f"[CE_BLOCK schema=2 source_id=source-1 source_sha256={sha} block_id=block-1 order=1]\n"
        "Native preserved body"
    )
    native_chunk = f"[CE_SOURCE schema=2 source_id=source-1 sha256={sha}]\n\n{candidate}"

    class _Rag:
        async def aquery_data(self, _question, _params):
            return {"status": "success", "data": {"chunks": [{"content": native_chunk}]}}

    class _QueryParam:
        def __init__(self, **_kwargs) -> None:
            pass

    async def _new_rag(_domain):
        return _Rag(), {"QueryParam": _QueryParam}

    async def _close_rag(_rag, _runtime):
        return None

    client._new_rag = _new_rag  # type: ignore[method-assign]
    client._close_rag = _close_rag  # type: ignore[method-assign]
    client._run = lambda awaitable, deadline=None: asyncio.run(awaitable)  # type: ignore[method-assign]

    result = client.retrieve(
        Domain(
            id="domain-index",
            display_name="Index",
            runtime_instance_id="runtime-1",
            embedding_profile_id="openai-embedding-default",
            state="running",
        ),
        question="question",
        deadline=None,
    )

    assert result.candidates[0].text == candidate
    assert parse_ce_block_marker(result.candidates[0].text) is not None


def test_settings_require_index_lease_longer_than_timeout() -> None:
    with pytest.raises(ValueError, match="source_index_lease_seconds must exceed"):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            testing=True,
            source_index_lease_seconds=60,
            source_index_timeout_seconds=120,
        )
