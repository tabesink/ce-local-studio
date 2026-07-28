"""Private parser execution helpers: killable Docling and bounded Reducto I/O.

These helpers never authorize, commit product state, or return provider URLs
into PreparedSource. They exist so hung local converts and URL-pointer results
cannot retain prep leases or leak private links.
"""

from __future__ import annotations

import base64
import json
import multiprocessing as mp
import os
import tempfile
from pathlib import Path
from typing import Any

_MAX_REDUCTO_ASSET_BYTES = 10 * 1024 * 1024


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _revive_bytes(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {"__bytes_b64__"} and isinstance(value["__bytes_b64__"], str):
            return base64.b64decode(value["__bytes_b64__"])
        return {key: _revive_bytes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_revive_bytes(item) for item in value]
    return value


def _adapter_error(code: str, message: str, status_code: int):
    from context_engine.adapters.parsers import ParserAdapterError

    return ParserAdapterError(code, message, status_code)


def _is_adapter_error(exc: BaseException) -> bool:
    from context_engine.adapters.parsers import ParserAdapterError

    return isinstance(exc, ParserAdapterError)


def _docling_worker(temp_path: str, out_path: str, filename: str | None) -> None:
    """Child process entry: convert then write a JSON payload path."""
    del filename
    try:
        from context_engine.adapters.parsers import (
            ParserAdapterError as _PAE,
            _docling_payload_from_document,
        )
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

        converter = DocumentConverter()
        result = converter.convert(temp_path)
        document = getattr(result, "document", result)
        payload = _docling_payload_from_document(document)
        Path(out_path).write_text(json.dumps(payload, default=_json_default), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - boundary maps in parent
        err = {
            "code": "parser_unavailable",
            "message": "Parser failed.",
            "status_code": 502,
        }
        if isinstance(exc, _PAE):
            err = {"code": exc.code, "message": exc.message, "status_code": exc.status_code}
        elif isinstance(exc, ImportError):
            err = {"code": "parser_unavailable", "message": "Parser is not available.", "status_code": 503}
        elif isinstance(exc, TimeoutError):
            err = {"code": "parser_timeout", "message": "Parser timed out.", "status_code": 504}
        Path(out_path).write_text(json.dumps({"__parser_error__": err}), encoding="utf-8")


def run_docling_convert_killable(
    original_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run Docling in a killable child process with a hard wall-clock deadline."""
    del content_type
    if timeout_seconds <= 0:
        raise _adapter_error("parser_unavailable", "Parser failed.", 502)

    suffix = Path(filename or "source.bin").suffix or ".bin"
    fd, temp_name = tempfile.mkstemp(suffix=suffix)
    out_fd, out_name = tempfile.mkstemp(suffix=".json")
    os.close(out_fd)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(original_bytes)

        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_docling_worker, args=(temp_name, out_name, filename), daemon=True)
        proc.start()
        proc.join(timeout_seconds)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
                proc.join(1)
            raise _adapter_error("parser_timeout", "Parser timed out.", 504)

        if proc.exitcode not in (0, None) and not Path(out_name).stat().st_size:
            raise _adapter_error("parser_unavailable", "Parser failed.", 502)

        raw = Path(out_name).read_text(encoding="utf-8")
        if not raw.strip():
            raise _adapter_error("parser_unavailable", "Parser failed.", 502)
        payload = _revive_bytes(json.loads(raw))
        if not isinstance(payload, dict):
            raise _adapter_error("parser_malformed_response", "Parser response could not be normalized.", 502)
        err = payload.get("__parser_error__")
        if isinstance(err, dict):
            raise _adapter_error(
                str(err.get("code") or "parser_unavailable"),
                str(err.get("message") or "Parser failed."),
                int(err.get("status_code") or 502),
            )
        return payload
    except Exception as exc:
        if _is_adapter_error(exc):
            raise
        if isinstance(exc, json.JSONDecodeError):
            raise _adapter_error(
                "parser_malformed_response",
                "Parser response could not be normalized.",
                502,
            ) from exc
        raise _adapter_error("parser_unavailable", "Parser failed.", 502) from exc
    finally:
        for path in (temp_name, out_name):
            try:
                os.unlink(path)
            except OSError:
                pass


def _httpx_get_bytes(url: str, *, timeout_seconds: float, max_bytes: int) -> bytes:
    try:
        import httpx
    except ImportError as exc:
        raise _adapter_error("parser_unavailable", "Parser is not available.", 503) from exc

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                if response.status_code in {401, 403}:
                    raise _adapter_error("parser_not_ready", "Parser is not configured.", 409)
                if response.status_code >= 400:
                    raise _adapter_error("parser_unavailable", "Parser failed.", 502)
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise _adapter_error(
                            "parser_malformed_response",
                            "Parser response could not be normalized.",
                            502,
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
    except Exception as exc:
        if _is_adapter_error(exc):
            raise
        message = str(exc).lower()
        if "timeout" in message or "timed out" in message:
            raise _adapter_error("parser_timeout", "Parser timed out.", 504) from exc
        raise _adapter_error("parser_unavailable", "Parser failed.", 502) from exc


def _httpx_get_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    raw = _httpx_get_bytes(url, timeout_seconds=timeout_seconds, max_bytes=_MAX_REDUCTO_ASSET_BYTES * 5)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _adapter_error(
            "parser_malformed_response",
            "Parser response could not be normalized.",
            502,
        ) from exc
    if not isinstance(payload, dict):
        raise _adapter_error("parser_malformed_response", "Parser response could not be normalized.", 502)
    return payload


def _sniff_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return None


def resolve_reducto_url_result(payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    """Resolve type=url pointer results privately before normalization."""
    nested = payload.get("result")
    if not isinstance(nested, dict) or nested.get("type") != "url":
        return payload
    result_url = nested.get("url")
    if not isinstance(result_url, str) or not result_url.strip():
        raise _adapter_error("parser_malformed_response", "Parser response could not be normalized.", 502)
    fetched = _httpx_get_json(result_url.strip(), timeout_seconds=timeout_seconds)
    if isinstance(fetched.get("result"), dict):
        merged_result = dict(fetched["result"])
    elif isinstance(fetched.get("chunks"), list):
        merged_result = {"type": "full", "chunks": fetched["chunks"]}
    else:
        merged_result = dict(fetched)
    merged_result.pop("url", None)
    if merged_result.get("type") == "url":
        raise _adapter_error("parser_malformed_response", "Parser response could not be normalized.", 502)
    out = {key: value for key, value in payload.items() if key != "result"}
    out["result"] = merged_result
    out.pop("job_id", None)
    return out


def materialize_reducto_remote_assets(payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    """Download figure/table image URLs into bytes; strip URL fields before normalize."""
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    chunks = result.get("chunks")
    if not isinstance(chunks, list):
        return payload

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        blocks = chunk.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            image_url = block.get("image_url")
            if not isinstance(image_url, str) or not image_url.strip():
                block.pop("image_url", None)
                continue
            data = _httpx_get_bytes(
                image_url.strip(),
                timeout_seconds=timeout_seconds,
                max_bytes=_MAX_REDUCTO_ASSET_BYTES,
            )
            mime = _sniff_image_mime(data)
            if mime is None:
                raise _adapter_error(
                    "parser_malformed_response",
                    "Parser response could not be normalized.",
                    502,
                )
            block["image_bytes"] = data
            block["mime_type"] = mime
            block.pop("image_url", None)
            block.pop("job_id", None)
    return payload
