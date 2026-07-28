from __future__ import annotations

import os


ALLOWED_SEED_ENVIRONMENTS = frozenset({"development", "test"})


class SeedGateError(RuntimeError):
    """Raised when a gated seed write is attempted without the allowlist."""


def seed_writes_allowed(
    *,
    environment: str | None = None,
    allow_test_seed: str | None = None,
) -> bool:
    env = (environment if environment is not None else os.getenv("CE_ENVIRONMENT", "")).strip().lower()
    allow_raw = (
        allow_test_seed if allow_test_seed is not None else os.getenv("CE_ALLOW_TEST_SEED", "")
    ).strip().lower()
    allow = allow_raw in {"1", "true", "yes", "on"}
    return env in ALLOWED_SEED_ENVIRONMENTS and allow


def require_seed_writes_allowed(
    *,
    environment: str | None = None,
    allow_test_seed: str | None = None,
) -> None:
    if not seed_writes_allowed(environment=environment, allow_test_seed=allow_test_seed):
        raise SeedGateError(
            "Composer seed writes require CE_ENVIRONMENT=development|test "
            "and CE_ALLOW_TEST_SEED=true."
        )


def require_seed_reset_allowed(*, environment: str | None = None) -> None:
    env = (environment if environment is not None else os.getenv("CE_ENVIRONMENT", "")).strip().lower()
    if env != "test":
        raise SeedGateError(
            "Composer seed --reset is allowed only when CE_ENVIRONMENT=test."
        )
