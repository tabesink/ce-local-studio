from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from context_engine.config import Settings
from context_engine.db import utc_now
from context_engine.models import DOMAIN_STATE_RUNNING, Domain
from context_engine.services.auth import iso_utc
from context_engine.services.domains import DomainRuntimeController, controller_from_settings

MAX_LIGHTRAG_DIAGNOSTIC_LINES = 200
MAX_LIGHTRAG_DIAGNOSTIC_BODY_BYTES = 64 * 1024
MAX_LIGHTRAG_DIAGNOSTIC_LINE_CHARS = 500
LIGHTRAG_DIAGNOSTIC_KIND = "lightrag"
LIGHTRAG_DIAGNOSTIC_FILENAME = "lightrag.log"

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+")
_FORBIDDEN_LINE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]:\\[^\s]+"),
    re.compile(r"(?<!\w)/(?:[^\s/]+/)+[^\s]+"),
    re.compile(
        r"secret|credential|provider payload|raw lightrag|prompt|user question|assistant answer|"
        r"source text|evidence excerpt|traceback|stack trace|storage path|runtime url",
        re.IGNORECASE,
    ),
)


class DiagnosticsError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class LightRAGDiagnostics:
    domain_id: str
    captured_at: str
    lines: list[str]
    truncated: bool

    @property
    def line_count(self) -> int:
        return len(self.lines)


def _domain_or_error(db: Session, domain_id: str) -> Domain:
    domain = db.get(Domain, domain_id)
    if domain is None:
        raise DiagnosticsError(404, "domain_not_found", "Domain not found.")
    if domain.state != DOMAIN_STATE_RUNNING:
        raise DiagnosticsError(409, "domain_state_conflict", "Domain lifecycle state does not allow this operation.")
    return domain


def _diagnostics_path(controller: DomainRuntimeController, domain: Domain) -> Path:
    return controller.runtime_dir(domain.id, domain.runtime_instance_id) / "logs" / LIGHTRAG_DIAGNOSTIC_FILENAME


def _redact_line(line: str) -> str:
    value = _CONTROL_CHARS_RE.sub(" ", line).strip()
    if not value:
        return "[empty diagnostic line]"
    if any(pattern.search(value) for pattern in _FORBIDDEN_LINE_PATTERNS):
        return "[redacted diagnostic line]"
    return value[:MAX_LIGHTRAG_DIAGNOSTIC_LINE_CHARS]


def _fit_body(domain_id: str, captured_at: str, lines: list[str], truncated: bool) -> tuple[list[str], bool]:
    fitted = list(lines)
    while fitted:
        body = {
            "diagnostics": {
                "domainId": domain_id,
                "kind": LIGHTRAG_DIAGNOSTIC_KIND,
                "capturedAt": captured_at,
                "lineCount": len(fitted),
                "truncated": truncated,
                "lines": [{"message": line} for line in fitted],
            }
        }
        if len(json.dumps(body, separators=(",", ":")).encode("utf-8")) <= MAX_LIGHTRAG_DIAGNOSTIC_BODY_BYTES:
            return fitted, truncated
        fitted = fitted[1:]
        truncated = True
    return [], True


def read_lightrag_diagnostics(
    db: Session,
    *,
    settings: Settings,
    domain_id: str,
    tail: int,
    controller: DomainRuntimeController | None = None,
) -> LightRAGDiagnostics:
    if tail < 1 or tail > MAX_LIGHTRAG_DIAGNOSTIC_LINES:
        raise DiagnosticsError(422, "validation_error", "Request validation failed.")
    domain = _domain_or_error(db, domain_id)
    controller = controller or controller_from_settings(settings)
    log_path = _diagnostics_path(controller, domain)
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DiagnosticsError(502, "diagnostics_unavailable", "Diagnostics unavailable.") from exc
    truncated = len(raw_lines) > tail
    captured_at = iso_utc(utc_now())
    lines = [_redact_line(line) for line in raw_lines[-tail:]]
    lines, truncated = _fit_body(domain.id, captured_at, lines, truncated)
    return LightRAGDiagnostics(domain_id=domain.id, captured_at=captured_at, lines=lines, truncated=truncated)


def safe_lightrag_diagnostics(diagnostics: LightRAGDiagnostics) -> dict[str, Any]:
    return {
        "domainId": diagnostics.domain_id,
        "kind": LIGHTRAG_DIAGNOSTIC_KIND,
        "capturedAt": diagnostics.captured_at,
        "lineCount": diagnostics.line_count,
        "truncated": diagnostics.truncated,
        "lines": [{"message": line} for line in diagnostics.lines],
    }
