from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.services.domains import DomainDeleteWorker
from context_engine.services.indexing import SourceIndexWorker
from context_engine.services.runtime_config import validate_config_encryption_key
from context_engine.services.sources import SourceDeleteWorker, SourcePreparationWorker
from context_engine.services.structured_logging import configure_json_logging, safe_log

logger = logging.getLogger(__name__)

WORKER_HEARTBEAT_FILENAME = ".ce-worker-heartbeat"


class _RunOnceWorker(Protocol):
    def run_once(self, db: Any) -> bool: ...


class _CompositeDeleteWorker:
    """Prefer source cleanup, then domain delete, in one worker slot."""

    def __init__(self, settings: Settings) -> None:
        self._source = SourceDeleteWorker(settings)
        self._domain = DomainDeleteWorker(settings)

    def run_once(self, db: Any) -> bool:
        return bool(self._source.run_once(db) or self._domain.run_once(db))


def touch_worker_heartbeat(path: Path | str) -> None:
    """Create or refresh the worker heartbeat file used by compose healthchecks."""
    heartbeat = Path(path)
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.touch()


def run_once_pass(
    prep_worker: _RunOnceWorker,
    index_worker: _RunOnceWorker,
    delete_worker: _RunOnceWorker,
    db: Any,
) -> bool:
    """Claim at most one unit of work in prep → index → delete order."""
    return bool(prep_worker.run_once(db) or index_worker.run_once(db) or delete_worker.run_once(db))


def build_workers(settings: Settings) -> dict[str, _RunOnceWorker]:
    return {
        "prep": SourcePreparationWorker(settings),
        "index": SourceIndexWorker(settings),
        "delete": _CompositeDeleteWorker(settings),
    }


def run_loop(
    *,
    session_factory: Callable[[], Any],
    prep_worker: _RunOnceWorker,
    index_worker: _RunOnceWorker,
    delete_worker: _RunOnceWorker,
    idle_seconds: float,
    sleep_fn: Callable[[float], None] = time.sleep,
    should_continue: Callable[[], bool] | None = None,
    heartbeat_path: Path | str | None = None,
) -> None:
    """Round-robin lease workers until ``should_continue`` returns false."""
    continue_fn = should_continue or (lambda: True)
    while continue_fn():
        db = session_factory()
        did_work = False
        try:
            did_work = run_once_pass(prep_worker, index_worker, delete_worker, db)
        except Exception:
            safe_log(
                logger,
                "stack_worker.iteration_failed",
                safe_error_code="worker_error",
                outcome="failed",
            )
            did_work = False
        finally:
            close = getattr(db, "close", None)
            if callable(close):
                close()
        if heartbeat_path is not None:
            try:
                touch_worker_heartbeat(heartbeat_path)
            except Exception:
                safe_log(
                    logger,
                    "stack_worker.heartbeat_failed",
                    safe_error_code="heartbeat_write_failed",
                    outcome="failed",
                )
        if not did_work:
            sleep_fn(idle_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context Engine lease worker poll loop")
    parser.parse_args(argv)

    settings = Settings.from_env()
    configure_json_logging()
    validate_config_encryption_key(settings)

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    workers = build_workers(settings)
    heartbeat_path = Path(settings.domain_runtime_root) / WORKER_HEARTBEAT_FILENAME
    safe_log(logger, "stack_worker.started", outcome="succeeded")
    try:
        run_loop(
            session_factory=session_factory,
            prep_worker=workers["prep"],
            index_worker=workers["index"],
            delete_worker=workers["delete"],
            idle_seconds=float(settings.worker_idle_seconds),
            heartbeat_path=heartbeat_path,
        )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
