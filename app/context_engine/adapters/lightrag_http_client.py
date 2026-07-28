"""Private HTTP LightRAG client for per-domain Docker runtimes (production path)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from context_engine.config import Settings
    from context_engine.models import Domain
    from context_engine.services.indexing import IndexReadiness, IndexSubmitResult


@dataclass(frozen=True)
class HttpTransportResponse:
    status_code: int
    body: bytes


class LightRAGHttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float,
    ) -> HttpTransportResponse: ...


class UrllibLightRAGHttpTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float,
    ) -> HttpTransportResponse:
        data = None if json_body is None else json.dumps(json_body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)  # noqa: S310
        try:
            with urlopen(req, timeout=timeout) as response:  # noqa: S310 — private runtime only
                return HttpTransportResponse(status_code=int(response.status), body=response.read())
        except HTTPError as exc:
            body = exc.read() if hasattr(exc, "read") else b""
            return HttpTransportResponse(status_code=int(exc.code), body=body or b"")


class PrivateHttpLightRAGClient:
    """Production native client: private HTTP to one domain container."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: LightRAGHttpTransport | None = None,
        embedding_dimensions: int | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport or UrllibLightRAGHttpTransport()
        self._embedding_dimensions = embedding_dimensions

    def _runtime_dir(self, domain: Domain) -> Path:
        return Path(self._settings.domain_runtime_root) / domain.id / domain.runtime_instance_id

    def _base_url(self, domain: Domain) -> str:
        from context_engine.services.indexing import _safe_error

        endpoint_path = self._runtime_dir(domain) / "endpoint.json"
        if endpoint_path.is_file():
            try:
                payload = json.loads(endpoint_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc
            base = payload.get("baseUrl") if isinstance(payload, dict) else None
            if isinstance(base, str) and base.startswith("http://"):
                return base.rstrip("/")
        port = int(self._settings.domain_lightrag_port)
        name = f"ce_domain_{domain.id}_{domain.runtime_instance_id[:12]}"
        return f"http://{name}:{port}"

    def _timeout(self) -> float:
        return float(max(1, int(self._settings.source_index_timeout_seconds)))

    def _call(
        self,
        domain: Domain,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        deadline: float | None = None,
    ) -> HttpTransportResponse:
        from context_engine.services.indexing import SourceIndexError, _safe_error

        remaining = self._timeout() if deadline is None else max(0.1, deadline - time.monotonic())
        if remaining <= 0:
            raise SourceIndexError(504, "source_index_timeout", "Source index runtime timed out.")
        url = f"{self._base_url(domain)}{path}"
        try:
            return self._transport.request(method, url, json_body=json_body, timeout=remaining)
        except TimeoutError as exc:
            raise SourceIndexError(504, "source_index_timeout", "Source index runtime timed out.") from exc
        except URLError as exc:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc

    def _parse_json(self, body: bytes) -> dict[str, Any]:
        from context_engine.services.indexing import _safe_error

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.") from exc
        if not isinstance(payload, dict):
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
        return payload

    def submit(self, domain: Domain, *, request_id: str, content_hash: str, rendered_text: str) -> IndexSubmitResult:
        from context_engine.services.indexing import (
            IndexSubmitResult,
            SourceIndexError,
            _private_remote_id,
            _rendered_block_ids,
            _safe_error,
            _safe_request_id,
        )

        _safe_request_id(request_id)
        if self._embedding_dimensions is not None and self._embedding_dimensions < 1:
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        if hashlib.sha256(rendered_text.encode("utf-8")).hexdigest() != content_hash:
            raise SourceIndexError(409, "source_index_conflict", "Source index request conflict.")
        if not _rendered_block_ids(rendered_text):
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        response = self._call(
            domain,
            "POST",
            "/v1/index/submit",
            json_body={
                "request_id": request_id,
                "content_hash": content_hash,
                "rendered_text": rendered_text,
            },
        )
        if response.status_code == 409:
            raise SourceIndexError(409, "source_index_conflict", "Source index request conflict.")
        if response.status_code == 422:
            raise SourceIndexError(422, "source_index_input_invalid", "Source cannot be indexed.")
        if response.status_code >= 400:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
        payload = self._parse_json(response.body)
        remote = payload.get("remote_document_id")
        if not isinstance(remote, str) or not remote:
            remote = _private_remote_id(request_id)
        return IndexSubmitResult(remote_document_id=remote)

    def readiness(self, domain: Domain, *, request_id: str) -> IndexReadiness:
        from context_engine.services.indexing import IndexReadiness, SourceIndexError, _safe_request_id

        _safe_request_id(request_id)
        try:
            response = self._call(domain, "GET", f"/v1/index/readiness/{request_id}")
        except SourceIndexError as exc:
            return IndexReadiness(ready=False, failed=True, error_code=exc.code, error_message=exc.message)
        except Exception:  # noqa: BLE001
            return IndexReadiness(
                ready=False,
                failed=True,
                error_code="source_index_unavailable",
                error_message="Source index runtime unavailable.",
            )
        if response.status_code >= 400:
            return IndexReadiness(
                ready=False,
                failed=True,
                error_code="source_index_unavailable",
                error_message="Source index runtime unavailable.",
            )
        payload = self._parse_json(response.body)
        return IndexReadiness(
            ready=payload.get("ready") is True,
            failed=payload.get("failed") is True,
            error_code=payload.get("error_code") if isinstance(payload.get("error_code"), str) else None,
            error_message=payload.get("error_message") if isinstance(payload.get("error_message"), str) else None,
        )

    def delete(self, domain: Domain, *, request_id: str) -> None:
        from context_engine.services.indexing import _safe_error, _safe_request_id

        _safe_request_id(request_id)
        response = self._call(domain, "DELETE", f"/v1/index/{request_id}")
        if response.status_code >= 400:
            raise _safe_error("source_index_delete_failed", "Source index content could not be removed.")

    def is_absent(self, domain: Domain, *, request_id: str) -> bool:
        from context_engine.services.indexing import _safe_error, _safe_request_id

        _safe_request_id(request_id)
        response = self._call(domain, "GET", f"/v1/index/{request_id}/absent")
        if response.status_code >= 400:
            raise _safe_error("source_index_unavailable", "Source index runtime unavailable.")
        payload = self._parse_json(response.body)
        return payload.get("absent") is True

    def retrieve(self, domain: Domain, *, question: str, deadline: float | None = None):
        from context_engine.services.evidence import ScopedRetrievalError
        from context_engine.services.indexing import (
            SourceIndexError,
            _bounded_adapter_result,
            _rendered_hit_chunks,
        )

        if not question.strip():
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")
        try:
            response = self._call(
                domain,
                "POST",
                "/v1/retrieve",
                json_body={"question": question},
                deadline=deadline,
            )
        except SourceIndexError as exc:
            code = "retrieval_timeout" if exc.code == "source_index_timeout" else "retrieval_unavailable"
            message = "Scoped retrieval timed out." if code == "retrieval_timeout" else "Scoped retrieval is unavailable."
            raise ScopedRetrievalError(code, message) from exc
        if response.status_code >= 400:
            raise ScopedRetrievalError("retrieval_unavailable", "Scoped retrieval is unavailable.")
        result = self._parse_json(response.body)
        if (
            result.get("status") == "failure"
            and isinstance(result.get("metadata"), dict)
            and result["metadata"].get("failure_reason") == "no_results"
        ):
            return _bounded_adapter_result((), self._settings)
        if result.get("status") != "success":
            raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
        data = result.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("chunks"), list):
            raise ScopedRetrievalError("retrieval_malformed", "Scoped retrieval returned an invalid result.")
        texts: list[str] = []
        raw_bytes = 0
        for chunk in data["chunks"]:
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

    def preserved_block_ids(self, domain: Domain, *, request_id: str) -> tuple[str, ...]:
        return ()
