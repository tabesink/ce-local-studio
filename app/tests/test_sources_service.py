from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from context_engine.api.catalog_schemas import AdminSourceDto
from context_engine.models import (
    SOURCE_INDEX_STATE_ACCEPTED,
    SOURCE_INDEX_STATE_CANCELLING,
    SOURCE_INDEX_STATE_NOT_REQUESTED,
    SOURCE_INDEX_STATE_QUEUED,
    SOURCE_INDEX_STATE_READY,
    SOURCE_INDEX_STATE_SUBMITTING,
    SOURCE_PREP_STATUS_QUEUED,
    SOURCE_STATE_PENDING,
    SOURCE_STATE_PREPARED,
    SourceDocument,
    SourcePreparationOperation,
)
from context_engine.services.sources import (
    _public_index_state,
    new_document_public_ref,
    safe_source,
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
