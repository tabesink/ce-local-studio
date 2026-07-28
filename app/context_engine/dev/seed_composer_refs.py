from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from context_engine.db import utc_now
from context_engine.dev.seed_gate import require_seed_writes_allowed
from context_engine.dev.seed_prompt_templates import (
    TEMPLATE_DISABLED_ID,
    TEMPLATE_SAFETY_SUMMARY_ID,
    seed_prompt_template_fixtures,
)
from context_engine.models import (
    COMPOSER_REF_KIND_EVIDENCE,
    COMPOSER_REF_KIND_SOURCE,
    COMPOSER_REF_KIND_TEMPLATE,
    DOMAIN_STATE_RUNNING,
    DOMAIN_STATE_STOPPED,
    EMPTY_COMPOSER_REF_FINGERPRINT,
    ROLE_MEMBER,
    SOURCE_STATE_PREPARED,
    TURN_ROUTE_DIRECT_LLM,
    TURN_ROUTE_DOMAIN_RAG,
    TURN_STATUS_COMPLETED,
    TURN_STATUS_REDACTED,
    ComposerRefToken,
    Conversation,
    ConversationTurn,
    ConversationTurnComposerRef,
    ConversationTurnEvidenceRef,
    Domain,
    ModelProfile,
    ProviderConfig,
    SourceDocument,
    User,
)

SEED_CLOCK = datetime(2026, 7, 17, 12, 0, 0)
RESERVED_CONSUMED_TOKEN_KEY = "token_mina_consumed_source"

USER_MINA_ID = "a1111111-1111-4111-8111-user00000001"
USER_NOAH_ID = "a1111111-1111-4111-8111-user00000002"
EMBED_PROFILE_ID = "a1111111-1111-4111-8111-embed0000001"
DOMAIN_MANUALS_ID = "domain_manuals"
DOMAIN_POLICIES_ID = "domain_policies"
SOURCE_PUMP_ID = "a1111111-1111-4111-8111-source000001"
SOURCE_PUMP_PUBLIC_REF = "doc_pump_manual"
CONV_MINA_ID = "a1111111-1111-4111-8111-conv00000001"
CONV_MINA_PUBLIC_REF = "conv_mina_manuals"
TURN_FIGURE_ID = "a1111111-1111-4111-8111-turn00000001"
TURN_FIGURE_PUBLIC_REF = "turn_mina_figure"
TURN_REDACTED_ID = "a1111111-1111-4111-8111-turn00000002"
TURN_REDACTED_PUBLIC_REF = "turn_mina_redacted"
EVIDENCE_FIGURE_ID = "a1111111-1111-4111-8111-ev0000000001"
EVIDENCE_FIGURE_PUBLIC_REF = "ev_mina_figure_valve"

ACCEPTED_SOURCE_PUBLIC_REF = "accepted_mina_source_01"
ACCEPTED_EVIDENCE_PUBLIC_REF = "accepted_mina_evidence_01"
ACCEPTED_TEMPLATE_PUBLIC_REF = "accepted_mina_template_01"
ACCEPTED_REDACTED_PUBLIC_REF = "accepted_mina_redacted_01"

# Hash-only fixture identity. Persist sha256(preimage); never store raw tokens.
# Preimage scheme is test/seed-only and is not a browser-visible secret.
TOKEN_FIXTURE_KEYS = (
    "token_mina_source_valid",
    "token_mina_evidence_valid",
    "token_mina_template_valid",
    "token_mina_expired",
    "token_noah_wrong_owner",
    "token_mina_wrong_domain",
    "token_mina_deleted_target",
    "token_mina_disabled_template",
    RESERVED_CONSUMED_TOKEN_KEY,
)


def fixture_token_hash(fixture_key: str) -> str:
    return sha256(f"ce-p11-01:{fixture_key}".encode("utf-8")).hexdigest()


TOKEN_HASHES = {key: fixture_token_hash(key) for key in TOKEN_FIXTURE_KEYS}


@dataclass(frozen=True)
class TokenFixture:
    fixture_key: str
    token_id: str
    owner_user_id: str
    ref_kind: str
    target_id: str
    domain_id: str | None
    safe_label: str
    expires_at: datetime
    consumed_at: datetime | None = None


@dataclass(frozen=True)
class AcceptedRefFixture:
    public_ref: str
    accepted_id: str
    turn_id: str
    ref_order: int
    ref_kind: str
    safe_label: str | None
    safe_description: str | None
    domain_id: str | None
    source_document_id: str | None
    source_block_id: str | None
    evidence_ref_id: str | None
    prompt_template_id: str | None
    redacted_at: datetime | None


def _token_fixtures(*, now: datetime) -> tuple[TokenFixture, ...]:
    valid_expiry = now + timedelta(hours=1)
    expired_at = now - timedelta(hours=1)
    return (
        TokenFixture(
            fixture_key="token_mina_source_valid",
            token_id="b1111111-1111-4111-8111-token0000001",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=SOURCE_PUMP_ID,
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Pump manual",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_evidence_valid",
            token_id="b1111111-1111-4111-8111-token0000002",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_EVIDENCE,
            target_id=EVIDENCE_FIGURE_ID,
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Relief valve figure",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_template_valid",
            token_id="b1111111-1111-4111-8111-token0000003",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_TEMPLATE,
            target_id=TEMPLATE_SAFETY_SUMMARY_ID,
            domain_id=None,
            safe_label="Safety summary",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_expired",
            token_id="b1111111-1111-4111-8111-token0000004",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=SOURCE_PUMP_ID,
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Expired source",
            expires_at=expired_at,
        ),
        TokenFixture(
            fixture_key="token_noah_wrong_owner",
            token_id="b1111111-1111-4111-8111-token0000005",
            owner_user_id=USER_NOAH_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=SOURCE_PUMP_ID,
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Noah source",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_wrong_domain",
            token_id="b1111111-1111-4111-8111-token0000006",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=SOURCE_PUMP_ID,
            domain_id=DOMAIN_POLICIES_ID,
            safe_label="Wrong domain source",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_deleted_target",
            token_id="b1111111-1111-4111-8111-token0000007",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id="missing-source-target-0001",
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Deleted target",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key="token_mina_disabled_template",
            token_id="b1111111-1111-4111-8111-token0000008",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_TEMPLATE,
            target_id=TEMPLATE_DISABLED_ID,
            domain_id=None,
            safe_label="Disabled template",
            expires_at=valid_expiry,
        ),
        TokenFixture(
            fixture_key=RESERVED_CONSUMED_TOKEN_KEY,
            token_id="b1111111-1111-4111-8111-token0000009",
            owner_user_id=USER_MINA_ID,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            target_id=SOURCE_PUMP_ID,
            domain_id=DOMAIN_MANUALS_ID,
            safe_label="Consumed source",
            expires_at=valid_expiry,
            consumed_at=now - timedelta(minutes=5),
        ),
    )


def _accepted_ref_fixtures() -> tuple[AcceptedRefFixture, ...]:
    return (
        AcceptedRefFixture(
            public_ref=ACCEPTED_SOURCE_PUBLIC_REF,
            accepted_id="c1111111-1111-4111-8111-accepted0001",
            turn_id=TURN_FIGURE_ID,
            ref_order=1,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            safe_label="Pump manual",
            safe_description="Equipment manuals source",
            domain_id=DOMAIN_MANUALS_ID,
            source_document_id=SOURCE_PUMP_ID,
            source_block_id=None,
            evidence_ref_id=None,
            prompt_template_id=None,
            redacted_at=None,
        ),
        AcceptedRefFixture(
            public_ref=ACCEPTED_EVIDENCE_PUBLIC_REF,
            accepted_id="c1111111-1111-4111-8111-accepted0002",
            turn_id=TURN_FIGURE_ID,
            ref_order=2,
            ref_kind=COMPOSER_REF_KIND_EVIDENCE,
            safe_label="Relief valve figure",
            safe_description="Figure evidence",
            domain_id=DOMAIN_MANUALS_ID,
            source_document_id=None,
            source_block_id=None,
            evidence_ref_id=EVIDENCE_FIGURE_ID,
            prompt_template_id=None,
            redacted_at=None,
        ),
        AcceptedRefFixture(
            public_ref=ACCEPTED_TEMPLATE_PUBLIC_REF,
            accepted_id="c1111111-1111-4111-8111-accepted0003",
            turn_id=TURN_FIGURE_ID,
            ref_order=3,
            ref_kind=COMPOSER_REF_KIND_TEMPLATE,
            safe_label="Safety summary",
            safe_description="Approved template",
            domain_id=None,
            source_document_id=None,
            source_block_id=None,
            evidence_ref_id=None,
            prompt_template_id=TEMPLATE_SAFETY_SUMMARY_ID,
            redacted_at=None,
        ),
        AcceptedRefFixture(
            public_ref=ACCEPTED_REDACTED_PUBLIC_REF,
            accepted_id="c1111111-1111-4111-8111-accepted0004",
            turn_id=TURN_REDACTED_ID,
            ref_order=1,
            ref_kind=COMPOSER_REF_KIND_SOURCE,
            safe_label=None,
            safe_description=None,
            domain_id=DOMAIN_MANUALS_ID,
            source_document_id=SOURCE_PUMP_ID,
            source_block_id=None,
            evidence_ref_id=None,
            prompt_template_id=None,
            redacted_at=SEED_CLOCK,
        ),
    )


def _upsert_user(db: Session, *, user_id: str, username: str) -> None:
    user = db.get(User, user_id)
    if user is None:
        db.add(
            User(
                id=user_id,
                username=username,
                password_hash="synthetic-password-hash",
                role=ROLE_MEMBER,
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
                password_changed_at=SEED_CLOCK,
            )
        )
        return
    user.username = username
    user.role = ROLE_MEMBER
    user.is_disabled = False


def _ensure_runtime_parents(db: Session) -> None:
    if db.get(ProviderConfig, "openai") is None:
        db.add(
            ProviderConfig(
                provider_kind="openai",
                display_name="OpenAI",
                requires_credentials=True,
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
        db.flush()
    profile = db.get(ModelProfile, EMBED_PROFILE_ID)
    if profile is None:
        db.add(
            ModelProfile(
                id=EMBED_PROFILE_ID,
                name="embed_384_v1",
                profile_kind="embedding",
                provider_kind="openai",
                model_name="text-embedding-3-small",
                vector_dimensions=384,
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
        db.flush()


def _upsert_domain(db: Session, *, domain_id: str, display_name: str, state: str) -> None:
    domain = db.get(Domain, domain_id)
    if domain is None:
        db.add(
            Domain(
                id=domain_id,
                display_name=display_name,
                state=state,
                embedding_profile_id=EMBED_PROFILE_ID,
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
        return
    domain.display_name = display_name
    domain.state = state
    domain.embedding_profile_id = EMBED_PROFILE_ID


def _upsert_source(db: Session) -> None:
    source = db.get(SourceDocument, SOURCE_PUMP_ID)
    if source is None:
        db.add(
            SourceDocument(
                id=SOURCE_PUMP_ID,
                public_ref=SOURCE_PUMP_PUBLIC_REF,
                domain_id=DOMAIN_MANUALS_ID,
                original_filename="pump-manual.pdf",
                content_type="application/pdf",
                original_sha256="a" * 64,
                original_size_bytes=2048,
                original_object_key="source/doc_pump_manual",
                state=SOURCE_STATE_PREPARED,
                parser_kind="docling",
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
        return
    source.public_ref = SOURCE_PUMP_PUBLIC_REF
    source.domain_id = DOMAIN_MANUALS_ID
    source.state = SOURCE_STATE_PREPARED


def _upsert_conversation_graph(db: Session) -> None:
    conversation = db.get(Conversation, CONV_MINA_ID)
    if conversation is None:
        db.add(
            Conversation(
                id=CONV_MINA_ID,
                public_ref=CONV_MINA_PUBLIC_REF,
                owner_user_id=USER_MINA_ID,
                title="Mina manuals",
                version=1,
                created_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
    else:
        conversation.public_ref = CONV_MINA_PUBLIC_REF
        conversation.owner_user_id = USER_MINA_ID
        conversation.title = "Mina manuals"
    db.flush()

    figure = db.get(ConversationTurn, TURN_FIGURE_ID)
    if figure is None:
        db.add(
            ConversationTurn(
                id=TURN_FIGURE_ID,
                public_ref=TURN_FIGURE_PUBLIC_REF,
                conversation_id=CONV_MINA_ID,
                client_request_id="client_demo_figure_001",
                route=TURN_ROUTE_DOMAIN_RAG,
                domain_id=DOMAIN_MANUALS_ID,
                status=TURN_STATUS_COMPLETED,
                user_message="Where is the relief valve?",
                assistant_answer="The relief valve is downstream of the pump [1].",
                composer_ref_fingerprint=EMPTY_COMPOSER_REF_FINGERPRINT,
                created_at=SEED_CLOCK,
                started_at=SEED_CLOCK,
                completed_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
    else:
        figure.public_ref = TURN_FIGURE_PUBLIC_REF
        figure.status = TURN_STATUS_COMPLETED
        figure.domain_id = DOMAIN_MANUALS_ID

    redacted = db.get(ConversationTurn, TURN_REDACTED_ID)
    if redacted is None:
        db.add(
            ConversationTurn(
                id=TURN_REDACTED_ID,
                public_ref=TURN_REDACTED_PUBLIC_REF,
                conversation_id=CONV_MINA_ID,
                client_request_id="client_demo_redacted_001",
                route=TURN_ROUTE_DIRECT_LLM,
                status=TURN_STATUS_REDACTED,
                user_message="Preserved redacted question.",
                assistant_answer=None,
                composer_ref_fingerprint=EMPTY_COMPOSER_REF_FINGERPRINT,
                created_at=SEED_CLOCK,
                started_at=SEED_CLOCK,
                completed_at=SEED_CLOCK,
                updated_at=SEED_CLOCK,
            )
        )
    else:
        redacted.public_ref = TURN_REDACTED_PUBLIC_REF
        redacted.status = TURN_STATUS_REDACTED
        redacted.assistant_answer = None
    db.flush()

    evidence = db.get(ConversationTurnEvidenceRef, EVIDENCE_FIGURE_ID)
    if evidence is None:
        db.add(
            ConversationTurnEvidenceRef(
                id=EVIDENCE_FIGURE_ID,
                public_ref=EVIDENCE_FIGURE_PUBLIC_REF,
                turn_id=TURN_FIGURE_ID,
                evidence_order=1,
                source_document_id=SOURCE_PUMP_ID,
                source_block_id="block_valve_figure",
                citation_label="1",
                source_label="Pump manual",
                excerpt="Figure 4 places the relief valve downstream of the pump.",
                created_at=SEED_CLOCK,
            )
        )
    else:
        evidence.public_ref = EVIDENCE_FIGURE_PUBLIC_REF
        evidence.turn_id = TURN_FIGURE_ID
        evidence.source_document_id = SOURCE_PUMP_ID


def _upsert_tokens(db: Session, *, now: datetime) -> None:
    for entry in _token_fixtures(now=now):
        token_hash = TOKEN_HASHES[entry.fixture_key]
        token = db.get(ComposerRefToken, entry.token_id)
        if token is None:
            db.add(
                ComposerRefToken(
                    id=entry.token_id,
                    token_hash=token_hash,
                    owner_user_id=entry.owner_user_id,
                    ref_kind=entry.ref_kind,
                    target_id=entry.target_id,
                    domain_id=entry.domain_id,
                    safe_label=entry.safe_label,
                    safe_description=entry.fixture_key,
                    expires_at=entry.expires_at,
                    consumed_at=entry.consumed_at,
                    created_at=SEED_CLOCK,
                )
            )
            continue
        token.token_hash = token_hash
        token.owner_user_id = entry.owner_user_id
        token.ref_kind = entry.ref_kind
        token.target_id = entry.target_id
        token.domain_id = entry.domain_id
        token.safe_label = entry.safe_label
        token.safe_description = entry.fixture_key
        token.expires_at = entry.expires_at
        token.consumed_at = entry.consumed_at


def _upsert_accepted_refs(db: Session) -> None:
    for entry in _accepted_ref_fixtures():
        ref = db.get(ConversationTurnComposerRef, entry.accepted_id)
        if ref is None:
            db.add(
                ConversationTurnComposerRef(
                    id=entry.accepted_id,
                    public_ref=entry.public_ref,
                    turn_id=entry.turn_id,
                    ref_order=entry.ref_order,
                    ref_kind=entry.ref_kind,
                    safe_label=entry.safe_label,
                    safe_description=entry.safe_description,
                    domain_id=entry.domain_id,
                    source_document_id=entry.source_document_id,
                    source_block_id=entry.source_block_id,
                    evidence_ref_id=entry.evidence_ref_id,
                    prompt_template_id=entry.prompt_template_id,
                    redacted_at=entry.redacted_at,
                    created_at=SEED_CLOCK,
                )
            )
            continue
        ref.public_ref = entry.public_ref
        ref.turn_id = entry.turn_id
        ref.ref_order = entry.ref_order
        ref.ref_kind = entry.ref_kind
        ref.safe_label = entry.safe_label
        ref.safe_description = entry.safe_description
        ref.domain_id = entry.domain_id
        ref.source_document_id = entry.source_document_id
        ref.source_block_id = entry.source_block_id
        ref.evidence_ref_id = entry.evidence_ref_id
        ref.prompt_template_id = entry.prompt_template_id
        ref.redacted_at = entry.redacted_at


def seed_composer_ref_fixtures(
    db: Session,
    *,
    reset: bool = False,
    environment: str | None = None,
    allow_test_seed: str | None = None,
    now: datetime | None = None,
) -> None:
    require_seed_writes_allowed(environment=environment, allow_test_seed=allow_test_seed)
    clock = now or utc_now()
    seed_prompt_template_fixtures(
        db,
        reset=reset,
        environment=environment,
        allow_test_seed=allow_test_seed,
    )
    _ensure_runtime_parents(db)
    _upsert_user(db, user_id=USER_MINA_ID, username="member.mina")
    _upsert_user(db, user_id=USER_NOAH_ID, username="member.noah")
    db.flush()
    _upsert_domain(
        db,
        domain_id=DOMAIN_MANUALS_ID,
        display_name="Equipment Manuals",
        state=DOMAIN_STATE_RUNNING,
    )
    _upsert_domain(
        db,
        domain_id=DOMAIN_POLICIES_ID,
        display_name="Workplace Policies",
        state=DOMAIN_STATE_STOPPED,
    )
    db.flush()
    _upsert_source(db)
    db.flush()
    _upsert_conversation_graph(db)
    db.flush()
    _upsert_tokens(db, now=clock)
    _upsert_accepted_refs(db)
    db.commit()


def public_accepted_ref_projection(ref: ConversationTurnComposerRef) -> dict[str, object]:
    return {
        "id": ref.public_ref,
        "kind": ref.ref_kind,
        "order": ref.ref_order,
        "label": ref.safe_label,
        "description": ref.safe_description,
    }


def list_seeded_token_fixture_keys(db: Session) -> set[str]:
    rows = db.scalars(select(ComposerRefToken).where(ComposerRefToken.safe_description.is_not(None)))
    return {row.safe_description for row in rows if row.safe_description}
