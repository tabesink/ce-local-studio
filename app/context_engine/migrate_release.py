"""Release-step migrate entrypoint: Path 1 preflight → alembic upgrade → post-check.

Compose and scripts/dev.sh must invoke this module instead of bare
`alembic upgrade head`. API/worker processes must never call it.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from context_engine.config import Settings
from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD
from context_engine.services.schema_compatibility import (
    REASON_CURRENT_TARGET_OK,
    REASON_EMPTY_OK,
    REASON_SNAPSHOT_HEAD_MISMATCH,
    classify_with_ordered_revisions,
    collect_inventory_from_engine,
    load_expected_snapshot,
    snapshot_path_for_head,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class MigrateReleaseError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(APP_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(APP_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def ordered_revisions(config: Config | None = None) -> tuple[str, ...]:
    cfg = config or _alembic_config(Settings().database_url)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if heads != [SUPPORTED_ALEMBIC_HEAD]:
        raise MigrateReleaseError(REASON_SNAPSHOT_HEAD_MISMATCH)
    revisions: list[str] = []
    for revision in script.walk_revisions(base="base", head="heads"):
        revisions.append(revision.revision)
    revisions.reverse()
    return tuple(revisions)


@contextmanager
def _bound_database_url_env(database_url: str):
    """migrations/env.py prefers CONTEXT_ENGINE_DATABASE_URL over alembic.ini."""
    key = "CONTEXT_ENGINE_DATABASE_URL"
    previous = os.environ.get(key)
    os.environ[key] = database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def run_migrate_release(
    *,
    database_url: str | None = None,
    upgrade=command.upgrade,
) -> str:
    """Run preflight, upgrade when needed, and post-verify. Returns accept reason."""
    settings = Settings(database_url=database_url) if database_url else Settings()
    target_url = settings.database_url
    config = _alembic_config(target_url)

    snapshot_path = snapshot_path_for_head(SUPPORTED_ALEMBIC_HEAD)
    if not snapshot_path.is_file():
        raise MigrateReleaseError(REASON_SNAPSHOT_HEAD_MISMATCH)
    try:
        expected = load_expected_snapshot(SUPPORTED_ALEMBIC_HEAD)
    except (FileNotFoundError, ValueError) as exc:
        raise MigrateReleaseError(REASON_SNAPSHOT_HEAD_MISMATCH) from exc

    ordered = ordered_revisions(config)
    with _bound_database_url_env(target_url):
        engine = create_engine(target_url, pool_pre_ping=True)
        try:
            before = collect_inventory_from_engine(engine)
            before_fp = before.fingerprint()
            before_rev = before.alembic_revision
            verdict = classify_with_ordered_revisions(
                before,
                policy="migrate",
                ordered_revisions=ordered,
                expected=expected,
                supported_head=SUPPORTED_ALEMBIC_HEAD,
            )
            if not verdict.accepted:
                after = collect_inventory_from_engine(engine)
                if after.fingerprint() != before_fp or after.alembic_revision != before_rev:
                    raise MigrateReleaseError("catalog_mutated_during_refuse")
                raise MigrateReleaseError(verdict.reason)

            upgrade(config, "head")
            after = collect_inventory_from_engine(engine)
            post = classify_with_ordered_revisions(
                after,
                policy="startup",
                ordered_revisions=ordered,
                expected=expected,
                supported_head=SUPPORTED_ALEMBIC_HEAD,
            )
            if not post.accepted or post.reason != REASON_CURRENT_TARGET_OK:
                raise MigrateReleaseError(
                    post.reason if not post.accepted else "post_upgrade_mismatch"
                )
            return (
                verdict.reason
                if verdict.reason in {REASON_EMPTY_OK, REASON_CURRENT_TARGET_OK}
                else post.reason
            )
        finally:
            engine.dispose()


def main() -> None:
    try:
        reason = run_migrate_release()
    except MigrateReleaseError as exc:
        print(f"migrate_release refused: {exc.reason}", file=sys.stderr)
        print(
            "action: provision a fresh database or restore a current-head backup; "
            "do not force upgrade",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    print(f"migrate_release ok: {reason}")


if __name__ == "__main__":
    main()
