from __future__ import annotations

from context_engine.config import Settings
from context_engine.db import create_db_engine, create_session_factory
from context_engine.services.auth import seed_admin


def bootstrap_initial_admin(settings: Settings | None = None) -> None:
    app_settings = settings or Settings()
    if not app_settings.admin_username or not app_settings.admin_password:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD are required for administrator bootstrap.")

    engine = create_db_engine(app_settings)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as db:
            user = seed_admin(db, app_settings)
            if user is None:
                raise RuntimeError("Administrator bootstrap configuration is incomplete.")
    finally:
        engine.dispose()


def main() -> None:
    bootstrap_initial_admin()
    print("Administrator bootstrap complete.")


if __name__ == "__main__":
    main()
