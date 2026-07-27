from __future__ import annotations

import ast
from pathlib import Path

import pytest

from context_engine.models import TURN_ROUTE_DIRECT_LLM, TURN_ROUTE_DOMAIN_RAG
from context_engine.services.chat_turns import (
    ChatTurnError,
    _validate_effective_route,
    classify_turn_route,
    normalize_optional_domain_id,
)

_APP_ROOT = Path(__file__).resolve().parents[1]
_PRODUCTION_ROOT = _APP_ROOT / "context_engine"


def test_m07_ae1_no_domain_general_classifies_direct_llm() -> None:
    route, domain_id = classify_turn_route(message="What is 2+2?", domain_id=None)
    assert route == TURN_ROUTE_DIRECT_LLM
    assert domain_id is None


def test_m07_ae3_explicit_domain_classifies_domain_rag_even_for_general_message() -> None:
    route, domain_id = classify_turn_route(message="What is 2+2?", domain_id="ops-manual")
    assert route == TURN_ROUTE_DOMAIN_RAG
    assert domain_id == "ops-manual"


def test_m07_ae2_domain_seeking_without_domain_raises_domain_required() -> None:
    with pytest.raises(ChatTurnError) as failure:
        classify_turn_route(
            message="According to the manual, where is the valve?",
            domain_id=None,
        )
    assert failure.value.status_code == 422
    assert failure.value.code == "domain_required"


@pytest.mark.parametrize(
    "raw",
    (
        "Bad Domain!",
        "A",
        "UPPERCASE",
        "has spaces",
        "-leading-hyphen",
    ),
)
def test_malformed_domain_id_fails_validation_before_classification(raw: str) -> None:
    with pytest.raises(ChatTurnError) as failure:
        normalize_optional_domain_id(raw)
    assert failure.value.status_code == 422
    assert failure.value.code == "validation_error"


def test_normalize_optional_domain_id_accepts_valid_slug() -> None:
    assert normalize_optional_domain_id("ops-manual") == "ops-manual"
    assert normalize_optional_domain_id(None) is None


def test_impossible_domain_rag_without_domain_fails_closed() -> None:
    with pytest.raises(ChatTurnError) as failure:
        _validate_effective_route(route=TURN_ROUTE_DOMAIN_RAG, domain_id=None)
    assert failure.value.code == "domain_required"


def test_impossible_direct_llm_with_domain_fails_closed() -> None:
    with pytest.raises(ChatTurnError) as failure:
        _validate_effective_route(route=TURN_ROUTE_DIRECT_LLM, domain_id="ops-manual")
    assert failure.value.code == "validation_error"


def test_unknown_route_fails_closed() -> None:
    with pytest.raises(ChatTurnError) as failure:
        _validate_effective_route(route="client_chosen", domain_id=None)
    assert failure.value.code == "validation_error"


def test_claim_turn_has_zero_production_callers() -> None:
    callers: list[str] = []
    for path in _PRODUCTION_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name != "claim_turn":
                continue
            # Definition site is not a caller.
            if path.name == "chat_turns.py" and isinstance(func, ast.Name):
                # Still count attribute-less Name calls inside the module body
                # only when they are not the function definition itself.
                pass
            callers.append(f"{path.relative_to(_APP_ROOT)}:{node.lineno}")

    # Filter out the definition: `def claim_turn(` is not a Call node, so any
    # remaining hits inside production are real callers.
    assert callers == [], f"unexpected production claim_turn callers: {callers}"
