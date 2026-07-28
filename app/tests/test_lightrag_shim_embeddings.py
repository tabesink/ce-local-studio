"""P10-05 U7: LightRAG shim selects sealed embedding bindings."""

from __future__ import annotations

import asyncio

import pytest

from context_engine.adapters.embeddings import EmbeddingAdapterError, EmbeddingRequest


def test_shim_uses_provider_adapter_when_synthetic_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_EMBEDDING_DIMENSIONS", "4")
    monkeypatch.setenv("CE_EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    monkeypatch.setenv("CE_EMBEDDING_PROVIDER_KIND", "openai")
    monkeypatch.setenv("CE_EMBEDDING_CREDENTIAL", "sk-test")
    monkeypatch.delenv("CE_EMBEDDING_ALLOW_SYNTHETIC", raising=False)
    monkeypatch.setenv("CE_RUNTIME_ROOT", "/tmp/ce-shim-test-runtime")
    monkeypatch.setenv("WORKING_DIR", "/tmp/ce-shim-test-runtime/lightrag")

    calls: list[EmbeddingRequest] = []

    class _FakeAdapter:
        def embed(self, request: EmbeddingRequest) -> list[list[float]]:
            calls.append(request)
            return [[0.1, 0.2, 0.3, 0.4] for _ in request.texts]

    monkeypatch.setattr(
        "context_engine.adapters.embeddings.resolve_embedding_adapter",
        lambda _kind, registry=None: _FakeAdapter(),
    )
    # Avoid constructing real LightRAG / vendored imports for this unit.
    import context_engine.tools.ce_lightrag_shim as shim

    captured: dict[str, object] = {}

    class _Tok:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

    class _Wrap:
        def __call__(self, **attrs):
            def decorator(fn):
                captured["attrs"] = attrs
                return fn

            return decorator

    class _FakeLightRAG:
        def __init__(self, **kwargs) -> None:
            captured["embedding_func"] = kwargs["embedding_func"]

    monkeypatch.setattr(shim, "create_app", shim.create_app)  # keep reference
    # Patch imports inside create_app by stubbing modules after path setup.
    import types
    import sys

    fake_lightrag = types.ModuleType("lightrag")
    fake_lightrag.LightRAG = _FakeLightRAG
    fake_utils = types.ModuleType("lightrag.utils")
    fake_utils.Tokenizer = _Tok
    fake_utils.wrap_embedding_func_with_attrs = _Wrap()
    monkeypatch.setitem(sys.modules, "lightrag", fake_lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", fake_utils)
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.ensure_vendored_lightrag_import_path",
        lambda: None,
    )
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.assert_vendored_lightrag_loaded",
        lambda _mod: None,
    )

    app = shim.create_app()
    assert app is not None
    embed_fn = captured["embedding_func"]
    assert embed_fn is not None
    vectors = asyncio.run(embed_fn(["hello"]))  # type: ignore[misc]
    assert getattr(vectors, "shape", None) == (1, 4)
    assert calls and calls[0].credential == "sk-test"
    assert calls[0].dimensions == 4


def test_shim_requires_explicit_synthetic_or_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CE_EMBEDDING_ALLOW_SYNTHETIC", raising=False)
    monkeypatch.delenv("CE_EMBEDDING_PROVIDER_KIND", raising=False)
    monkeypatch.delenv("CE_EMBEDDING_CREDENTIAL", raising=False)
    monkeypatch.setenv("CE_RUNTIME_ROOT", "/tmp/ce-shim-test-runtime-2")
    monkeypatch.setenv("WORKING_DIR", "/tmp/ce-shim-test-runtime-2/lightrag")

    import types
    import sys
    import context_engine.tools.ce_lightrag_shim as shim

    fake_lightrag = types.ModuleType("lightrag")
    fake_lightrag.LightRAG = lambda **kwargs: None
    fake_utils = types.ModuleType("lightrag.utils")
    fake_utils.Tokenizer = lambda *a, **k: None
    fake_utils.wrap_embedding_func_with_attrs = lambda **attrs: (lambda fn: fn)
    monkeypatch.setitem(sys.modules, "lightrag", fake_lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", fake_utils)
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.ensure_vendored_lightrag_import_path",
        lambda: None,
    )
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.assert_vendored_lightrag_loaded",
        lambda _mod: None,
    )

    with pytest.raises(RuntimeError, match="Embedding provider is not configured"):
        shim.create_app()


def test_provider_embed_error_maps_without_leaking_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.setenv("CE_EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    monkeypatch.setenv("CE_EMBEDDING_PROVIDER_KIND", "openai")
    monkeypatch.setenv("CE_EMBEDDING_CREDENTIAL", "sk-secret-do-not-leak")
    monkeypatch.delenv("CE_EMBEDDING_ALLOW_SYNTHETIC", raising=False)
    monkeypatch.setenv("CE_RUNTIME_ROOT", "/tmp/ce-shim-test-runtime-3")
    monkeypatch.setenv("WORKING_DIR", "/tmp/ce-shim-test-runtime-3/lightrag")

    class _Boom:
        def embed(self, request: EmbeddingRequest) -> list[list[float]]:
            raise EmbeddingAdapterError("embedding_timeout", "Embedding is unavailable.", 504)

    monkeypatch.setattr(
        "context_engine.adapters.embeddings.resolve_embedding_adapter",
        lambda _kind, registry=None: _Boom(),
    )

    import types
    import sys
    import context_engine.tools.ce_lightrag_shim as shim
    from fastapi import HTTPException

    captured: dict[str, object] = {}

    class _FakeLightRAG:
        def __init__(self, **kwargs) -> None:
            captured["embedding_func"] = kwargs["embedding_func"]

    fake_lightrag = types.ModuleType("lightrag")
    fake_lightrag.LightRAG = _FakeLightRAG
    fake_utils = types.ModuleType("lightrag.utils")
    fake_utils.Tokenizer = lambda *a, **k: None
    fake_utils.wrap_embedding_func_with_attrs = lambda **attrs: (lambda fn: fn)
    monkeypatch.setitem(sys.modules, "lightrag", fake_lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", fake_utils)
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.ensure_vendored_lightrag_import_path",
        lambda: None,
    )
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.assert_vendored_lightrag_loaded",
        lambda _mod: None,
    )

    shim.create_app()
    embed_fn = captured["embedding_func"]
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(embed_fn(["q"]))  # type: ignore[misc]
    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "embedding_timeout"
    assert "sk-secret" not in str(exc_info.value.detail)
