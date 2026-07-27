from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import (
    AUDIT_EVENT_SOURCE_INDEX_CANCELLED,
    AUDIT_EVENT_SOURCE_INDEX_RETRY_QUEUED,
    DOMAIN_STATE_DELETING,
    SOURCE_INDEX_REMOTE_STATES,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLED,
    SOURCE_INDEX_STATE_CANCELLING,
    SOURCE_INDEX_STATE_FAILED,
    SOURCE_INDEX_STATE_NOT_REQUESTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_STATE_PREPARED,
    Domain,
    SourceBlock,
    SourceDocument,
)
from context_engine.services.audit import AuditContext, commit_protected_mutation
from context_engine.services.domains import (
    DomainRuntimeController,
    controller_from_settings,
    domain_available,
)
from context_engine.services.lightrag_runtime import (
    assert_vendored_lightrag_loaded,
    ensure_vendored_lightrag_import_path,
)
from context_engine.services.structured_logging import safe_log
from context_engine.services.metrics import safe_increment

logger = logging.getLogger(__name__)

LIGHTRAG_HANDOFF_SCHEMA_VERSION = "2"
SOURCE_INDEX_UNCERTAIN_CODE = "source_index_uncertain"
_RENDER_HEADER_RE = re.compile(
    rf"^\[CE_BLOCK schema={re.escape(LIGHTRAG_HANDOFF_SCHEMA_VERSION)} "
    r"source_id=([^\]\s]+) source_sha256=([^\]\s]{64}) "
    r"block_id=([^\]\s]+) order=([1-9]\d*)\]$",
    re.MULTILINE,
)
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_NATIVE_LIGHTRAG_LIFECYCLE_LOCK = threading.RLock()


class SourceIndexError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class RenderedLightRAGInput:
    text: str
    content_hash: str
    block_ids: tuple[str, ...]


@dataclass(frozen=True)
class IndexSubmitResult:
    remote_document_id: str


@dataclass(frozen=True)
class IndexReadiness:
    ready: bool
    failed: bool = False
    error_code: str | None = None
    error_message: str | None = None


class LightRAGClientProtocol(Protocol):
    def submit(self, domain: Domain, *, request_id: str, content_hash: str, rendered_text: str) -> IndexSubmitResult: ...

    def readiness(self, domain: Domain, *, request_id: str) -> IndexReadiness: ...

    def delete(self, domain: Domain, *, request_id: str) -> None: ...

    def is_absent(self, domain: Domain, *, request_id: str) -> bool: ...


def _safe_error(code: str, message: str) -> SourceIndexError:
    return SourceIndexError(502, code, message)


def _normalize_markdown(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def render_blocks_to_lightrag_handoff(
    *,
    source_id: str,
    original_sha256: str,
    blocks: list[SourceBlock],
) -> RenderedLightRAGInput:
    """Render ordered Source Blocks into the versioned LightRAG handoff."""
    if not blocks:
        raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")

    seen_ids: set[str] = set()
    rendered_blocks: list[str] = []
    block_ids: list[str] = []
    for block in blocks:
        if block.id in seen_ids:
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        seen_ids.add(block.id)
        body = _normalize_markdown(block.canonical_markdown or "")
        if not body or re.search(r"\[CE_(?:SOURCE|BLOCK)\b", body):
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        rendered_blocks.append(
            f"[CE_BLOCK schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION} source_id={source_id} "
            f"source_sha256={original_sha256} block_id={block.id} order={block.source_order}]\n{body}"
        )
        block_ids.append(block.id)

    text = (
        f"[CE_SOURCE schema={LIGHTRAG_HANDOFF_SCHEMA_VERSION} "
        f"source_id={source_id} sha256={original_sha256}]\n\n" + "\n\n".join(rendered_blocks)
    )
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return RenderedLightRAGInput(text=text, content_hash=content_hash, block_ids=tuple(block_ids))


def render_lightrag_input(db: Session, source: SourceDocument) -> RenderedLightRAGInput:
    if source.state != SOURCE_STATE_PREPARED:
        raise SourceIndexError(409, "source_state_conflict", "Source state does not allow this operation.")

    blocks = list(
        db.scalars(
            select(SourceBlock)
            .where(SourceBlock.source_document_id == source.id)
            .order_by(SourceBlock.source_order, SourceBlock.id)
        )
    )
    return render_blocks_to_lightrag_handoff(
        source_id=source.id,
        original_sha256=source.original_sha256,
        blocks=blocks,
    )


def compute_index_request_id(source_id: str, generation: int, content_hash: str) -> str:
    return f"{source_id}-{generation}-{content_hash[:16]}"


def source_has_current_index_identity(source: SourceDocument) -> bool:
    if source.index_generation < 1 or not source.index_request_id or not source.index_content_hash:
        return False
    return source.index_request_id == compute_index_request_id(source.id, source.index_generation, source.index_content_hash)


def _queue_new_generation(db: Session, source: SourceDocument) -> RenderedLightRAGInput:
    rendered = render_lightrag_input(db, source)
    now = utc_now()
    source.index_generation += 1
    source.index_request_id = compute_index_request_id(source.id, source.index_generation, rendered.content_hash)
    source.index_content_hash = rendered.content_hash
    source.index_remote_document_id = None
    source.index_state = SOURCE_INDEX_STATE_QUEUED
    source.index_error_code = None
    source.index_error_message = None
    source.index_lease_owner = None
    source.index_lease_expires_at = None
    source.index_accepted_at = None
    source.index_ready_at = None
    source.index_updated_at = now
    source.updated_at = now
    source.version += 1
    return rendered


def queue_source_index_after_publish(db: Session, source: SourceDocument) -> None:
    if source.state != SOURCE_STATE_PREPARED:
        raise SourceIndexError(409, "source_state_conflict", "Source state does not allow this operation.")
    _queue_new_generation(db, source)


def _domain_or_404(db: Session, domain_id: str) -> Domain:
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise SourceIndexError(404, "domain_not_found", "Domain not found.")
    if domain.state == DOMAIN_STATE_DELETING:
        raise SourceIndexError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    return domain


def _source_or_404(db: Session, domain_id: str, source_id: str) -> SourceDocument:
    source = db.get(SourceDocument, source_id)
    if source is None or source.domain_id != domain_id:
        raise SourceIndexError(404, "source_not_found", "Source not found.")
    return source


def _safe_request_id(request_id: str) -> str:
    if _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
    return request_id


def _private_remote_id(request_id: str) -> str:
    return hashlib.sha256(f"ce-index:{request_id}".encode()).hexdigest()[:32]


def _rendered_block_ids(rendered_text: str) -> list[str]:
    return [match.group(3) for match in _RENDER_HEADER_RE.finditer(rendered_text)]


def _rendered_hit_chunks(rendered_text: str) -> list[dict[str, str]]:
    matches = list(_RENDER_HEADER_RE.finditer(rendered_text))
    chunks: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(rendered_text)
        text = rendered_text[start:end].strip()
        if text:
            chunks.append({"blockId": match.group(3), "text": text})
    return chunks


def _bounded_adapter_result(texts, settings: Settings):
    # Import lazily: evidence owns the retrieval port while this adapter also
    # implements the independent index-lifecycle protocol.
    from context_engine.services.evidence import (
        ScopedRetrievalCandidate,
        ScopedRetrievalResult,
        normalize_scoped_retrieval_result,
    )

    result = ScopedRetrievalResult(
        candidates=tuple(
            ScopedRetrievalCandidate(text=text)
            for text in itertools.islice(texts, settings.retrieval_max_candidates)
        )
    )
    normalize_scoped_retrieval_result(result, settings=settings)
    return result


class LocalLightRAGIndexClient:
    def __init__(self, settings: Settings, controller: DomainRuntimeController | None = None) -> None:
        self._settings = settings
        self._controller = controller or controller_from_settings(settings)

    def _index_dir(self, domain: Domain) -> Path:
        return self._controller.runtime_dir(domain.id, domain.runtime_instance_id) / "index"

    def _record_path(self, domain: Domain, request_id: str) -> Path:
        return self._index_dir(domain) / f"{_safe_request_id(request_id)}.json"

    def submit(self, domain: Domain, *, request_id: str, content_hash: str, rendered_text: str) -> IndexSubmitResult:
        if not self._controller.health(domain).healthy:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
        block_ids = _rendered_block_ids(rendered_text)
        if not block_ids:
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        record_path = self._record_path(domain, request_id)
        remote_id = _private_remote_id(request_id)
        if record_path.exists():
            try:
                existing = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc
            if existing.get("contentHash") != content_hash:
                raise SourceIndexError(409, "source_index_conflict", "Source index request conflict.")
            return IndexSubmitResult(remote_document_id=str(existing.get("remoteDocumentId") or remote_id))
        record = {
            "requestId": request_id,
            "contentHash": content_hash,
            "remoteDocumentId": remote_id,
            "blockIds": block_ids,
            "chunks": _rendered_hit_chunks(rendered_text),
            "status": "ready",
        }
        try:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc
        return IndexSubmitResult(remote_document_id=remote_id)

    def readiness(self, domain: Domain, *, request_id: str) -> IndexReadiness:
        if not self._controller.health(domain).healthy:
            return IndexReadiness(ready=False, failed=True, error_code="source_index_unavailable", error_message="Source index runtime unavailable.")
        record_path = self._record_path(domain, request_id)
        if not record_path.exists():
            return IndexReadiness(ready=False, failed=True, error_code="source_index_missing", error_message="Source index content is unavailable.")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return IndexReadiness(ready=False, failed=True, error_code="source_index_unavailable", error_message="Source index runtime unavailable.")
        if record.get("status") == "failed":
            return IndexReadiness(ready=False, failed=True, error_code="source_index_failed", error_message="Source index failed.")
        return IndexReadiness(ready=record.get("status") == "ready")

    def delete(self, domain: Domain, *, request_id: str) -> None:
        record_path = self._record_path(domain, request_id)
        try:
            if record_path.exists():
                record_path.unlink()
        except OSError as exc:
            raise _safe_error("source_index_delete_failed", "Source index content could not be removed.") from exc

    def is_absent(self, domain: Domain, *, request_id: str) -> bool:
        return not self._record_path(domain, request_id).exists()

    def retrieve(self, domain: Domain, *, question: str, deadline: float | None = None):
        from context_engine.services.evidence import ScopedRetrievalError

        if not question.strip() or not self._controller.health(domain).healthy:
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")
        if deadline is not None and time.monotonic() >= deadline:
            raise ScopedRetrievalError("retrieval_timeout", "Scoped retrieval timed out.")
        index_dir = self._index_dir(domain)
        if not index_dir.is_dir():
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")
        texts: list[str] = []
        try:
            record_paths = sorted(index_dir.glob("*.json"))
        except OSError as exc:
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.") from exc
        if not record_paths:
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")
        for record_path in record_paths:
            if len(texts) >= self._settings.retrieval_max_candidates:
                break
            if deadline is not None and time.monotonic() >= deadline:
                raise ScopedRetrievalError("retrieval_timeout", "Scoped retrieval timed out.")
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.") from exc
            if record.get("status") != "ready":
                continue
            chunks = record.get("chunks")
            if not isinstance(chunks, list):
                raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
            for chunk in chunks:
                if len(texts) >= self._settings.retrieval_max_candidates:
                    break
                if not isinstance(chunk, dict) or type(chunk.get("text")) is not str:
                    raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
                texts.append(chunk["text"])
        return _bounded_adapter_result(texts, self._settings)

    def preserved_block_ids(self, domain: Domain, *, request_id: str) -> tuple[str, ...]:
        record_path = self._record_path(domain, request_id)
        if not record_path.exists():
            return ()
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ()
        values = record.get("blockIds")
        if not isinstance(values, list):
            return ()
        return tuple(str(value) for value in values)


class LightRAGClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _working_dir(self, domain: Domain) -> Path:
        return Path(self._settings.domain_runtime_root) / domain.id / domain.runtime_instance_id / "lightrag"

    def _run(self, coro, *, deadline: float | None = None):
        # LightRAG 1.4.16 uses module-level shared storage state. Keep native
        # lifecycle calls process-serialized until per-domain concurrency is proven.
        timeout_seconds = max(1, int(self._settings.source_index_timeout_seconds))
        call_deadline = deadline or (time.monotonic() + timeout_seconds)
        remaining = call_deadline - time.monotonic()
        if remaining <= 0 or not _NATIVE_LIGHTRAG_LIFECYCLE_LOCK.acquire(timeout=remaining):
            if hasattr(coro, "close"):
                coro.close()
            raise SourceIndexError(504, "source_index_timeout", "Source index runtime timed out.")
        try:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                remaining = call_deadline - time.monotonic()
                if remaining <= 0:
                    if hasattr(coro, "close"):
                        coro.close()
                    raise TimeoutError
                task = loop.create_task(coro)
                done, _ = loop.run_until_complete(asyncio.wait({task}, timeout=remaining))
                if task not in done:
                    task.cancel()
                    raise TimeoutError
                return task.result()
            except TimeoutError as exc:
                raise SourceIndexError(504, "source_index_timeout", "Source index runtime timed out.") from exc
            finally:
                # Cleanup may consume only the original call budget. Closing the
                # private loop prevents a cancellation-resistant task from
                # retaining the process-global LightRAG lock after the deadline.
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.wait(pending, timeout=0))
                pending = [task for task in pending if not task.done()]
                remaining = call_deadline - time.monotonic()
                if pending and remaining > 0:
                    loop.run_until_complete(asyncio.wait(pending, timeout=remaining))
                remaining = call_deadline - time.monotonic()
                if remaining > 0:
                    shutdown_task = loop.create_task(loop.shutdown_asyncgens())
                    loop.run_until_complete(asyncio.wait({shutdown_task}, timeout=remaining))
                    if not shutdown_task.done():
                        shutdown_task.cancel()
                asyncio.set_event_loop(None)
                loop.close()
        finally:
            _NATIVE_LIGHTRAG_LIFECYCLE_LOCK.release()

    def _load_runtime(self):
        try:
            ensure_vendored_lightrag_import_path()
            import lightrag
            import numpy as np
            from lightrag import LightRAG
            from lightrag.base import DocStatus, QueryParam
            from lightrag.kg.shared_storage import (
                finalize_share_data,
                initialize_share_data,
            )
            from lightrag.utils import wrap_embedding_func_with_attrs

            assert_vendored_lightrag_loaded(lightrag)
        except Exception as exc:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc
        return {
            "DocStatus": DocStatus,
            "LightRAG": LightRAG,
            "QueryParam": QueryParam,
            "finalize_share_data": finalize_share_data,
            "initialize_share_data": initialize_share_data,
            "np": np,
            "wrap_embedding_func_with_attrs": wrap_embedding_func_with_attrs,
        }

    async def _new_rag(self, domain: Domain):
        runtime = self._load_runtime()
        runtime["initialize_share_data"](workers=1)
        np = runtime["np"]
        wrap_embedding_func_with_attrs = runtime["wrap_embedding_func_with_attrs"]

        @wrap_embedding_func_with_attrs(embedding_dim=8, max_token_size=256, model_name="ce-native-embedding")
        async def embed(texts, **_kwargs):
            return np.array(
                [[float((idx + len(text)) % 7) for idx in range(8)] for text in texts],
                dtype=np.float32,
            )

        async def llm(_prompt, system_prompt=None, history_messages=None, **_kwargs):
            return "synthetic entity"

        working_dir = self._working_dir(domain)
        working_dir.mkdir(parents=True, exist_ok=True)
        rag = runtime["LightRAG"](
            working_dir=str(working_dir),
            embedding_func=embed,
            llm_model_func=llm,
            chunk_token_size=256,
            chunk_overlap_token_size=0,
        )
        await rag.initialize_storages()
        return rag, runtime

    async def _close_rag(self, rag, runtime) -> None:
        try:
            await rag.finalize_storages()
        finally:
            runtime["finalize_share_data"]()

    def submit(self, domain: Domain, *, request_id: str, content_hash: str, rendered_text: str) -> IndexSubmitResult:
        _safe_request_id(request_id)
        if hashlib.sha256(rendered_text.encode("utf-8")).hexdigest() != content_hash:
            raise SourceIndexError(409, "source_index_conflict", "Source index request conflict.")
        if not _rendered_block_ids(rendered_text):
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")

        async def op() -> IndexSubmitResult:
            rag, runtime = await self._new_rag(domain)
            try:
                returned = await rag.ainsert(
                    rendered_text,
                    ids=request_id,
                    file_paths=f"{request_id}.ce-source",
                    track_id=request_id,
                )
            finally:
                await self._close_rag(rag, runtime)
            if returned not in {None, request_id}:
                raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
            return IndexSubmitResult(remote_document_id=_private_remote_id(request_id))

        try:
            return self._run(op())
        except SourceIndexError:
            raise
        except Exception as exc:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc

    def readiness(self, domain: Domain, *, request_id: str) -> IndexReadiness:
        _safe_request_id(request_id)

        async def op() -> IndexReadiness:
            rag, runtime = await self._new_rag(domain)
            try:
                status = await rag.doc_status.get_by_id(request_id)
            finally:
                await self._close_rag(rag, runtime)
            if status is None:
                return IndexReadiness(
                    ready=False,
                    failed=True,
                    error_code="source_index_missing",
                    error_message="Source index content is unavailable.",
                )
            raw_status = status.get("status") if isinstance(status, dict) else getattr(status, "status", None)
            status_value = getattr(raw_status, "value", raw_status)
            if status_value == "failed":
                return IndexReadiness(
                    ready=False,
                    failed=True,
                    error_code="source_index_failed",
                    error_message="Source index failed.",
                )
            return IndexReadiness(ready=status_value == "processed")

        try:
            return self._run(op())
        except SourceIndexError as exc:
            return IndexReadiness(ready=False, failed=True, error_code=exc.code, error_message=exc.message)
        except Exception:  # noqa: BLE001 -- the dependency boundary must fail closed
            return IndexReadiness(
                ready=False,
                failed=True,
                error_code="source_index_unavailable",
                error_message="Source index runtime unavailable.",
            )

    def delete(self, domain: Domain, *, request_id: str) -> None:
        _safe_request_id(request_id)

        async def op() -> None:
            rag, runtime = await self._new_rag(domain)
            try:
                await rag.adelete_by_doc_id(request_id)
            finally:
                await self._close_rag(rag, runtime)

        try:
            self._run(op())
        except SourceIndexError:
            raise
        except Exception as exc:
            raise _safe_error("source_index_delete_failed", "Source index content could not be removed.") from exc

    def is_absent(self, domain: Domain, *, request_id: str) -> bool:
        _safe_request_id(request_id)

        async def op() -> bool:
            rag, runtime = await self._new_rag(domain)
            try:
                return await rag.doc_status.get_by_id(request_id) is None
            finally:
                await self._close_rag(rag, runtime)

        try:
            return bool(self._run(op()))
        except SourceIndexError:
            raise
        except Exception as exc:
            # Surface verification failures instead of reporting "still present",
            # which callers would misread as a failed delete.
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc

    def retrieve(self, domain: Domain, *, question: str, deadline: float | None = None):
        from context_engine.services.evidence import ScopedRetrievalError

        if not question.strip():
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")

        async def op():
            rag, runtime = await self._new_rag(domain)
            try:
                QueryParam = runtime["QueryParam"]
                result = await rag.aquery_data(question, QueryParam(mode="naive", top_k=10, chunk_top_k=10))
            finally:
                await self._close_rag(rag, runtime)
            if (
                isinstance(result, dict)
                and result.get("status") == "failure"
                and isinstance(result.get("metadata"), dict)
                and result["metadata"].get("failure_reason") == "no_results"
            ):
                return _bounded_adapter_result((), self._settings)
            if not isinstance(result, dict):
                raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
            status = result.get("status")
            if status == "failure":
                raise ScopedRetrievalError(
                    "retrieval_malformed",
                    "Scoped retrieval returned an invalid result.",
                )
            if status != "success":
                raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
            data = result.get("data")
            if not isinstance(data, dict):
                raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
            chunks = data.get("chunks")
            if not isinstance(chunks, list):
                raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
            texts: list[str] = []
            raw_bytes = 0
            for chunk in chunks:
                if not isinstance(chunk, dict) or type(chunk.get("content")) is not str:
                    raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
                raw_bytes += len(chunk["content"].encode("utf-8"))
                if raw_bytes > self._settings.retrieval_max_aggregate_bytes:
                    raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
                for rendered_chunk in _rendered_hit_chunks(chunk["content"]):
                    texts.append(rendered_chunk["text"])
                    if len(texts) >= self._settings.retrieval_max_candidates:
                        break
                if len(texts) >= self._settings.retrieval_max_candidates:
                    break
            return _bounded_adapter_result(texts, self._settings)

        try:
            return self._run(op(), deadline=deadline)
        except SourceIndexError as exc:
            code = "retrieval_timeout" if exc.code == "source_index_timeout" else "retrieval_unavailable"
            message = "Scoped retrieval timed out." if code == "retrieval_timeout" else "Scoped retrieval is unavailable."
            raise ScopedRetrievalError(code, message) from exc
        except ScopedRetrievalError:
            raise
        except Exception as exc:
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.") from exc

    def preserved_block_ids(self, domain: Domain, *, request_id: str) -> tuple[str, ...]:
        _safe_request_id(request_id)

        async def op() -> tuple[str, ...]:
            rag, runtime = await self._new_rag(domain)
            try:
                status = await rag.doc_status.get_by_id(request_id)
                if status is None:
                    return ()
                chunk_ids = status.get("chunks_list") if isinstance(status, dict) else getattr(status, "chunks_list", None)
                if not chunk_ids:
                    return ()
                chunks = await rag.text_chunks.get_by_ids(list(chunk_ids))
            finally:
                await self._close_rag(rag, runtime)
            block_ids: list[str] = []
            for chunk in chunks:
                if isinstance(chunk, dict) and isinstance(chunk.get("content"), str):
                    block_ids.extend(_rendered_block_ids(chunk["content"]))
            return tuple(block_ids)

        try:
            return self._run(op())
        except Exception:  # noqa: BLE001 -- this optional proof must fail closed
            return ()


def index_client_from_settings(settings: Settings, controller: DomainRuntimeController | None = None) -> LightRAGClientProtocol:
    kind = settings.lightrag_client_kind.strip().lower()
    if kind == "native":
        return LightRAGClient(settings)
    if kind == "local":
        return LocalLightRAGIndexClient(settings, controller)
    raise SourceIndexError(502, "source_index_unavailable", "Source index runtime unavailable.")


def _remote_delete_required(source: SourceDocument) -> bool:
    return bool(source.index_request_id and (source.index_state in SOURCE_INDEX_REMOTE_STATES or source.index_remote_document_id))


def _delete_remote_if_needed(
    db: Session,
    settings: Settings,
    source: SourceDocument,
    request_id: str | None,
    client: LightRAGClientProtocol | None = None,
) -> None:
    if not request_id:
        return
    domain = db.get(Domain, source.domain_id)
    if domain is None:
        return
    client = client or index_client_from_settings(settings)
    client.delete(domain, request_id=request_id)
    if not client.is_absent(domain, request_id=request_id):
        raise SourceIndexError(502, "source_index_delete_failed", "Source index content could not be removed.")


def retry_source_index(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    source_id: str,
    client: LightRAGClientProtocol | None = None,
    audit_context: AuditContext | None = None,
) -> SourceDocument:
    _domain_or_404(db, domain_id)
    source = _source_or_404(db, domain_id, source_id)
    if source.state != SOURCE_STATE_PREPARED:
        raise SourceIndexError(409, "source_state_conflict", "Source state does not allow this operation.")
    if source.index_state in {SOURCE_INDEX_STATE_QUEUED, SOURCE_INDEX_STATE_SUBMITTING, SOURCE_INDEX_STATE_CANCELLING}:
        raise SourceIndexError(409, "source_index_in_progress", "Source indexing is already in progress.")

    old_request_id = source.index_request_id
    if _remote_delete_required(source):
        _delete_remote_if_needed(db, settings, source, old_request_id, client)

    def mutate() -> SourceDocument:
        _queue_new_generation(db, source)
        return source

    if audit_context is not None:
        source = commit_protected_mutation(
            db,
            mutate,
            event_name=AUDIT_EVENT_SOURCE_INDEX_RETRY_QUEUED,
            context=audit_context,
            target_kind="source_document",
            target_id=source.id,
            metadata={"indexState": SOURCE_INDEX_STATE_QUEUED},
        )
    else:
        mutate()
        db.commit()
    db.refresh(source)
    return source


def cancel_source_index(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    source_id: str,
    client: LightRAGClientProtocol | None = None,
    audit_context: AuditContext | None = None,
) -> SourceDocument:
    _domain_or_404(db, domain_id)
    source = _source_or_404(db, domain_id, source_id)
    if source.state != SOURCE_STATE_PREPARED:
        raise SourceIndexError(409, "source_state_conflict", "Source state does not allow this operation.")
    if source.index_state in {SOURCE_INDEX_STATE_NOT_REQUESTED, SOURCE_INDEX_STATE_CANCELLED}:
        raise SourceIndexError(409, "source_state_conflict", "Source state does not allow this operation.")

    old_request_id = source.index_request_id
    needs_remote_delete = _remote_delete_required(source) or source.index_state == SOURCE_INDEX_STATE_SUBMITTING
    now = utc_now()
    source.index_generation += 1
    source.index_state = SOURCE_INDEX_STATE_CANCELLING
    source.index_error_code = None
    source.index_error_message = None
    source.index_lease_owner = None
    source.index_lease_expires_at = None
    source.index_updated_at = now
    source.updated_at = now
    source.version += 1
    db.commit()
    db.refresh(source)

    try:
        if needs_remote_delete:
            _delete_remote_if_needed(db, settings, source, old_request_id, client)
    except SourceIndexError:
        current = db.get(SourceDocument, source.id)
        if current is not None:
            current.index_error_code = "source_index_delete_failed"
            current.index_error_message = "Source index content could not be removed."
            current.index_updated_at = utc_now()
            db.commit()
        raise

    def mutate_cancelled() -> SourceDocument:
        source.index_state = SOURCE_INDEX_STATE_CANCELLED
        source.index_request_id = None
        source.index_content_hash = None
        source.index_remote_document_id = None
        source.index_accepted_at = None
        source.index_ready_at = None
        source.index_updated_at = utc_now()
        source.updated_at = source.index_updated_at
        source.version += 1
        return source

    if audit_context is not None:
        source = commit_protected_mutation(
            db,
            mutate_cancelled,
            event_name=AUDIT_EVENT_SOURCE_INDEX_CANCELLED,
            context=audit_context,
            target_kind="source_document",
            target_id=source.id,
            metadata={"indexState": SOURCE_INDEX_STATE_CANCELLED},
        )
    else:
        mutate_cancelled()
        db.commit()
    db.refresh(source)
    return source


def cleanup_index_before_source_delete(
    db: Session,
    *,
    settings: Settings,
    source: SourceDocument,
    client: LightRAGClientProtocol | None = None,
) -> None:
    old_request_id = source.index_request_id
    needs_remote_delete = _remote_delete_required(source) or source.index_state == SOURCE_INDEX_STATE_SUBMITTING
    if source.index_state not in {SOURCE_INDEX_STATE_NOT_REQUESTED, SOURCE_INDEX_STATE_CANCELLED}:
        now = utc_now()
        source.index_generation += 1
        source.index_state = SOURCE_INDEX_STATE_CANCELLING if needs_remote_delete else SOURCE_INDEX_STATE_CANCELLED
        source.index_error_code = None
        source.index_error_message = None
        source.index_lease_owner = None
        source.index_lease_expires_at = None
        source.index_updated_at = now
        source.updated_at = now
        db.commit()
        db.refresh(source)

    try:
        if needs_remote_delete:
            _delete_remote_if_needed(db, settings, source, old_request_id, client)
    except SourceIndexError:
        current = db.get(SourceDocument, source.id)
        if current is not None:
            current.index_error_code = "source_index_delete_failed"
            current.index_error_message = "Source index content could not be removed."
            current.index_updated_at = utc_now()
            db.commit()
        raise

    if source.index_state != SOURCE_INDEX_STATE_CANCELLED:
        source.index_state = SOURCE_INDEX_STATE_CANCELLED
        source.index_request_id = None
        source.index_content_hash = None
        source.index_remote_document_id = None
        source.index_accepted_at = None
        source.index_ready_at = None
        source.index_updated_at = utc_now()
        source.updated_at = source.index_updated_at
        db.commit()
        db.refresh(source)


def _worker_result_is_current(source: SourceDocument, generation: int, request_id: str) -> bool:
    return (
        source.index_generation == generation
        and source.index_request_id == request_id
        and source.state == SOURCE_STATE_PREPARED
        and source.index_state not in {SOURCE_INDEX_STATE_CANCELLING, SOURCE_INDEX_STATE_CANCELLED}
    )


def _lease_heartbeat_seconds(lease_seconds: int) -> int:
    return max(1, lease_seconds // 3)


def _index_lease_current(
    source: SourceDocument,
    *,
    owner: str,
    now=None,
) -> bool:
    current = now or utc_now()
    if source.index_lease_owner != owner:
        return False
    return source.index_lease_expires_at is not None and source.index_lease_expires_at >= current


def _heartbeat_index_lease(
    db: Session,
    source: SourceDocument,
    *,
    owner: str,
    lease_seconds: int,
    now=None,
) -> bool:
    current = now or utc_now()
    db.refresh(source)
    if not _index_lease_current(source, owner=owner, now=current):
        return False
    if source.index_state in {SOURCE_INDEX_STATE_CANCELLING, SOURCE_INDEX_STATE_CANCELLED}:
        return False
    source.index_lease_expires_at = current + timedelta(seconds=lease_seconds)
    source.index_updated_at = current
    source.updated_at = current
    db.commit()
    db.refresh(source)
    return True


def schedule_index_poll_backoff(
    db: Session,
    *,
    source_id: str,
    generation: int,
    request_id: str,
    backoff_seconds: int,
) -> bool:
    """Persist not-ready poll backoff via lease-expiry gating (DRIFT-28)."""
    source = db.get(SourceDocument, source_id)
    if source is None or not _worker_result_is_current(source, generation, request_id):
        return False
    if source.index_state not in {SOURCE_INDEX_STATE_SUBMITTING, SOURCE_INDEX_STATE_ACCEPTED}:
        return False
    now = utc_now()
    source.index_lease_owner = None
    source.index_lease_expires_at = now + timedelta(seconds=max(1, backoff_seconds))
    source.index_updated_at = now
    source.updated_at = now
    db.commit()
    return True


def mark_index_accepted_if_current(
    db: Session,
    *,
    source_id: str,
    generation: int,
    request_id: str,
    remote_document_id: str,
) -> bool:
    source = db.get(SourceDocument, source_id)
    if source is None or source.index_state != SOURCE_INDEX_STATE_SUBMITTING or not _worker_result_is_current(source, generation, request_id):
        return False
    now = utc_now()
    source.index_state = SOURCE_INDEX_STATE_ACCEPTED
    source.index_remote_document_id = remote_document_id
    source.index_error_code = None
    source.index_error_message = None
    source.index_accepted_at = now
    source.index_ready_at = None
    source.index_lease_owner = None
    source.index_lease_expires_at = None
    source.index_updated_at = now
    source.updated_at = now
    source.version += 1
    db.commit()
    return True


def mark_index_ready_if_current(db: Session, *, source_id: str, generation: int, request_id: str) -> bool:
    source = db.get(SourceDocument, source_id)
    if source is None or source.index_state != SOURCE_INDEX_STATE_ACCEPTED or not _worker_result_is_current(source, generation, request_id):
        return False
    now = utc_now()
    source.index_state = SOURCE_INDEX_STATE_READY
    source.index_error_code = None
    source.index_error_message = None
    source.index_ready_at = now
    source.index_lease_owner = None
    source.index_lease_expires_at = None
    source.index_updated_at = now
    source.updated_at = now
    source.version += 1
    db.commit()
    return True


def mark_index_failed_if_current(db: Session, *, source_id: str, generation: int, request_id: str, code: str, message: str) -> bool:
    source = db.get(SourceDocument, source_id)
    if source is None or not _worker_result_is_current(source, generation, request_id):
        return False
    now = utc_now()
    source.index_state = SOURCE_INDEX_STATE_FAILED
    source.index_error_code = code
    source.index_error_message = message
    source.index_lease_owner = None
    source.index_lease_expires_at = None
    source.index_updated_at = now
    source.updated_at = now
    source.version += 1
    db.commit()
    return True


def mark_index_uncertain_if_current(
    db: Session,
    *,
    source_id: str,
    generation: int,
    request_id: str,
    backoff_seconds: int,
    message: str = "Source index runtime outcome uncertain; reconciliation required.",
) -> bool:
    """Leave submitting non-terminal after unknown remote timeout (DRIFT-32)."""
    source = db.get(SourceDocument, source_id)
    if source is None or source.index_state != SOURCE_INDEX_STATE_SUBMITTING or not _worker_result_is_current(source, generation, request_id):
        return False
    now = utc_now()
    source.index_error_code = SOURCE_INDEX_UNCERTAIN_CODE
    source.index_error_message = message
    source.index_lease_owner = None
    source.index_lease_expires_at = now + timedelta(seconds=max(1, backoff_seconds))
    source.index_updated_at = now
    source.updated_at = now
    db.commit()
    return True


class SourceIndexWorker:
    def __init__(self, settings: Settings, client: LightRAGClientProtocol | None = None) -> None:
        self._settings = settings
        self._client = client or index_client_from_settings(settings)

    def run_once(self, db: Session) -> bool:
        source = self._claim_next_source(db)
        if source is None:
            return False
        domain = db.get(Domain, source.domain_id)
        if domain is None:
            return True
        generation = source.index_generation
        request_id = source.index_request_id
        owner = self._settings.source_index_worker_id
        lease_seconds = self._settings.source_index_lease_seconds
        backoff_seconds = self._settings.source_index_poll_backoff_seconds
        if not request_id:
            # Without a request id the submission can never progress; fail the
            # source instead of leaving it SUBMITTING until the lease expires.
            now = utc_now()
            source.index_state = SOURCE_INDEX_STATE_FAILED
            source.index_error_code = "source_index_request_missing"
            source.index_error_message = "Source index request id is missing."
            source.index_lease_owner = None
            source.index_lease_expires_at = None
            source.index_updated_at = now
            source.updated_at = now
            db.commit()
            return True

        if source.index_state == SOURCE_INDEX_STATE_SUBMITTING:
            return self._run_submitting(
                db,
                source=source,
                domain=domain,
                generation=generation,
                request_id=request_id,
                owner=owner,
                lease_seconds=lease_seconds,
                backoff_seconds=backoff_seconds,
            )

        if source.index_state == SOURCE_INDEX_STATE_ACCEPTED:
            return self._run_accepted(
                db,
                source=source,
                domain=domain,
                generation=generation,
                request_id=request_id,
                owner=owner,
                lease_seconds=lease_seconds,
                backoff_seconds=backoff_seconds,
            )

        return True

    def _run_submitting(
        self,
        db: Session,
        *,
        source: SourceDocument,
        domain: Domain,
        generation: int,
        request_id: str,
        owner: str,
        lease_seconds: int,
        backoff_seconds: int,
    ) -> bool:
        if not _heartbeat_index_lease(db, source, owner=owner, lease_seconds=lease_seconds):
            return True

        # Probe first: timeout/reclaim may have already landed the remote handoff.
        readiness = self._client.readiness(domain, request_id=request_id)
        if readiness.ready:
            remote_id = source.index_remote_document_id or _private_remote_id(request_id)
            if mark_index_accepted_if_current(
                db,
                source_id=source.id,
                generation=generation,
                request_id=request_id,
                remote_document_id=remote_id,
            ):
                mark_index_ready_if_current(db, source_id=source.id, generation=generation, request_id=request_id)
            return True
        if not readiness.failed:
            remote_id = source.index_remote_document_id or _private_remote_id(request_id)
            mark_index_accepted_if_current(
                db,
                source_id=source.id,
                generation=generation,
                request_id=request_id,
                remote_document_id=remote_id,
            )
            return True
        if readiness.error_code not in {None, "source_index_missing"}:
            mark_index_failed_if_current(
                db,
                source_id=source.id,
                generation=generation,
                request_id=request_id,
                code=readiness.error_code or "source_index_failed",
                message=readiness.error_message or "Source index failed.",
            )
            return True

        try:
            result = self._submit_with_lease_heartbeat(
                db,
                source_id=source.id,
                domain=domain,
                request_id=request_id,
                owner=owner,
                lease_seconds=lease_seconds,
            )
        except SourceIndexError as exc:
            db.rollback()
            if exc.code == "source_index_timeout":
                mark_index_uncertain_if_current(
                    db,
                    source_id=source.id,
                    generation=generation,
                    request_id=request_id,
                    backoff_seconds=backoff_seconds,
                    message=exc.message,
                )
            else:
                mark_index_failed_if_current(
                    db,
                    source_id=source.id,
                    generation=generation,
                    request_id=request_id,
                    code=exc.code,
                    message=exc.message,
                )
            return True
        if result is None:
            return True
        mark_index_accepted_if_current(
            db,
            source_id=source.id,
            generation=generation,
            request_id=request_id,
            remote_document_id=result.remote_document_id,
        )
        return True

    def _run_accepted(
        self,
        db: Session,
        *,
        source: SourceDocument,
        domain: Domain,
        generation: int,
        request_id: str,
        owner: str,
        lease_seconds: int,
        backoff_seconds: int,
    ) -> bool:
        if not _heartbeat_index_lease(db, source, owner=owner, lease_seconds=lease_seconds):
            return True
        readiness = self._client.readiness(domain, request_id=request_id)
        if readiness.failed:
            mark_index_failed_if_current(
                db,
                source_id=source.id,
                generation=generation,
                request_id=request_id,
                code=readiness.error_code or "source_index_failed",
                message=readiness.error_message or "Source index failed.",
            )
        elif readiness.ready:
            mark_index_ready_if_current(db, source_id=source.id, generation=generation, request_id=request_id)
        else:
            schedule_index_poll_backoff(
                db,
                source_id=source.id,
                generation=generation,
                request_id=request_id,
                backoff_seconds=backoff_seconds,
            )
        return True

    def _submit_with_lease_heartbeat(
        self,
        db: Session,
        *,
        source_id: str,
        domain: Domain,
        request_id: str,
        owner: str,
        lease_seconds: int,
    ) -> IndexSubmitResult | None:
        source = db.get(SourceDocument, source_id)
        if source is None:
            return None
        rendered = render_lightrag_input(db, source)
        if rendered.content_hash != source.index_content_hash:
            raise SourceIndexError(409, "source_index_conflict", "Source index request conflict.")

        from context_engine.db import create_db_engine, create_session_factory

        stop = threading.Event()
        lost = threading.Event()
        heartbeat_seconds = _lease_heartbeat_seconds(lease_seconds)
        engine = create_db_engine(self._settings)
        session_factory = create_session_factory(engine)

        def _beat() -> None:
            while not stop.wait(heartbeat_seconds):
                with session_factory() as beat_db:
                    current = beat_db.get(SourceDocument, source_id)
                    if current is None or not _heartbeat_index_lease(
                        beat_db,
                        current,
                        owner=owner,
                        lease_seconds=lease_seconds,
                    ):
                        lost.set()
                        return

        thread = threading.Thread(target=_beat, name="source-index-lease-heartbeat", daemon=True)
        thread.start()
        try:
            result = self._client.submit(
                domain,
                request_id=request_id,
                content_hash=rendered.content_hash,
                rendered_text=rendered.text,
            )
        finally:
            stop.set()
            thread.join(timeout=max(1, heartbeat_seconds))
            engine.dispose()
        if lost.is_set():
            return None
        return result

    def _claim_next_source(self, db: Session) -> SourceDocument | None:
        now = utc_now()
        lease_expired = SourceDocument.index_lease_expires_at.is_not(None) & (
            SourceDocument.index_lease_expires_at < now
        )
        source = db.scalar(
            select(SourceDocument)
            .where(
                SourceDocument.state == SOURCE_STATE_PREPARED,
                or_(
                    SourceDocument.index_state == SOURCE_INDEX_STATE_QUEUED,
                    (SourceDocument.index_state == SOURCE_INDEX_STATE_SUBMITTING) & lease_expired,
                    (
                        (SourceDocument.index_state == SOURCE_INDEX_STATE_ACCEPTED)
                        & or_(SourceDocument.index_lease_expires_at.is_(None), lease_expired)
                    ),
                ),
            )
            .order_by(SourceDocument.index_updated_at, SourceDocument.created_at, SourceDocument.id)
            # Row lock prevents double-claim across worker processes on Postgres;
            # SQLAlchemy's SQLite dialect ignores FOR UPDATE, so dev/tests are unaffected.
            .with_for_update(skip_locked=True)
        )
        if source is None:
            return None
        if source.index_state == SOURCE_INDEX_STATE_QUEUED:
            source.index_state = SOURCE_INDEX_STATE_SUBMITTING
            source.index_error_code = None
            source.index_error_message = None
            source.version += 1
        source.index_lease_owner = self._settings.source_index_worker_id
        source.index_lease_expires_at = now + timedelta(seconds=self._settings.source_index_lease_seconds)
        source.index_updated_at = now
        source.updated_at = now
        db.commit()
        db.refresh(source)
        safe_log(
            logger,
            "source_index_worker.claimed",
            domain_id=source.domain_id,
            source_id=source.id,
            index_request_id=source.index_request_id,
            outcome="succeeded",
        )
        safe_increment(
            "worker_operation",
            operation_type="source_index",
            outcome="succeeded",
        )
        return source


def source_is_query_eligible(
    db: Session,
    source: SourceDocument,
    domain: Domain,
    *,
    settings: Settings | None = None,
    controller: DomainRuntimeController | None = None,
) -> bool:
    controller = controller or (controller_from_settings(settings) if settings is not None else None)
    if controller is None or not domain_available(db, domain, controller):
        return False
    if source.domain_id != domain.id or source.state != SOURCE_STATE_PREPARED:
        return False
    if source.index_state != SOURCE_INDEX_STATE_READY:
        return False
    return source_has_current_index_identity(source)
