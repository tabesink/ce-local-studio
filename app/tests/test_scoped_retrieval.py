from __future__ import annotations

from dataclasses import dataclass

import pytest

from context_engine.config import Settings
from context_engine.models import Domain
from context_engine.services.evidence import (
    ScopedRetrievalCandidate,
    ScopedRetrievalError,
    ScopedRetrievalResult,
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


def test_retrieval_settings_are_positive_and_aggregate_covers_one_candidate() -> None:
    with pytest.raises(ValueError, match="retrieval_timeout_seconds must be positive"):
        _settings(retrieval_timeout_seconds=0)
    with pytest.raises(ValueError, match="retrieval_max_aggregate_bytes"):
        _settings(retrieval_max_candidate_bytes=513, retrieval_max_aggregate_bytes=512)
