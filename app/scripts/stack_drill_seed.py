#!/usr/bin/env python3
"""P12-04 U3 / R12 — minimal synthetic drill corpus for backup/restore continuity.

Finish seeding before any F1 write-fence (api/worker stop). This seeder is a
Compose-matrix drill helper, not the full demo package. Synthetic content only;
gated by CE_ENVIRONMENT=development|test and CE_ALLOW_TEST_SEED=true.

Pure helpers (build_seed_plan / object_put_plan) run without network or DB.
When CONTEXT_ENGINE_DATABASE_URL (or --database-url) is available, apply via ORM
and optionally put stub object bytes when a store put callback is provided.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence


SEED_CLOCK = datetime(2026, 7, 17, 12, 0, 0)
DRILL_MARKER = "p12_04_drill"

# Deterministic synthetic identities (fixture-style; not production defaults).
DOMAIN_ID = "domain_drill_continuity"
DOMAIN_DISPLAY = "Drill Continuity Domain"
EMBED_PROFILE_ID = "a1111111-1111-4111-8111-drill-embed01"
PROVIDER_KIND = "openai"
MEMBER_USERNAME = "drill.member@example.test"
ADMIN_USERNAME = "drill.admin@example.test"
MEMBER_ID = "a1111111-1111-4111-8111-drill-user01"
ADMIN_ID = "a1111111-1111-4111-8111-drill-user02"
CONV_ID = "a1111111-1111-4111-8111-drill-conv01"
CONV_PUBLIC_REF = "conv_drill_continuity"
TURN_REDACTED_ID = "a1111111-1111-4111-8111-drill-turn01"
TURN_REDACTED_PUBLIC_REF = "turn_drill_redacted"
SOURCE_ID = "a1111111-1111-4111-8111-drill-src01"
SOURCE_PUBLIC_REF = "doc_drill_manual"
SOURCE_TOMBSTONE_ID = "a1111111-1111-4111-8111-drill-src02"
SOURCE_TOMBSTONE_PUBLIC_REF = "doc_drill_tombstone"
BLOCK_ID = "a1111111-1111-4111-8111-drill-blk01"
COMPOSER_REF_TOKEN_PREIMAGE = "ce-p12-04-drill-expired-ref-preimage"
FORBIDDEN_ANSWER_TEXT = "DRILL_FORBIDDEN_REDACTED_ANSWER_TEXT_v1"
USER_QUESTION = "What does the drill manual say about lockout?"

# Flat keys (filesystem adapter rejects path separators; S3 accepts these too).
ORIGINAL_OBJECT_KEY = "obj_drill_original"
PREVIEW_OBJECT_KEY = "obj_drill_preview"
PAGE_MAP_OBJECT_KEY = "obj_drill_page_map"
TOMBSTONE_OBJECT_KEY = "obj_drill_tombstone"

# Minimal synthetic PDF-like stub bytes (not a real parser input).
ORIGINAL_BYTES = b"%PDF-1.4\n%CE-DRILL-SYNTHETIC\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PREVIEW_BYTES = b"%PDF-1.4\n%CE-DRILL-PREVIEW\ntrailer<<>>\n%%EOF\n"
PAGE_MAP_BYTES = b'{"schemaVersion":1,"pages":[{"page":1,"width":612,"height":792}]}\n'
TOMBSTONE_BYTES = b"%PDF-1.4\n%CE-DRILL-TOMBSTONE\n%%EOF\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _token_hash(preimage: str) -> str:
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ObjectPutSpec:
    key: str
    sha256: str
    size_bytes: int
    content: bytes


@dataclass(frozen=True)
class AuditSeedSpec:
    event_name: str
    actor_kind: str
    outcome: str
    target_kind: str | None
    target_id: str | None
    request_id: str
    created_at: datetime


@dataclass(frozen=True)
class ComposerRefSeedSpec:
    token_hash: str
    owner_user_id: str
    ref_kind: str
    target_id: str
    domain_id: str
    safe_label: str
    expires_at: datetime
    consumed_at: datetime | None
    invalidated: bool


@dataclass(frozen=True)
class RedactedTurnSeedSpec:
    turn_id: str
    public_ref: str
    client_request_id: str
    user_message: str
    forbidden_answer_text: str
    status: str
    stop_reason: str
    domain_id: str


@dataclass(frozen=True)
class SourceSeedSpec:
    source_id: str
    public_ref: str
    domain_id: str
    original_object_key: str
    original_sha256: str
    original_size_bytes: int
    preview_object_key: str | None
    preview_sha256: str | None
    preview_size_bytes: int | None
    preview_page_map_object_key: str | None
    preview_page_map_sha256: str | None
    preview_reuses_original: bool
    state: str
    preview_state: str
    index_state: str


@dataclass(frozen=True)
class DrillSeedPlan:
    """Network-free seed plan for R12 continuity corpus."""

    marker: str
    clock: datetime
    domain_id: str
    domain_display_name: str
    embed_profile_id: str
    member_username: str
    admin_username: str
    member_id: str
    admin_id: str
    conversation_id: str
    conversation_public_ref: str
    prepared_source: SourceSeedSpec
    tombstone_source: SourceSeedSpec
    block_id: str
    block_text: str
    redacted_turn: RedactedTurnSeedSpec
    composer_ref: ComposerRefSeedSpec
    audit_events: tuple[AuditSeedSpec, ...]
    object_puts: tuple[ObjectPutSpec, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_public_dict(self) -> dict[str, Any]:
        """JSON-safe projection (no raw object bytes)."""
        payload = asdict(self)
        payload["clock"] = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        payload["object_puts"] = [
            {
                "key": put.key,
                "sha256": put.sha256,
                "sizeBytes": put.size_bytes,
            }
            for put in self.object_puts
        ]
        for event in payload["audit_events"]:
            event["created_at"] = event["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
        cref = payload["composer_ref"]
        cref["expires_at"] = cref["expires_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
        if cref.get("consumed_at") is not None:
            cref["consumed_at"] = cref["consumed_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
        # Never emit raw token preimage or forbidden answer as a "live" answer field.
        payload["redacted_turn"]["assistant_answer"] = None
        payload["composer_ref_token_preimage_present"] = True
        return payload


def build_seed_plan(*, preview_reuses_original: bool = False) -> DrillSeedPlan:
    """Build a deterministic R12 seed plan without touching the network or DB."""
    original_sha = _sha(ORIGINAL_BYTES)
    preview_sha = original_sha if preview_reuses_original else _sha(PREVIEW_BYTES)
    preview_key = ORIGINAL_OBJECT_KEY if preview_reuses_original else PREVIEW_OBJECT_KEY
    preview_size = len(ORIGINAL_BYTES) if preview_reuses_original else len(PREVIEW_BYTES)
    page_map_sha = _sha(PAGE_MAP_BYTES)
    tombstone_sha = _sha(TOMBSTONE_BYTES)
    expired_at = SEED_CLOCK - timedelta(hours=1)
    audit_at = SEED_CLOCK

    puts: list[ObjectPutSpec] = [
        ObjectPutSpec(
            key=ORIGINAL_OBJECT_KEY,
            sha256=original_sha,
            size_bytes=len(ORIGINAL_BYTES),
            content=ORIGINAL_BYTES,
        ),
        ObjectPutSpec(
            key=PAGE_MAP_OBJECT_KEY,
            sha256=page_map_sha,
            size_bytes=len(PAGE_MAP_BYTES),
            content=PAGE_MAP_BYTES,
        ),
        ObjectPutSpec(
            key=TOMBSTONE_OBJECT_KEY,
            sha256=tombstone_sha,
            size_bytes=len(TOMBSTONE_BYTES),
            content=TOMBSTONE_BYTES,
        ),
    ]
    if not preview_reuses_original:
        puts.insert(
            1,
            ObjectPutSpec(
                key=PREVIEW_OBJECT_KEY,
                sha256=preview_sha,
                size_bytes=len(PREVIEW_BYTES),
                content=PREVIEW_BYTES,
            ),
        )

    prepared = SourceSeedSpec(
        source_id=SOURCE_ID,
        public_ref=SOURCE_PUBLIC_REF,
        domain_id=DOMAIN_ID,
        original_object_key=ORIGINAL_OBJECT_KEY,
        original_sha256=original_sha,
        original_size_bytes=len(ORIGINAL_BYTES),
        preview_object_key=preview_key,
        preview_sha256=preview_sha,
        preview_size_bytes=preview_size,
        preview_page_map_object_key=PAGE_MAP_OBJECT_KEY,
        preview_page_map_sha256=page_map_sha,
        preview_reuses_original=preview_reuses_original,
        state="prepared",
        preview_state="ready",
        index_state="ready",
    )
    tombstone = SourceSeedSpec(
        source_id=SOURCE_TOMBSTONE_ID,
        public_ref=SOURCE_TOMBSTONE_PUBLIC_REF,
        domain_id=DOMAIN_ID,
        original_object_key=TOMBSTONE_OBJECT_KEY,
        original_sha256=tombstone_sha,
        original_size_bytes=len(TOMBSTONE_BYTES),
        preview_object_key=None,
        preview_sha256=None,
        preview_size_bytes=None,
        preview_page_map_object_key=None,
        preview_page_map_sha256=None,
        preview_reuses_original=False,
        state="deleting",
        preview_state="not_requested",
        index_state="not_requested",
    )
    redacted = RedactedTurnSeedSpec(
        turn_id=TURN_REDACTED_ID,
        public_ref=TURN_REDACTED_PUBLIC_REF,
        client_request_id="drill-redacted-turn-1",
        user_message=USER_QUESTION,
        forbidden_answer_text=FORBIDDEN_ANSWER_TEXT,
        status="redacted",
        stop_reason="redacted",
        domain_id=DOMAIN_ID,
    )
    composer = ComposerRefSeedSpec(
        token_hash=_token_hash(COMPOSER_REF_TOKEN_PREIMAGE),
        owner_user_id=MEMBER_ID,
        ref_kind="source",
        target_id=SOURCE_ID,
        domain_id=DOMAIN_ID,
        safe_label="Drill source chip",
        expires_at=expired_at,
        consumed_at=None,
        invalidated=True,
    )
    audits = (
        AuditSeedSpec(
            event_name="domain.created",
            actor_kind="administrator",
            outcome="succeeded",
            target_kind="domain",
            target_id=DOMAIN_ID,
            request_id="drill-audit-domain-created",
            created_at=audit_at,
        ),
        AuditSeedSpec(
            event_name="source.uploaded",
            actor_kind="administrator",
            outcome="succeeded",
            target_kind="source",
            target_id=SOURCE_ID,
            request_id="drill-audit-source-uploaded",
            created_at=audit_at + timedelta(seconds=1),
        ),
        AuditSeedSpec(
            event_name="source.delete_queued",
            actor_kind="administrator",
            outcome="succeeded",
            target_kind="source",
            target_id=SOURCE_TOMBSTONE_ID,
            request_id="drill-audit-source-delete-queued",
            created_at=audit_at + timedelta(seconds=2),
        ),
    )
    return DrillSeedPlan(
        marker=DRILL_MARKER,
        clock=SEED_CLOCK,
        domain_id=DOMAIN_ID,
        domain_display_name=DOMAIN_DISPLAY,
        embed_profile_id=EMBED_PROFILE_ID,
        member_username=MEMBER_USERNAME,
        admin_username=ADMIN_USERNAME,
        member_id=MEMBER_ID,
        admin_id=ADMIN_ID,
        conversation_id=CONV_ID,
        conversation_public_ref=CONV_PUBLIC_REF,
        prepared_source=prepared,
        tombstone_source=tombstone,
        block_id=BLOCK_ID,
        block_text="Isolate electrical power before opening the service panel.",
        redacted_turn=redacted,
        composer_ref=composer,
        audit_events=audits,
        object_puts=tuple(puts),
        notes=(
            "Finish seeding before F1 write-fence (stop api/worker).",
            "Citations/Evidence after LightRAG rebuild are U6/R14 — not owned here.",
            "Forbidden answer text must remain omitted after restore (R13).",
        ),
    )


def object_put_plan(plan: DrillSeedPlan | None = None) -> list[dict[str, Any]]:
    """Return key/sha/size put specs (bytes omitted) for census/recon fixtures."""
    active = plan or build_seed_plan()
    return [
        {"key": put.key, "sha256": put.sha256, "sizeBytes": put.size_bytes}
        for put in active.object_puts
    ]


def apply_object_puts(
    plan: DrillSeedPlan,
    *,
    put: Callable[[str, bytes], None],
) -> list[str]:
    """Put stub object bytes; return keys written. Failures raise."""
    written: list[str] = []
    for spec in plan.object_puts:
        put(spec.key, spec.content)
        written.append(spec.key)
    return written


def expected_audit_rows(plan: DrillSeedPlan | None = None) -> list[dict[str, str]]:
    """Ordered audit projection used by continuity digest checks."""
    active = plan or build_seed_plan()
    rows: list[dict[str, str]] = []
    for event in sorted(active.audit_events, key=lambda e: (e.created_at, e.request_id)):
        rows.append(
            {
                "event_name": event.event_name,
                "outcome": event.outcome,
                "target_kind": event.target_kind or "",
                "target_id": event.target_id or "",
                "request_id": event.request_id,
                "created_at": event.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return rows


def seed_drill_corpus(
    session: Any,
    plan: DrillSeedPlan | None = None,
    *,
    put: Callable[[str, bytes], None] | None = None,
    commit: bool = True,
) -> DrillSeedPlan:
    """Apply seed plan via SQLAlchemy ORM session. Idempotent on fixture IDs."""
    from context_engine.dev.seed_gate import require_seed_writes_allowed
    from context_engine.models import (
        AUDIT_ACTOR_ADMINISTRATOR,
        COMPOSER_REF_KIND_SOURCE,
        DOMAIN_STATE_STOPPED,
        ROLE_ADMINISTRATOR,
        ROLE_MEMBER,
        SOURCE_BLOCK_KIND_TEXT,
        SOURCE_INDEX_STATE_NOT_REQUESTED,
        SOURCE_INDEX_STATE_READY,
        SOURCE_PREVIEW_STATE_NOT_REQUESTED,
        SOURCE_PREVIEW_STATE_READY,
        SOURCE_STATE_DELETING,
        SOURCE_STATE_PREPARED,
        TURN_ROUTE_DOMAIN_RAG,
        TURN_STATUS_REDACTED,
        TURN_STOP_REASON_REDACTED,
        AuditEvent,
        ComposerRefToken,
        Conversation,
        ConversationTurn,
        Domain,
        ModelProfile,
        ProviderConfig,
        SourceBlock,
        SourceDocument,
        User,
    )

    require_seed_writes_allowed()
    active = plan or build_seed_plan()

    if put is not None:
        apply_object_puts(active, put=put)

    if session.get(ProviderConfig, PROVIDER_KIND) is None:
        session.add(
            ProviderConfig(
                provider_kind=PROVIDER_KIND,
                display_name="OpenAI",
                requires_credentials=True,
            )
        )

    profile = session.get(ModelProfile, active.embed_profile_id)
    if profile is None:
        session.add(
            ModelProfile(
                id=active.embed_profile_id,
                name="Drill Embedding 384",
                profile_kind="embedding",
                provider_kind=PROVIDER_KIND,
                model_name="text-embedding-3-small",
                vector_dimensions=384,
            )
        )

    domain = session.get(Domain, active.domain_id)
    if domain is None:
        session.add(
            Domain(
                id=active.domain_id,
                display_name=active.domain_display_name,
                state=DOMAIN_STATE_STOPPED,
                embedding_profile_id=active.embed_profile_id,
                control_generation=1,
                runtime_instance_id="runtime-drill-continuity",
                created_at=active.clock,
                updated_at=active.clock,
            )
        )

    for user_id, username, role in (
        (active.member_id, active.member_username, ROLE_MEMBER),
        (active.admin_id, active.admin_username, ROLE_ADMINISTRATOR),
    ):
        if session.get(User, user_id) is None:
            session.add(
                User(
                    id=user_id,
                    username=username,
                    password_hash="synthetic-drill-password-hash",
                    role=role,
                    created_at=active.clock,
                    updated_at=active.clock,
                )
            )

    def _upsert_source(spec: SourceSeedSpec) -> None:
        source = session.get(SourceDocument, spec.source_id)
        state = SOURCE_STATE_DELETING if spec.state == "deleting" else SOURCE_STATE_PREPARED
        preview_state = (
            SOURCE_PREVIEW_STATE_READY if spec.preview_state == "ready" else SOURCE_PREVIEW_STATE_NOT_REQUESTED
        )
        index_state = (
            SOURCE_INDEX_STATE_READY if spec.index_state == "ready" else SOURCE_INDEX_STATE_NOT_REQUESTED
        )
        values = dict(
            public_ref=spec.public_ref,
            domain_id=spec.domain_id,
            original_filename="drill-manual.pdf",
            content_type="application/pdf",
            original_sha256=spec.original_sha256,
            original_size_bytes=spec.original_size_bytes,
            original_object_key=spec.original_object_key,
            state=state,
            parser_kind="docling",
            preparation_generation=1,
            index_state=index_state,
            index_generation=1 if index_state == SOURCE_INDEX_STATE_READY else 0,
            index_request_id="drill-index-1" if index_state == SOURCE_INDEX_STATE_READY else None,
            index_content_hash=spec.original_sha256 if index_state == SOURCE_INDEX_STATE_READY else None,
            preview_state=preview_state,
            preview_generation=1 if preview_state == SOURCE_PREVIEW_STATE_READY else 0,
            preview_version=1 if preview_state == SOURCE_PREVIEW_STATE_READY else 0,
            preview_object_key=spec.preview_object_key,
            preview_sha256=spec.preview_sha256,
            preview_size_bytes=spec.preview_size_bytes,
            preview_page_count=1 if preview_state == SOURCE_PREVIEW_STATE_READY else None,
            preview_page_map_object_key=spec.preview_page_map_object_key,
            preview_page_map_sha256=spec.preview_page_map_sha256,
            preview_reuses_original=spec.preview_reuses_original,
            preview_ready_at=active.clock if preview_state == SOURCE_PREVIEW_STATE_READY else None,
            version=1,
            created_at=active.clock,
            updated_at=active.clock,
        )
        if source is None:
            session.add(SourceDocument(id=spec.source_id, **values))
        else:
            for key, value in values.items():
                setattr(source, key, value)

    _upsert_source(active.prepared_source)
    _upsert_source(active.tombstone_source)

    block = session.get(SourceBlock, active.block_id)
    if block is None:
        session.add(
            SourceBlock(
                id=active.block_id,
                source_document_id=active.prepared_source.source_id,
                domain_id=active.domain_id,
                source_order=1,
                kind=SOURCE_BLOCK_KIND_TEXT,
                canonical_markdown=active.block_text,
                page_start=1,
                page_end=1,
                created_at=active.clock,
            )
        )

    conversation = session.get(Conversation, active.conversation_id)
    if conversation is None:
        session.add(
            Conversation(
                id=active.conversation_id,
                public_ref=active.conversation_public_ref,
                owner_user_id=active.member_id,
                title="Drill continuity",
                created_at=active.clock,
                updated_at=active.clock,
            )
        )

    turn = session.get(ConversationTurn, active.redacted_turn.turn_id)
    turn_values = dict(
        public_ref=active.redacted_turn.public_ref,
        conversation_id=active.conversation_id,
        client_request_id=active.redacted_turn.client_request_id,
        domain_id=active.redacted_turn.domain_id,
        route=TURN_ROUTE_DOMAIN_RAG,
        status=TURN_STATUS_REDACTED,
        stop_reason=TURN_STOP_REASON_REDACTED,
        user_message=active.redacted_turn.user_message,
        assistant_answer=None,
        started_at=active.clock,
        completed_at=active.clock,
        created_at=active.clock,
        updated_at=active.clock,
    )
    if turn is None:
        session.add(ConversationTurn(id=active.redacted_turn.turn_id, **turn_values))
    else:
        for key, value in turn_values.items():
            setattr(turn, key, value)

    # Expired / invalidated composer ref (hash only — never persist raw token).
    from sqlalchemy import select

    existing_ref = session.execute(
        select(ComposerRefToken).where(ComposerRefToken.token_hash == active.composer_ref.token_hash)
    ).scalar_one_or_none()
    if existing_ref is None:
        session.add(
            ComposerRefToken(
                token_hash=active.composer_ref.token_hash,
                owner_user_id=active.composer_ref.owner_user_id,
                ref_kind=COMPOSER_REF_KIND_SOURCE,
                target_id=active.composer_ref.target_id,
                domain_id=active.composer_ref.domain_id,
                safe_label=active.composer_ref.safe_label,
                expires_at=active.composer_ref.expires_at,
                consumed_at=active.composer_ref.consumed_at,
                created_at=active.clock,
            )
        )
    else:
        existing_ref.expires_at = active.composer_ref.expires_at
        existing_ref.consumed_at = active.composer_ref.consumed_at
        existing_ref.target_id = active.composer_ref.target_id

    for event in active.audit_events:
        existing_audit = session.execute(
            select(AuditEvent).where(AuditEvent.request_id == event.request_id)
        ).scalar_one_or_none()
        if existing_audit is None:
            session.add(
                AuditEvent(
                    event_name=event.event_name,
                    actor_kind=event.actor_kind or AUDIT_ACTOR_ADMINISTRATOR,
                    actor_user_id=active.admin_id,
                    target_kind=event.target_kind,
                    target_id=event.target_id,
                    request_id=event.request_id,
                    outcome=event.outcome,
                    created_at=event.created_at,
                )
            )

    session.flush()
    if commit:
        session.commit()
    return active


def _put_via_product_store(key: str, data: bytes) -> None:
    from context_engine.adapters.object_storage import object_store_from_settings
    from context_engine.config import Settings

    store = object_store_from_settings(Settings())
    put_key = getattr(store, "put_key", None)
    if not callable(put_key):
        raise RuntimeError("object_store_put_key_unavailable")
    put_key(key, data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P12-04 U3 drill corpus seeder (R12). "
            "IMPORTANT: finish seeding before any F1 write-fence "
            "(stop api/worker only after this seeder completes)."
        )
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print JSON seed plan (no DB/object writes; safe for unit fixtures).",
    )
    parser.add_argument(
        "--preview-reuses-original",
        action="store_true",
        help="Seed preview_reuses_original=true (preview key dedupes onto original).",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override CONTEXT_ENGINE_DATABASE_URL for ORM seed apply.",
    )
    parser.add_argument(
        "--put-objects",
        action="store_true",
        help="Also put stub object bytes via product object store (when configured).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the public seed plan JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    plan = build_seed_plan(preview_reuses_original=bool(args.preview_reuses_original))
    public = plan.to_public_dict()

    if args.output is not None:
        args.output.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.plan_only:
        print(json.dumps(public, indent=2, sort_keys=True))
        return 0

    database_url = (
        (args.database_url or "").strip()
        or os.environ.get("CONTEXT_ENGINE_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if not database_url:
        print(
            "database_url_required: set CONTEXT_ENGINE_DATABASE_URL or pass --database-url "
            "(or use --plan-only)",
            file=sys.stderr,
        )
        return 2

    try:
        from context_engine.dev.seed_gate import require_seed_writes_allowed
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        require_seed_writes_allowed()
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        put_cb = _put_via_product_store if args.put_objects else None
        with Session() as session:
            seed_drill_corpus(session, plan, put=put_cb, commit=True)
    except Exception as exc:
        print(f"seed_failed:{type(exc).__name__}", file=sys.stderr)
        return 1

    print(
        f"seed:ok marker={plan.marker} domain={plan.domain_id} "
        f"objects={len(plan.object_puts)} audits={len(plan.audit_events)} "
        f"finish_before_fence=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
