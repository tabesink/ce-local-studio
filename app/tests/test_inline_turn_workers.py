"""P10-03: CE_INLINE_TURN_WORKERS split from CONTEXT_ENGINE_TESTING."""

from __future__ import annotations

from context_engine.config import Settings


def test_inline_defaults_to_testing_when_unset() -> None:
    assert Settings(testing=True, inline_turn_workers=None).inline_turn_workers_enabled() is True
    assert Settings(testing=False, inline_turn_workers=None).inline_turn_workers_enabled() is False


def test_inline_false_under_testing_disables_api_inline() -> None:
    assert Settings(testing=True, inline_turn_workers=False).inline_turn_workers_enabled() is False


def test_inline_true_without_testing_never_enables() -> None:
    assert Settings(testing=False, inline_turn_workers=True).inline_turn_workers_enabled() is False


def test_inline_true_with_testing_enables() -> None:
    assert Settings(testing=True, inline_turn_workers=True).inline_turn_workers_enabled() is True
