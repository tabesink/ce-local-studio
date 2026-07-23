from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_TEMPLATE,
    ConversationTurnEvidenceRef,
    PromptTemplate,
    SourceBlock,
)
from context_engine.services.composer_refs import ValidatedComposerRef

TEMPLATE_BODY_CAP_CHARS = 2000
SOURCE_CONTEXT_BLOCK_CAP = 4
SOURCE_CONTEXT_CAP_CHARS = 1000
TOTAL_ASSEMBLY_CAP_CHARS = 8000


@dataclass(frozen=True)
class PromptAssemblySnippet:
    kind: str
    label: str | None
    body: str


@dataclass(frozen=True)
class PromptAssemblyContext:
    snippets: tuple[PromptAssemblySnippet, ...]
    total_chars: int

    @property
    def is_empty(self) -> bool:
        return not self.snippets


class PromptAssemblyService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def assemble(self, refs: tuple[ValidatedComposerRef, ...]) -> PromptAssemblyContext:
        snippets: list[PromptAssemblySnippet] = []
        remaining = TOTAL_ASSEMBLY_CAP_CHARS
        for ref in refs:
            if remaining <= 0:
                break
            body = self._body_for_ref(ref)
            if not body:
                continue
            body = body[:remaining].rstrip()
            if not body:
                continue
            snippets.append(PromptAssemblySnippet(kind=ref.kind, label=ref.label, body=body))
            remaining -= len(body)
        total_chars = sum(len(snippet.body) for snippet in snippets)
        return PromptAssemblyContext(snippets=tuple(snippets), total_chars=total_chars)

    def _body_for_ref(self, ref: ValidatedComposerRef) -> str:
        if ref.kind == COMPOSER_REF_KIND_TEMPLATE and ref.prompt_template_id:
            return self._template_body(ref.prompt_template_id)
        if ref.kind == COMPOSER_REF_KIND_SOURCE and ref.source_document_id:
            return self._source_body(ref.source_document_id)
        if ref.kind == COMPOSER_REF_KIND_EVIDENCE and ref.evidence_ref_id:
            return self._evidence_body(ref.evidence_ref_id)
        return ""

    def _template_body(self, template_id: str) -> str:
        template = self._db.get(PromptTemplate, template_id)
        if template is None:
            return ""
        return template.body[:TEMPLATE_BODY_CAP_CHARS].rstrip()

    def _source_body(self, source_document_id: str) -> str:
        blocks = self._db.scalars(
            select(SourceBlock)
            .where(SourceBlock.source_document_id == source_document_id)
            .order_by(SourceBlock.source_order)
            .limit(SOURCE_CONTEXT_BLOCK_CAP)
        )
        body = ""
        for block in blocks:
            text = block.canonical_markdown.strip()
            if not text:
                continue
            separator = "\n\n" if body else ""
            remaining = SOURCE_CONTEXT_CAP_CHARS - len(body) - len(separator)
            if remaining <= 0:
                break
            text = text[:remaining].rstrip()
            if not text:
                continue
            body = f"{body}{separator}{text}"
            if len(body) >= SOURCE_CONTEXT_CAP_CHARS:
                break
        return body

    def _evidence_body(self, evidence_ref_id: str) -> str:
        evidence_ref = self._db.get(ConversationTurnEvidenceRef, evidence_ref_id)
        if evidence_ref is None or evidence_ref.redacted_at is not None:
            return ""
        return (evidence_ref.excerpt or "").strip()
