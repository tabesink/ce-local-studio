"""Pure helpers for P12-05 ingress SSE delta timing proofs (no network I/O)."""

from __future__ import annotations

from typing import Sequence

# Distinguishes proxy one-blob flush / same-readline coalescing from multi-chunk streaming.
# Not a product SSE timing contract — proof-helper only (plan AE1 / U3).
SSE_DELTA_INTER_ARRIVAL_EPSILON_MS = 25.0


def answer_delta_timestamps_ms(frames: Sequence[tuple[float, str]]) -> list[float]:
    """Return monotonic timestamps (ms) for frames whose type is answer.delta."""
    return [ts_ms for ts_ms, event_type in frames if event_type == "answer.delta"]


def inter_arrival_ok(
    delta_timestamps_ms: Sequence[float],
    *,
    epsilon_ms: float = SSE_DELTA_INTER_ARRIVAL_EPSILON_MS,
) -> bool:
    """True when ≥2 deltas exist and each consecutive pair is separated by > epsilon_ms."""
    if len(delta_timestamps_ms) < 2:
        return False
    ordered = sorted(delta_timestamps_ms)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if (later - earlier) <= epsilon_ms:
            return False
    return True


def assert_incremental_answer_deltas(
    frames: Sequence[tuple[float, str]],
    *,
    epsilon_ms: float = SSE_DELTA_INTER_ARRIVAL_EPSILON_MS,
) -> None:
    deltas = answer_delta_timestamps_ms(frames)
    if len(deltas) < 2:
        raise AssertionError(f"need ≥2 answer.delta frames, got {len(deltas)}")
    if not inter_arrival_ok(deltas, epsilon_ms=epsilon_ms):
        raise AssertionError(
            f"answer.delta inter-arrival ≤ {epsilon_ms}ms "
            f"(buffered blob or coalesced read); timestamps_ms={list(deltas)}"
        )
