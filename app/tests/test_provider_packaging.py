"""P10-05 U2: explicit parser/embedding/synthesis packaging gates (AE1/AE2 packaging half)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
PYPROJECT = ROOT / "pyproject.toml"


def test_dockerfile_default_has_additive_extra_gates_off() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG CE_STACK_LIVE_IMAGE=0" in text
    assert "ARG CE_STACK_OBJECT_STORE_IMAGE=0" in text
    assert "ARG CE_STACK_PARSERS_IMAGE=0" in text
    assert "--extra lightrag-runtime" in text
    assert "--extra embeddings" in text
    assert "--extra parsers" in text
    assert "--extra synthesis" in text
    assert "--extra object-store" in text
    # Default path must not force provider extras without gates.
    assert 'CE_STACK_LIVE_IMAGE" = "1"' in text or "CE_STACK_LIVE_IMAGE" in text
    assert "CE_STACK_PARSERS_IMAGE" in text


def test_pyproject_declares_parsers_synthesis_embeddings_extras() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "parsers =" in text
    assert "docling" in text
    assert "reductoai" in text
    assert "synthesis =" in text
    assert "embeddings =" in text
    assert "openai" in text


def test_missing_docling_import_maps_to_parser_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    from context_engine.adapters.parsers import (
        PARSER_DOCLING,
        DoclingDocumentParser,
        ParserAdapterError,
        ParserRequest,
    )

    real_import = builtins.__import__

    def _blocked(name: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if name == "docling" or name.startswith("docling."):
            raise ImportError("docling not installed in this profile")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    from context_engine.adapters import parsers as parsers_mod

    parser = DoclingDocumentParser(convert=parsers_mod._default_docling_convert)
    with pytest.raises(ParserAdapterError) as exc_info:
        parser.parse(
            ParserRequest(
                source_document_id="src-packaging",
                parser_kind=PARSER_DOCLING,
                original_bytes=b"%PDF-1.4",
                content_type="application/pdf",
                filename="sample.pdf",
            )
        )
    assert exc_info.value.code == "parser_unavailable"
    assert exc_info.value.status_code == 503


def test_deployment_profile_cannot_advertise_absent_embedding_extra() -> None:
    """Matrix/docs may claim embeddings only when the extra exists in pyproject."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "[project.optional-dependencies]" in text
    assert "embeddings" in text
    # Bedrock/Ollama embedding SDKs are intentionally not packaged yet.
    assert "boto3" not in text.split("embeddings = [")[1].split("]")[0]
    assert "ollama" not in text.lower().split("embeddings")[1][:200]
