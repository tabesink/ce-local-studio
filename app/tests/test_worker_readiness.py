"""P10-03: worker internal readiness before claim (no admin gate)."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_engine.adapters.object_storage import ObjectStorageError
from context_engine.config import Settings
from context_engine.services import readiness as readiness_module
from context_engine.services.readiness import (
    SUPPORTED_ALEMBIC_HEAD,
    ReadinessError,
    check_worker_readiness,
)
from context_engine.worker import WORKER_HEARTBEAT_FILENAME, clear_worker_heartbeat, touch_worker_heartbeat


class _HealthySchemaDb:
    def execute(self, _statement: object) -> None:
        return None

    def scalar(self, statement: object) -> str | None:
        if "alembic_version" in str(statement):
            return SUPPORTED_ALEMBIC_HEAD
        return None


class _BadSchemaDb:
    def execute(self, _statement: object) -> None:
        return None

    def scalar(self, _statement: object) -> str:
        return "deadbeef0001"


@pytest.fixture(autouse=True)
def _bypass_catalog_compatibility_for_fake_dbs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(readiness_module, "check_catalog_compatibility", lambda _db: None)


def test_worker_readiness_ok_without_administrator(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    check_worker_readiness(_HealthySchemaDb(), settings)
    assert (tmp_path / "source-storage" / "objects").is_dir()


def test_worker_readiness_rejects_incompatible_schema(tmp_path: Path) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))
    with pytest.raises(ReadinessError) as exc_info:
        check_worker_readiness(_BadSchemaDb(), settings)
    assert exc_info.value.reason == "schema_incompatible"


def test_worker_readiness_rejects_catalog_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))

    def _fail(_db: object) -> None:
        raise ReadinessError("schema_incompatible")

    monkeypatch.setattr(readiness_module, "check_catalog_compatibility", _fail)
    with pytest.raises(ReadinessError) as exc_info:
        check_worker_readiness(_HealthySchemaDb(), settings)
    assert exc_info.value.reason == "schema_incompatible"


def test_worker_readiness_rejects_store_probe_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(testing=True, source_storage_root=str(tmp_path / "source-storage"))

    def _fail(_settings: object) -> None:
        raise ObjectStorageError("Object unavailable.")

    monkeypatch.setattr(readiness_module, "probe_object_store", _fail)
    with pytest.raises(ReadinessError) as exc_info:
        check_worker_readiness(_HealthySchemaDb(), settings)
    assert exc_info.value.reason == "object_store_unavailable"


def test_clear_worker_heartbeat_removes_stale_file(tmp_path: Path) -> None:
    path = tmp_path / "runtimes" / WORKER_HEARTBEAT_FILENAME
    touch_worker_heartbeat(path)
    assert path.is_file()
    clear_worker_heartbeat(path)
    assert not path.exists()
