"""P7-06 U3 unit proofs for turn lease heartbeat helpers (no PostgreSQL)."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from context_engine.db import Base, utc_now
from context_engine.models import (
    TURN_ROUTE_DIRECT_LLM,
    TURN_STATUS_CANCELLED,
    TURN_STATUS_RUNNING,
    Conversation,
    ConversationTurn,
    User,
)
from context_engine.services.chat_turns import (
    _heartbeat_turn_lease,
    _lease_heartbeat_seconds,
    _turn_lease_current,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _running_turn(db: Session, *, owner: str = "worker-a", generation: int = 1) -> ConversationTurn:
    now = utc_now()
    user = User(
        id=str(uuid4()),
        username=f"u_{uuid4().hex[:8]}",
        password_hash="x",
        role="member",
        is_disabled=False,
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )
    conversation = Conversation(
        id=str(uuid4()),
        public_ref=f"conv_{uuid4().hex}",
        owner_user_id=user.id,
        title="t",
        version=1,
        created_at=now,
        updated_at=now,
    )
    turn = ConversationTurn(
        id=str(uuid4()),
        public_ref=f"turn_{uuid4().hex}",
        conversation_id=conversation.id,
        client_request_id=f"req_{uuid4().hex}",
        status=TURN_STATUS_RUNNING,
        route=TURN_ROUTE_DIRECT_LLM,
        user_message="hi",
        composer_ref_fingerprint="0" * 64,
        lease_owner=owner,
        lease_expires_at=now + timedelta(seconds=30),
        execution_generation=generation,
        claimable_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add_all([user, conversation, turn])
    db.commit()
    db.refresh(turn)
    return turn


def test_lease_heartbeat_seconds_is_one_third_floor_one() -> None:
    assert _lease_heartbeat_seconds(9) == 3
    assert _lease_heartbeat_seconds(2) == 1
    assert _lease_heartbeat_seconds(1) == 1


def test_heartbeat_extends_expiry_when_owner_generation_and_running_match() -> None:
    db = _session()
    turn = _running_turn(db)
    before = turn.lease_expires_at
    assert _heartbeat_turn_lease(
        db,
        turn.id,
        owner="worker-a",
        lease_seconds=60,
        execution_generation=1,
    )
    db.refresh(turn)
    assert turn.lease_expires_at is not None
    assert before is not None
    assert turn.lease_expires_at > before
    assert turn.execution_generation == 1


def test_heartbeat_rejects_wrong_owner_generation_or_non_running() -> None:
    db = _session()
    turn = _running_turn(db)
    assert not _heartbeat_turn_lease(
        db,
        turn.id,
        owner="other",
        lease_seconds=60,
        execution_generation=1,
    )
    assert not _heartbeat_turn_lease(
        db,
        turn.id,
        owner="worker-a",
        lease_seconds=60,
        execution_generation=99,
    )
    turn.status = TURN_STATUS_CANCELLED
    db.commit()
    assert not _turn_lease_current(
        turn,
        owner="worker-a",
        execution_generation=1,
    )
    assert not _heartbeat_turn_lease(
        db,
        turn.id,
        owner="worker-a",
        lease_seconds=60,
        execution_generation=1,
    )
