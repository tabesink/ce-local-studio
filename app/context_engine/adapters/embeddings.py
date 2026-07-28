"""Private embedding adapters for the per-domain LightRAG runtime.

Selected only from sealed server-resolved profile/credentials. Never authorize,
log credentials/vectors, or expose provider URLs to product DTOs.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from context_engine.models import PROVIDER_BEDROCK, PROVIDER_OLLAMA, PROVIDER_OPENAI

SAFE_EMBEDDING_FAILURE_MESSAGE = "Embedding is unavailable."

OpenAIEmbeddingTransport = Callable[["EmbeddingRequest"], list[list[float]]]


class EmbeddingAdapterError(Exception):
    def __init__(
        self,
        code: str,
        message: str = SAFE_EMBEDDING_FAILURE_MESSAGE,
        status_code: int = 502,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class EmbeddingRequest:
    texts: tuple[str, ...]
    model_name: str
    dimensions: int
    credential: str | None
    timeout_seconds: float = 60.0


class EmbeddingAdapter(Protocol):
    def embed(self, request: EmbeddingRequest) -> list[list[float]]: ...


def validate_embedding_vectors(
    vectors: Sequence[Sequence[float]],
    *,
    expected_count: int,
    expected_dimensions: int,
) -> list[list[float]]:
    if len(vectors) != expected_count:
        raise EmbeddingAdapterError(
            "embedding_malformed_response",
            SAFE_EMBEDDING_FAILURE_MESSAGE,
            502,
        )
    validated: list[list[float]] = []
    for row in vectors:
        if len(row) != expected_dimensions:
            raise EmbeddingAdapterError(
                "embedding_dimension_mismatch",
                SAFE_EMBEDDING_FAILURE_MESSAGE,
                502,
            )
        floats: list[float] = []
        for value in row:
            number = float(value)
            if not math.isfinite(number):
                raise EmbeddingAdapterError(
                    "embedding_malformed_response",
                    SAFE_EMBEDDING_FAILURE_MESSAGE,
                    502,
                )
            floats.append(number)
        validated.append(floats)
    return validated


def _default_openai_embedding_transport(request: EmbeddingRequest) -> list[list[float]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EmbeddingAdapterError("embedding_unavailable", SAFE_EMBEDDING_FAILURE_MESSAGE, 503) from exc
    if not request.credential:
        raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409)
    try:
        client = OpenAI(api_key=request.credential, timeout=request.timeout_seconds)
        # text-embedding-3-* accepts dimensions; ada-002 ignores unknown kwargs via SDK.
        kwargs: dict[str, object] = {
            "model": request.model_name,
            "input": list(request.texts),
        }
        if request.model_name.startswith("text-embedding-3"):
            kwargs["dimensions"] = request.dimensions
        response = client.embeddings.create(**kwargs)
        data = getattr(response, "data", None) or []
        ordered = sorted(data, key=lambda item: int(getattr(item, "index", 0)))
        return [list(getattr(item, "embedding", [])) for item in ordered]
    except EmbeddingAdapterError:
        raise
    except TimeoutError as exc:
        raise EmbeddingAdapterError("embedding_timeout", SAFE_EMBEDDING_FAILURE_MESSAGE, 504) from exc
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "auth" in message or "401" in message or "403" in message or "api key" in message:
            raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409) from exc
        if "timeout" in message or "timed out" in message:
            raise EmbeddingAdapterError("embedding_timeout", SAFE_EMBEDDING_FAILURE_MESSAGE, 504) from exc
        raise EmbeddingAdapterError("embedding_unavailable", SAFE_EMBEDDING_FAILURE_MESSAGE, 502) from exc


class OpenAIEmbeddingAdapter:
    def __init__(self, *, transport: OpenAIEmbeddingTransport | None = None) -> None:
        self._transport = transport or _default_openai_embedding_transport

    def embed(self, request: EmbeddingRequest) -> list[list[float]]:
        if not request.credential:
            raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409)
        if request.dimensions <= 0 or not request.texts:
            raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409)
        try:
            vectors = self._transport(request)
        except EmbeddingAdapterError as exc:
            raise EmbeddingAdapterError(exc.code, exc.message, exc.status_code) from None
        except TimeoutError:
            raise EmbeddingAdapterError("embedding_timeout", SAFE_EMBEDDING_FAILURE_MESSAGE, 504) from None
        except Exception:
            raise EmbeddingAdapterError("embedding_unavailable", SAFE_EMBEDDING_FAILURE_MESSAGE, 502) from None
        return validate_embedding_vectors(
            vectors,
            expected_count=len(request.texts),
            expected_dimensions=request.dimensions,
        )


class UnsupportedEmbeddingAdapter:
    def __init__(self, provider_kind: str) -> None:
        self._provider_kind = provider_kind

    def embed(self, request: EmbeddingRequest) -> list[list[float]]:
        raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409)


def default_embedding_registry(
    *,
    transport: OpenAIEmbeddingTransport | None = None,
) -> dict[str, EmbeddingAdapter]:
    return {
        PROVIDER_OPENAI: OpenAIEmbeddingAdapter(transport=transport),
        PROVIDER_BEDROCK: UnsupportedEmbeddingAdapter(PROVIDER_BEDROCK),
        PROVIDER_OLLAMA: UnsupportedEmbeddingAdapter(PROVIDER_OLLAMA),
    }


def resolve_embedding_adapter(
    provider_kind: str,
    *,
    registry: dict[str, EmbeddingAdapter] | None = None,
) -> EmbeddingAdapter:
    adapters = registry if registry is not None else default_embedding_registry()
    adapter = adapters.get(provider_kind)
    if adapter is None:
        return UnsupportedEmbeddingAdapter(provider_kind)
    return adapter


def synthetic_embedding_vectors(texts: Sequence[str], *, dimensions: int) -> list[list[float]]:
    """Deterministic non-production vectors for explicit synthetic-only lanes."""
    if dimensions <= 0:
        raise EmbeddingAdapterError("embedding_not_ready", "Embedding is not configured.", 409)
    return [
        [float((idx + len(text)) % 7) for idx in range(dimensions)]
        for text in texts
    ]
