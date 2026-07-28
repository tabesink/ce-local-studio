"""P10-03: SIGTERM/SIGINT stop-claim and interruptible idle drain."""

from __future__ import annotations

from typing import Any

from context_engine.worker import run_loop


class _CountingWorker:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self, _db: Any) -> bool:
        self.calls += 1
        return False


class _BusyThenIdleWorker:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self, _db: Any) -> bool:
        self.calls += 1
        return self.calls == 1


def test_run_loop_stops_new_claims_when_should_continue_false() -> None:
    worker = _CountingWorker()
    sleeps: list[float] = []
    state = {"n": 0}

    def should_continue() -> bool:
        state["n"] += 1
        return state["n"] <= 2

    def sleep_fn(seconds: float) -> None:
        sleeps.append(seconds)

    run_loop(
        session_factory=lambda: object(),
        prep_worker=worker,
        index_worker=_CountingWorker(),
        turn_worker=_CountingWorker(),
        delete_worker=_CountingWorker(),
        idle_seconds=0.01,
        sleep_fn=sleep_fn,
        should_continue=should_continue,
    )
    assert worker.calls == 2
    assert len(sleeps) == 2


def test_run_loop_finishes_in_flight_pass_then_stops() -> None:
    busy = _BusyThenIdleWorker()
    state = {"n": 0}

    def should_continue() -> bool:
        # Allow first iteration (busy claim), then stop before a second claim cycle.
        state["n"] += 1
        return state["n"] <= 1

    run_loop(
        session_factory=lambda: object(),
        prep_worker=busy,
        index_worker=_CountingWorker(),
        turn_worker=_CountingWorker(),
        delete_worker=_CountingWorker(),
        idle_seconds=0.01,
        sleep_fn=lambda _s: None,
        should_continue=should_continue,
    )
    assert busy.calls == 1


def test_run_loop_idle_sleep_uses_injected_sleep_fn() -> None:
    """Interruptible shutdown is wired via sleep_fn (Event.wait in main)."""
    called: list[float] = []

    def should_continue() -> bool:
        return len(called) < 1

    run_loop(
        session_factory=lambda: object(),
        prep_worker=_CountingWorker(),
        index_worker=_CountingWorker(),
        turn_worker=_CountingWorker(),
        delete_worker=_CountingWorker(),
        idle_seconds=1.5,
        sleep_fn=lambda seconds: called.append(seconds),
        should_continue=should_continue,
    )
    assert called == [1.5]
