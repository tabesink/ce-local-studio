from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from context_engine.api.catalog_schemas import AdminSourceDto, OperationDto, OutlineItemDto
from context_engine.models import (
    SOURCE_BLOCK_KIND_FIGURE,
    SOURCE_BLOCK_KIND_TABLE,
    SOURCE_BLOCK_KIND_TEXT,
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLING,
    SOURCE_INDEX_STATE_NOT_REQUESTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_PREP_OPERATION_PREPARE,
    SOURCE_PREP_STATUS_FAILED,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_STATE_PENDING,
    SOURCE_STATE_PREPARED,
    SourceBlock,
    SourceDocument,
    SourcePreparationOperation,
)
from context_engine.services.sources import (
    _public_index_state,
    new_document_public_ref,
    safe_source,
    safe_source_operation,
    source_outline,
)


class _SessionStub:
    def __init__(self, active: SourcePreparationOperation | None = None) -> None:
        self._active = active

    def scalar(self, _statement):  # noqa: ANN001
        return self._active


def _source(
    *,
    state: str = SOURCE_STATE_PREPARED,
    index_state: str = SOURCE_INDEX_STATE_READY,
    version: int = 1,
) -> SourceDocument:
    return SourceDocument(
        id=str(uuid4()),
        public_ref=new_document_public_ref(),
        domain_id="domain-manuals",
        original_filename="pump-service-manual.pdf",
        content_type="application/pdf",
        original_sha256="a" * 64,
        original_size_bytes=2048,
        original_object_key="obj_testkey0123456789",
        state=state,
        parser_kind="docling",
        preparation_generation=1,
        index_state=index_state,
        index_generation=1,
        index_error_code="index_failed",
        index_error_message="private failure detail",
        version=version,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 5, 0),
    )


def test_safe_source_matches_closed_admin_source_dto() -> None:
    source = _source()
    active = SourcePreparationOperation(
        id=str(uuid4()),
        source_document_id=source.id,
        domain_id=source.domain_id,
        status=SOURCE_PREP_STATUS_QUEUED,
        preparation_generation_at_start=1,
        created_at=datetime(2026, 7, 25, 12, 1, 0),
        updated_at=datetime(2026, 7, 25, 12, 1, 0),
    )
    projection = safe_source(_SessionStub(active), source)

    dto = AdminSourceDto.model_validate(projection)
    assert dto.id == source.id
    assert dto.document_ref == source.public_ref
    assert dto.display_name == "pump-service-manual.pdf"
    assert dto.size_bytes == 2048
    assert dto.index_state == "ready"
    assert dto.active_operation_id == active.id
    assert dto.version == 1

    forbidden = {
        "originalSha256",
        "originalFilename",
        "originalSizeBytes",
        "originalObjectKey",
        "blockCount",
        "imageCount",
        "indexErrorCode",
        "indexErrorMessage",
        "indexAcceptedAt",
        "indexReadyAt",
        "indexUpdatedAt",
    }
    assert forbidden.isdisjoint(projection.keys())
    assert "obj_" not in str(projection.values())
    assert "a" * 64 not in str(projection.values())


def test_public_index_state_maps_internal_vocabulary() -> None:
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_NOT_REQUESTED)) == "not_requested"
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_QUEUED)) == "queued"
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_SUBMITTING)) == "processing"
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_ACCEPTED)) == "processing"
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_READY)) == "ready"
    assert _public_index_state(_source(index_state=SOURCE_INDEX_STATE_CANCELLING)) == "deleting"
    assert (
        _public_index_state(_source(state=SOURCE_STATE_PENDING, index_state=SOURCE_INDEX_STATE_READY))
        == "ready"
    )


def test_new_document_public_ref_is_opaque() -> None:
    ref = new_document_public_ref()
    assert ref.startswith("doc_")
    assert "/" not in ref
    assert len(ref) >= 16


def test_safe_source_operation_projects_closed_operation_dto() -> None:
    operation = SourcePreparationOperation(
        id=str(uuid4()),
        source_document_id=str(uuid4()),
        domain_id="domain-manuals",
        operation_type=SOURCE_PREP_OPERATION_PREPARE,
        status=SOURCE_PREP_STATUS_FAILED,
        preparation_generation_at_start=2,
        message="Preparation failed.",
        error_code="parser_timeout",
        error_message="Parser timed out.",
        version=3,
        created_at=datetime(2026, 7, 25, 12, 0, 0),
        updated_at=datetime(2026, 7, 25, 12, 1, 0),
        finished_at=datetime(2026, 7, 25, 12, 1, 0),
    )
    projected = safe_source_operation(operation)
    dto = OperationDto.model_validate(projected)
    assert dto.target_kind == "source"
    assert dto.target_ref == operation.source_document_id
    assert dto.generation == 2
    assert dto.error is not None
    assert dto.error.code == "parser_timeout"
    assert dto.error.message == "Parser timed out."
    assert projected["error"] == {"code": "parser_timeout", "message": "Parser timed out."}
    assert set(projected) == {
        "id",
        "targetKind",
        "targetRef",
        "operationType",
        "status",
        "generation",
        "message",
        "error",
        "requestedAt",
        "startedAt",
        "finishedAt",
        "version",
        "allowedActions",
    }
    assert "errorCode" not in projected
    assert "createdAt" not in projected
    assert "canonical_markdown" not in str(projected).lower()


def test_source_outline_projects_closed_items_without_canonical_text() -> None:
    from context_engine.models import Domain

    source_id = str(uuid4())
    domain = Domain(id="domain-manuals", display_name="Manuals", state="stopped", embedding_profile_id="x", runtime_instance_id="r")
    source = SourceDocument(
        id=source_id,
        public_ref=new_document_public_ref(),
        domain_id=domain.id,
        original_filename="pump.pdf",
        content_type="application/pdf",
        original_sha256="b" * 64,
        original_size_bytes=10,
        original_object_key="obj_outline",
        state=SOURCE_STATE_PREPARED,
        parser_kind="docling",
    )
    blocks = [
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain.id,
            source_order=1,
            kind=SOURCE_BLOCK_KIND_TEXT,
            canonical_markdown="# Pump Overview\nSecret body that must not leak.",
            heading_level=1,
            page_start=1,
            page_end=1,
            section_path='["Pump Overview"]',
        ),
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain.id,
            source_order=2,
            kind=SOURCE_BLOCK_KIND_TEXT,
            canonical_markdown="Body paragraph with private wording.",
            heading_level=None,
            page_start=1,
            page_end=1,
            section_path="[]",
        ),
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain.id,
            source_order=3,
            kind=SOURCE_BLOCK_KIND_TABLE,
            canonical_markdown="| a | b |\n|---|---|\n| secret | row |",
            heading_level=None,
            page_start=2,
            page_end=2,
            section_path='["Specs"]',
        ),
        SourceBlock(
            id=str(uuid4()),
            source_document_id=source_id,
            domain_id=domain.id,
            source_order=4,
            kind=SOURCE_BLOCK_KIND_FIGURE,
            canonical_markdown="![diagram](private)",
            heading_level=None,
            page_start=3,
            page_end=3,
            section_path="[]",
        ),
    ]

    class _Session:
        def get(self, model, key):  # noqa: ANN001
            if model is Domain and key == domain.id:
                return domain
            if model is SourceDocument and key == source_id:
                return source
            return None

        def scalars(self, statement):  # noqa: ANN001
            entity = statement.column_descriptions[0]["entity"]
            if entity is SourceBlock:
                return iter(blocks)
            return iter([])

    items = source_outline(_Session(), domain.id, source_id)
    assert len(items) == 3
    for item in items:
        OutlineItemDto.model_validate(item)
    assert {item["kind"] for item in items} == {"heading", "table", "figure"}
    serialized = str(items)
    assert "Secret body" not in serialized
    assert "canonical" not in serialized.lower()
    assert "private wording" not in serialized
    assert items[0] == {"kind": "heading", "label": "Pump Overview", "level": 1, "pageNumber": 1}
