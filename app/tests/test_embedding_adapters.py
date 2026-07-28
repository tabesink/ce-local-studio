"""P10-05 U7: immutable-profile embedding adapters (AE7)."""

from __future__ import annotations

import math

import pytest

from context_engine.adapters.embeddings import (
    EmbeddingAdapterError,
    EmbeddingRequest,
    OpenAIEmbeddingAdapter,
    default_embedding_registry,
    resolve_embedding_adapter,
    synthetic_embedding_vectors,
    validate_embedding_vectors,
)
from context_engine.models import PROVIDER_BEDROCK, PROVIDER_OLLAMA, PROVIDER_OPENAI


def test_openai_embedding_adapter_validates_model_and_dimensions() -> None:
    def transport(request: EmbeddingRequest) -> list[list[float]]:
        assert request.model_name == "text-embedding-3-small"
        assert request.dimensions == 8
        assert request.credential == "sk-test"
        return [[float(i) for i in range(8)] for _ in request.texts]

    adapter = OpenAIEmbeddingAdapter(transport=transport)
    vectors = adapter.embed(
        EmbeddingRequest(
            texts=("alpha", "beta"),
            model_name="text-embedding-3-small",
            dimensions=8,
            credential="sk-test",
        )
    )
    assert len(vectors) == 2
    assert len(vectors[0]) == 8


def test_embedding_dimension_mismatch_and_nonfinite_fail_closed() -> None:
    with pytest.raises(EmbeddingAdapterError) as mismatch:
        validate_embedding_vectors([[1.0, 2.0]], expected_count=1, expected_dimensions=3)
    assert mismatch.value.code == "embedding_dimension_mismatch"

    with pytest.raises(EmbeddingAdapterError) as bad:
        validate_embedding_vectors([[1.0, math.nan]], expected_count=1, expected_dimensions=2)
    assert bad.value.code == "embedding_malformed_response"

    with pytest.raises(EmbeddingAdapterError) as count:
        validate_embedding_vectors([[1.0]], expected_count=2, expected_dimensions=1)
    assert count.value.code == "embedding_malformed_response"


def test_missing_credential_and_unsupported_providers_fail_closed() -> None:
    with pytest.raises(EmbeddingAdapterError) as missing:
        OpenAIEmbeddingAdapter(transport=lambda _req: [[1.0]]).embed(
            EmbeddingRequest(texts=("x",), model_name="text-embedding-3-small", dimensions=1, credential=None)
        )
    assert missing.value.code == "embedding_not_ready"

    for kind in (PROVIDER_BEDROCK, PROVIDER_OLLAMA, "unknown"):
        adapter = resolve_embedding_adapter(kind)
        with pytest.raises(EmbeddingAdapterError) as exc_info:
            adapter.embed(
                EmbeddingRequest(
                    texts=("x",),
                    model_name="m",
                    dimensions=8,
                    credential="secret",
                )
            )
        assert exc_info.value.code == "embedding_not_ready"


def test_registry_maps_openai_and_keeps_bedrock_ollama_unsupported() -> None:
    registry = default_embedding_registry()
    assert PROVIDER_OPENAI in registry
    assert PROVIDER_BEDROCK in registry
    assert PROVIDER_OLLAMA in registry


def test_synthetic_vectors_are_deterministic_and_dimensioned() -> None:
    a = synthetic_embedding_vectors(("hello",), dimensions=4)
    b = synthetic_embedding_vectors(("hello",), dimensions=4)
    assert a == b
    assert len(a[0]) == 4
