from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass

import pytest

import context_engine.services.evidence as evidence_service
from context_engine.config import Settings
from context_engine.models import (
    SOURCE_INDEX_STATE_READY,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.evidence import (
    FrozenRetrievalScope,
    FrozenSourceIdentity,
    ScopedRetrievalCandidate,
    ScopedRetrievalError,
    ScopedRetrievalResult,
    map_retrieval_hits_to_internal_evidence,
    retrieve_bounded_candidates,
)
from context_engine.services.indexing import LightRAGClientProtocol


@dataclass
class _FixtureRetrievalClient:
    result: object
    seen_domain_id: str | None = None
    seen_question: str | None = None
    seen_deadline: float | None = None

    def retrieve(self, domain: Domain, *, question: str, deadline: float) -> object:
        self.seen_domain_id = domain.id
        self.seen_question = question
        self.seen_deadline = deadline
        return self.result


def _domain() -> Domain:
    return Domain(
        id="domain-retrieval",
        display_name="Retrieval",
        runtime_instance_id="runtime-1",
        embedding_profile_id="openai-embedding-default",
        state="running",
    )


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "testing": True,
        "source_index_lease_seconds": 180,
        "source_index_timeout_seconds": 120,
        "retrieval_timeout_seconds": 2,
        "retrieval_global_concurrency": 4,
        "retrieval_per_domain_concurrency": 2,
        "retrieval_max_candidates": 10,
        "retrieval_max_candidate_bytes": 128,
        "retrieval_max_aggregate_bytes": 512,
    }
    values.update(overrides)
    return Settings(**values)


def test_scoped_port_is_separate_and_caps_candidates_before_mapping() -> None:
    assert not hasattr(LightRAGClientProtocol, "retrieve")
    question = "SENTINEL-PRIVATE-QUESTION"
    client = _FixtureRetrievalClient(
        ScopedRetrievalResult(
            candidates=tuple(ScopedRetrievalCandidate(text=f"candidate-{index}") for index in range(11))
        )
    )

    candidates = retrieve_bounded_candidates(
        settings=_settings(),
        domain=_domain(),
        question=question,
        client=client,
    )

    assert len(candidates) == 10
    assert client.seen_domain_id == "domain-retrieval"
    assert client.seen_question == question
    assert isinstance(client.seen_deadline, float)


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (("not", "closed"), "retrieval_malformed"),
        (ScopedRetrievalResult(candidates=("wrong-type",)), "retrieval_malformed"),
        (
            ScopedRetrievalResult(candidates=(ScopedRetrievalCandidate(text="x" * 129),)),
            "retrieval_malformed",
        ),
        (
                ScopedRetrievalResult(
                    candidates=tuple(
                        ScopedRetrievalCandidate(text=character * 110)
                        for character in ("v", "w", "x", "y", "z")
                    )
                ),
            "retrieval_malformed",
        ),
    ],
)
def test_scoped_port_rejects_malformed_or_oversized_results_without_private_content(
    result: object,
    code: str,
) -> None:
    question = "SENTINEL-PRIVATE-QUESTION"
    client = _FixtureRetrievalClient(result)

    with pytest.raises(ScopedRetrievalError) as failure:
        retrieve_bounded_candidates(
            settings=_settings(),
            domain=_domain(),
            question=question,
            client=client,
        )

    assert failure.value.code == code
    assert question not in str(failure.value)
    assert "x" * 32 not in str(failure.value)


def test_scoped_port_normalizes_adapter_failure_without_private_content() -> None:
    question = "SENTINEL-PRIVATE-QUESTION"

    class _FailingClient:
        def retrieve(self, domain: Domain, *, question: str, deadline: float) -> object:
            raise ScopedRetrievalError("retrieval_unavailable", f"leaked: {question}")

    with pytest.raises(ScopedRetrievalError) as failure:
        retrieve_bounded_candidates(
            settings=_settings(),
            domain=_domain(),
            question=question,
            client=_FailingClient(),
        )

    assert failure.value.code == "retrieval_unavailable"
    assert question not in str(failure.value)
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None
    assert question not in "".join(traceback.format_exception(failure.value))


def test_scoped_port_saturation_releases_gate_for_later_calls() -> None:
    started = threading.Event()
    release = threading.Event()
    results: list[tuple[ScopedRetrievalCandidate, ...]] = []
    failures: list[BaseException] = []

    class _BlockingClient:
        def retrieve(self, domain: Domain, *, question: str, deadline: float) -> ScopedRetrievalResult:
            started.set()
            assert release.wait(timeout=1)
            return ScopedRetrievalResult(candidates=())

    def run_first_call() -> None:
        try:
            results.append(
                retrieve_bounded_candidates(
                    settings=_settings(
                        retrieval_timeout_seconds=1,
                        retrieval_global_concurrency=1,
                        retrieval_per_domain_concurrency=1,
                    ),
                    domain=_domain(),
                    question="first",
                    client=_BlockingClient(),
                )
            )
        except BaseException as exc:  # noqa: BLE001  # pragma: no cover - surfaced on the test thread
            failures.append(exc)

    first = threading.Thread(target=run_first_call, daemon=True)
    first.start()
    assert started.wait(timeout=1)

    with pytest.raises(ScopedRetrievalError) as saturated:
        retrieve_bounded_candidates(
            settings=_settings(
                retrieval_timeout_seconds=0.01,
                retrieval_global_concurrency=1,
                retrieval_per_domain_concurrency=1,
            ),
            domain=_domain(),
            question="second",
            client=_FixtureRetrievalClient(ScopedRetrievalResult(candidates=())),
        )
    assert saturated.value.code == "retrieval_saturated"

    release.set()
    first.join(timeout=1)
    assert not first.is_alive()
    assert failures == []
    assert results == [()]

    assert (
        retrieve_bounded_candidates(
            settings=_settings(
                retrieval_global_concurrency=1,
                retrieval_per_domain_concurrency=1,
            ),
            domain=_domain(),
            question="third",
            client=_FixtureRetrievalClient(ScopedRetrievalResult(candidates=())),
        )
        == ()
    )


def test_scoped_port_rejects_late_result_and_releases_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    readings = iter((0.0, 0.0, 0.0, 2.0))
    monkeypatch.setattr(evidence_service.time, "monotonic", lambda: next(readings, 2.0))
    settings = _settings(
        retrieval_timeout_seconds=1,
        retrieval_global_concurrency=1,
        retrieval_per_domain_concurrency=1,
    )
    client = _FixtureRetrievalClient(ScopedRetrievalResult(candidates=()))

    with pytest.raises(ScopedRetrievalError) as late:
        retrieve_bounded_candidates(
            settings=settings,
            domain=_domain(),
            question="late",
            client=client,
        )
    assert late.value.code == "retrieval_timeout"

    assert (
        retrieve_bounded_candidates(
            settings=settings,
            domain=_domain(),
            question="after-timeout",
            client=client,
        )
        == ()
    )


def test_retrieval_settings_are_positive_and_aggregate_covers_one_candidate() -> None:
    with pytest.raises(ValueError, match="retrieval_timeout_seconds must be positive"):
        _settings(retrieval_timeout_seconds=0)
    with pytest.raises(ValueError, match="retrieval_max_aggregate_bytes"):
        _settings(retrieval_max_candidate_bytes=513, retrieval_max_aggregate_bytes=512)


class _Rows:
    def __init__(self, rows: list[tuple[SourceBlock, SourceDocument]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[SourceBlock, SourceDocument]]:
        return self._rows


class _MappingSession:
    def __init__(self, rows: list[tuple[SourceBlock, SourceDocument]]) -> None:
        self.rows = rows
        self.execute_calls = 0

    def execute(self, _statement):
        self.execute_calls += 1
        return _Rows(self.rows)


def test_exact_schema_v2_mapping_uses_one_query_canonical_content_and_dense_first_wins() -> None:
    source = SourceDocument(
        id="source-1",
        public_ref="docref-source-1",
        domain_id="domain-retrieval",
        original_filename="manual.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=128,
        original_object_key="obj/source-1",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
        preparation_generation=3,
        index_state=SOURCE_INDEX_STATE_READY,
        index_generation=4,
        index_request_id="source-1-4-request",
        index_content_hash="c" * 64,
    )
    block = SourceBlock(
        id="block-1",
        source_document_id=source.id,
        domain_id=source.domain_id,
        source_order=2,
        kind="text",
        canonical_markdown="Canonical database content",
    )
    scope = FrozenRetrievalScope(
        domain_id=source.domain_id,
        control_generation=5,
        runtime_instance_id="runtime-1",
        sources=(
            FrozenSourceIdentity(
                source_document_id=source.id,
                preparation_generation=source.preparation_generation,
                index_generation=source.index_generation,
                index_request_id=source.index_request_id or "",
                index_content_hash=source.index_content_hash or "",
                original_sha256=source.original_sha256,
            ),
        ),
    )
    marker = (
        f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={source.original_sha256} "
        f"block_id={block.id} order={block.source_order}]"
    )
    db = _MappingSession([(block, source)])

    mapped = map_retrieval_hits_to_internal_evidence(
        db,  # type: ignore[arg-type]
        hits=[
            ScopedRetrievalCandidate(text="[CE_BLOCK id=block-legacy order=1]\nlegacy"),
            ScopedRetrievalCandidate(
                text=(
                    f"[CE_BLOCK schema=2 source_id=wrong-source source_sha256={source.original_sha256} "
                    f"block_id={block.id} order={block.source_order}]\nwrong source"
                )
            ),
            ScopedRetrievalCandidate(
                text=(
                    f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={'d' * 64} "
                    f"block_id={block.id} order={block.source_order}]\nwrong hash"
                )
            ),
            ScopedRetrievalCandidate(
                text=(
                    f"[CE_BLOCK schema=2 source_id={source.id} source_sha256={source.original_sha256} "
                    f"block_id={block.id} order=1]\nwrong order"
                )
            ),
            ScopedRetrievalCandidate(text=f"{marker}\nprovider text must not become excerpt"),
            ScopedRetrievalCandidate(text=f"{marker}\nduplicate"),
        ],
        frozen_scope=scope,
    )

    assert db.execute_calls == 1
    assert len(mapped) == 1
    assert mapped[0].source_document_id == source.id
    assert mapped[0].source_block_id == block.id
    assert mapped[0].excerpt == "Canonical database content"
    assert mapped[0].retrieval_order == 1
