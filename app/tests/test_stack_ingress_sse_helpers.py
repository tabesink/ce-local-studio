"""Unit altitude for P12-05 SSE inter-arrival gate (no Docker / no network)."""

from __future__ import annotations

import pytest

from context_engine.dev.ingress_sse_proof import (
    SSE_DELTA_INTER_ARRIVAL_EPSILON_MS,
    assert_incremental_answer_deltas,
    inter_arrival_ok,
)


def test_inter_arrival_rejects_fewer_than_two_deltas() -> None:
    assert inter_arrival_ok([0.0]) is False
    assert inter_arrival_ok([]) is False


def test_inter_arrival_rejects_same_burst_within_epsilon() -> None:
    assert inter_arrival_ok([100.0, 100.0 + SSE_DELTA_INTER_ARRIVAL_EPSILON_MS]) is False
    assert inter_arrival_ok([100.0, 110.0], epsilon_ms=25.0) is False


def test_inter_arrival_accepts_spaced_deltas() -> None:
    assert inter_arrival_ok([100.0, 100.0 + SSE_DELTA_INTER_ARRIVAL_EPSILON_MS + 1.0]) is True


def test_assert_incremental_answer_deltas_filters_non_delta_frames() -> None:
    frames = [
        (0.0, "turn.accepted"),
        (10.0, "answer.delta"),
        (50.0, "answer.delta"),
        (80.0, "turn.completed"),
    ]
    assert_incremental_answer_deltas(frames)


def test_assert_incremental_answer_deltas_fails_buffered_blob() -> None:
    frames = [
        (0.0, "answer.delta"),
        (5.0, "answer.delta"),
        (10.0, "turn.completed"),
    ]
    with pytest.raises(AssertionError, match="inter-arrival"):
        assert_incremental_answer_deltas(frames)
