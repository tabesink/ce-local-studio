"""Private per-domain LightRAG HTTP shim (not a public product API).

Preserves Context Engine request_id identity and schema-v2 handoff bytes while
isolating vendored LightRAG module state inside one container per domain.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

RUNTIME_ROOT = Path(os.environ.get("CE_RUNTIME_ROOT", "/ce-runtime"))
SECRETS_FILE = RUNTIME_ROOT / "secrets" / "provider.env"
WORKING_DIR = Path(os.environ.get("WORKING_DIR", str(RUNTIME_ROOT / "lightrag")))
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _load_sealed_env() -> None:
    if not SECRETS_FILE.is_file():
        return
    mode = SECRETS_FILE.stat().st_mode & 0o777
    if mode & 0o077:
        raise RuntimeError("Sealed provider env permissions are too open.")
    for raw_line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _safe_request_id(request_id: str) -> str:
    if _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise HTTPException(status_code=422, detail="invalid_request_id")
    return request_id


class SubmitBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    content_hash: str = Field(min_length=64, max_length=64)
    rendered_text: str = Field(min_length=1)


class RetrieveBody(BaseModel):
    question: str = Field(min_length=1)


def create_app() -> FastAPI:
    _load_sealed_env()
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    from context_engine.services.lightrag_runtime import (
        assert_vendored_lightrag_loaded,
        ensure_vendored_lightrag_import_path,
    )

    ensure_vendored_lightrag_import_path()
    import lightrag
    import numpy as np
    from lightrag import LightRAG
    from lightrag.utils import Tokenizer, wrap_embedding_func_with_attrs

    assert_vendored_lightrag_loaded(lightrag)

    embed_dim = int(os.environ.get("CE_EMBEDDING_DIMENSIONS", "8"))
    model_name = os.environ.get("CE_EMBEDDING_MODEL_NAME", "ce-domain-embedding")
    provider_kind = os.environ.get("CE_EMBEDDING_PROVIDER_KIND", "").strip().lower()
    credential = os.environ.get("CE_EMBEDDING_CREDENTIAL")
    allow_synthetic = os.environ.get("CE_EMBEDDING_ALLOW_SYNTHETIC", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    from context_engine.adapters.embeddings import (
        EmbeddingAdapterError,
        EmbeddingRequest,
        resolve_embedding_adapter,
        synthetic_embedding_vectors,
    )

    if allow_synthetic:
        embedding_mode = "synthetic"
        embedding_adapter = None
    elif provider_kind:
        embedding_mode = "provider"
        embedding_adapter = resolve_embedding_adapter(provider_kind)
    else:
        raise RuntimeError("Embedding provider is not configured for this runtime.")

    class _OfflineCharTokenizer:
        """Reversible char tokenizer — no tiktoken CDN (domain net is internal)."""

        def encode(self, content: str) -> list[int]:
            return [ord(char) for char in content]

        def decode(self, tokens: list[int]) -> str:
            return "".join(chr(token) for token in tokens if 0 <= int(token) <= 0x10FFFF)

    @wrap_embedding_func_with_attrs(embedding_dim=embed_dim, max_token_size=8192, model_name=model_name)
    async def embed(texts, **_kwargs):
        text_list = list(texts)
        if embedding_mode == "synthetic":
            vectors = synthetic_embedding_vectors(text_list, dimensions=embed_dim)
            return np.array(vectors, dtype=np.float32)
        assert embedding_adapter is not None
        try:
            vectors = embedding_adapter.embed(
                EmbeddingRequest(
                    texts=tuple(text_list),
                    model_name=model_name,
                    dimensions=embed_dim,
                    credential=credential,
                )
            )
        except EmbeddingAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
        return np.array(vectors, dtype=np.float32)

    async def llm(_prompt, system_prompt=None, history_messages=None, **_kwargs):
        # Entity extraction stub: Phase 1 retrieval uses naive chunk mode;
        # grounded synthesis stays in the API worker, not the LightRAG container.
        return "entity"

    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        embedding_func=embed,
        llm_model_func=llm,
        tokenizer=Tokenizer(model_name="ce-offline", tokenizer=_OfflineCharTokenizer()),
        # Char tokenizer: keep schema-v2 markers intact (256 would split mid-marker).
        chunk_token_size=int(os.environ.get("CE_LIGHTRAG_CHUNK_TOKEN_SIZE", "16384")),
        chunk_overlap_token_size=0,
    )

    app = FastAPI(title="ce-lightrag-shim", docs_url=None, redoc_url=None, openapi_url=None)
    initialized = {"ok": False}

    async def _ensure_ready() -> None:
        if not initialized["ok"]:
            await rag.initialize_storages()
            initialized["ok"] = True

    @app.get("/health")
    async def health() -> dict[str, str]:
        await _ensure_ready()
        return {"status": "healthy"}

    @app.post("/v1/index/submit")
    async def submit(body: SubmitBody) -> dict[str, str]:
        await _ensure_ready()
        request_id = _safe_request_id(body.request_id)
        if hashlib.sha256(body.rendered_text.encode("utf-8")).hexdigest() != body.content_hash:
            raise HTTPException(status_code=409, detail="source_index_conflict")
        returned = await rag.ainsert(
            body.rendered_text,
            ids=request_id,
            file_paths=f"{request_id}.ce-source",
            track_id=request_id,
        )
        if returned not in {None, request_id}:
            raise HTTPException(status_code=502, detail="source_index_unavailable")
        return {"remote_document_id": f"lightrag:{request_id}"}

    @app.get("/v1/index/readiness/{request_id}")
    async def readiness(request_id: str) -> dict[str, Any]:
        await _ensure_ready()
        request_id = _safe_request_id(request_id)
        status = await rag.doc_status.get_by_id(request_id)
        if status is None:
            return {
                "ready": False,
                "failed": True,
                "error_code": "source_index_missing",
                "error_message": "Source index content is unavailable.",
            }
        raw_status = status.get("status") if isinstance(status, dict) else getattr(status, "status", None)
        status_value = getattr(raw_status, "value", raw_status)
        if status_value == "failed":
            return {
                "ready": False,
                "failed": True,
                "error_code": "source_index_failed",
                "error_message": "Source index failed.",
            }
        return {"ready": status_value == "processed", "failed": False}

    @app.delete("/v1/index/{request_id}")
    async def delete(request_id: str) -> dict[str, bool]:
        await _ensure_ready()
        request_id = _safe_request_id(request_id)
        await rag.adelete_by_doc_id(request_id)
        return {"ok": True}

    @app.get("/v1/index/{request_id}/absent")
    async def is_absent(request_id: str) -> dict[str, bool]:
        await _ensure_ready()
        request_id = _safe_request_id(request_id)
        return {"absent": await rag.doc_status.get_by_id(request_id) is None}

    @app.post("/v1/retrieve")
    async def retrieve(body: RetrieveBody) -> dict[str, Any]:
        await _ensure_ready()
        from lightrag.base import QueryParam

        result = await rag.aquery_data(body.question, QueryParam(mode="naive", top_k=10, chunk_top_k=10))
        return result if isinstance(result, dict) else {"status": "failure", "data": {"chunks": []}}

    return app


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "9621"))
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ce-lightrag-shim failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
