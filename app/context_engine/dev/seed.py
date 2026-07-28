from __future__ import annotations

import argparse
import sys

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.dev.seed_composer_refs import seed_composer_ref_fixtures
from context_engine.dev.seed_gate import SeedGateError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gated Context Engine composer seed entry.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove non-fixture prompt templates after upserting fixtures (CE_ENVIRONMENT=test only).",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    db = session_factory()
    try:
        seed_composer_ref_fixtures(db, reset=args.reset)
    except SeedGateError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        db.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
