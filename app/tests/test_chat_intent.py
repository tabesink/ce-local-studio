from __future__ import annotations

import pytest

from context_engine.services.chat_intent import requires_domain

# AE6 closed Phase 1 pattern matrix (P7-02 / M-07).
_DOMAIN_SEEKING_FIXTURES = (
    "According to the manual, where is the valve?",
    "Summarize the SOP for lockout.",
    "What does the policy say about PPE?",
    "Find the procedure in the document.",
    "Where is that covered in the knowledge domain?",
)

_GENERAL_FIXTURES = (
    "What is 2+2?",
    "Explain recursion in plain language.",
    "Help me brainstorm a meeting agenda.",
)


@pytest.mark.parametrize("message", _DOMAIN_SEEKING_FIXTURES)
def test_m07_ae6_domain_seeking_patterns_require_domain(message: str) -> None:
    assert requires_domain(message) is True


@pytest.mark.parametrize("message", _GENERAL_FIXTURES)
def test_m07_ae6_general_messages_do_not_require_domain(message: str) -> None:
    assert requires_domain(message) is False
