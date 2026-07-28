"""P12-04 U6 unit tests for post-restore LightRAG rebuild helpers (AE4 rebuild half).

No Docker/LightRAG required. Topology credit:
``app/tests/test_lightrag_real_runtime_integration.py`` — not this drill.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.stack_drill_seed import DOMAIN_ID, SOURCE_ID, SOURCE_PUBLIC_REF
from scripts.stack_lightrag_rebuild_drill import (
    THREE_FILE_COMPOSE_MATRIX,
    TOPOLOGY_CREDIT_PATH,
    assert_backup_excludes_runtime_paths,
    assert_live_runtime_bind,
    assert_rebuild_store_kind,
    assert_runtime_root_empty,
    assert_three_file_compose_matrix,
    check_mapped_evidence,
    clear_runtime_root,
    compose_config_command,
    compose_up_command,
    domain_start_http_path,
    evaluate_ae4_rebuild_done,
    index_retry_http_path,
    main,
    run_lightrag_rebuild_drill,
    three_file_compose_files,
)


def test_three_file_compose_file_list() -> None:
    files = three_file_compose_files()
    assert files == [
        "compose.stack.yml",
        "compose.stack.minio.yml",
        "compose.stack.live.yml",
    ]
    assert files == list(THREE_FILE_COMPOSE_MATRIX)
    assert assert_three_file_compose_matrix(files) == []
    assert assert_three_file_compose_matrix(None) == []

    # Pairwise overlays alone are incomplete for AE4 rebuild.
    missing = assert_three_file_compose_matrix(
        ["compose.stack.yml", "compose.stack.minio.yml"]
    )
    assert missing == ["three_file_matrix_missing:compose.stack.live.yml"]

    missing_minio = assert_three_file_compose_matrix(
        ["compose.stack.yml", "compose.stack.live.yml"]
    )
    assert "compose.stack.minio.yml" in missing_minio[0]

    # Basename match works with app/-prefixed paths.
    assert (
        assert_three_file_compose_matrix(
            [
                "app/compose.stack.yml",
                "app/compose.stack.minio.yml",
                "app/compose.stack.live.yml",
            ]
        )
        == []
    )

    config_cmd = compose_config_command()
    assert config_cmd[:2] == ["docker", "compose"]
    assert config_cmd[-1] == "config"
    assert config_cmd.count("-f") == 3
    for name in THREE_FILE_COMPOSE_MATRIX:
        assert name in config_cmd

    up_cmd = compose_up_command(project="ce-drill-restore", env_file=".env.stack.local")
    assert "up" in up_cmd and "-d" in up_cmd and "--build" in up_cmd
    assert "-p" in up_cmd and "ce-drill-restore" in up_cmd


def test_empty_runtime_precondition(tmp_path: Path) -> None:
    root = tmp_path / "live-runtime"
    # Missing path is empty (mkdir later).
    assert assert_runtime_root_empty(root) == []

    root.mkdir()
    assert assert_runtime_root_empty(root) == []

    (root / "domain-a").mkdir()
    assert assert_runtime_root_empty(root) == ["runtime_root_not_empty"]

    assert clear_runtime_root(root, dry_run=False) == []
    assert assert_runtime_root_empty(root) == []
    assert not any(root.iterdir())

    # Named volume only refused; bind env required.
    assert "named_volume_only_refused" in assert_live_runtime_bind(
        runtime_root=str(root),
        using_named_volume_only=True,
    )
    assert f"CE_STACK_LIVE_RUNTIME_ROOT_missing" in assert_live_runtime_bind(
        runtime_root=None
    )
    assert "runtime_root_not_absolute" in assert_live_runtime_bind(
        runtime_root="relative/runtime"
    )


def test_refuse_filesystem_only_rebuild_as_evidence() -> None:
    assert assert_rebuild_store_kind("s3") == []
    assert assert_rebuild_store_kind("minio") == []
    assert "filesystem_rebuild_refused:filesystem" in assert_rebuild_store_kind(
        "filesystem"
    )
    assert "filesystem_rebuild_refused:missing" in assert_rebuild_store_kind("")

    rc = run_lightrag_rebuild_drill(
        runtime_root="/tmp/ce-p12-04-live-runtime-empty",
        store_kind="filesystem",
        dry_run=True,
    )
    assert rc == 1

    # Manifest store kind must be MinIO/s3; runtime paths forbidden in archive.
    assert assert_backup_excludes_runtime_paths(
        ["pg.dump", "objects/abc.bin", "consistency-manifest.json"],
        manifest={"storeKind": "s3", "runtimeVolumeExcluded": True},
    ) == []
    assert "backup_contains_runtime" in assert_backup_excludes_runtime_paths(
        ["pg.dump", "var/lib/stack-domain-runtimes/domain-a"]
    )[0]
    assert "filesystem_rebuild_refused:filesystem" in assert_backup_excludes_runtime_paths(
        [],
        manifest={"storeKind": "filesystem"},
    )


def test_pytest_only_credit_is_non_done_without_compose_drill() -> None:
    assert TOPOLOGY_CREDIT_PATH == (
        "app/tests/test_lightrag_real_runtime_integration.py"
    )

    pytest_only = evaluate_ae4_rebuild_done(
        three_file_matrix_ok=True,
        runtime_emptied=True,
        store_kind_ok=True,
        mapped_evidence_ok=True,
        compose_drill_path_exercised=False,
        pytest_topology_credit=True,
    )
    assert pytest_only["done"] is False
    assert pytest_only["pytestOnlyNonDone"] is True
    assert pytest_only["topologyCredit"] == TOPOLOGY_CREDIT_PATH
    assert pytest_only["composeDrillRequired"] is True

    compose_done = evaluate_ae4_rebuild_done(
        three_file_matrix_ok=True,
        runtime_emptied=True,
        store_kind_ok=True,
        mapped_evidence_ok=True,
        compose_drill_path_exercised=True,
        pytest_topology_credit=True,
    )
    assert compose_done["done"] is True
    assert compose_done["pytestOnlyNonDone"] is False

    # CLI evaluate-done: pytest-only exits non-zero.
    assert (
        main(
            [
                "--evaluate-done",
                "--three-file-ok",
                "--runtime-emptied",
                "--store-kind-ok",
                "--mapped-evidence-ok",
                "--no-compose-drill-exercised",
                "--pytest-topology-credit",
            ]
        )
        == 1
    )
    assert (
        main(
            [
                "--evaluate-done",
                "--compose-drill-exercised",
            ]
        )
        == 0
    )


def test_mapped_evidence_and_product_paths() -> None:
    assert domain_start_http_path(DOMAIN_ID).endswith(f"/admin/domains/{DOMAIN_ID}/start")
    assert "/index/retry" in index_retry_http_path(DOMAIN_ID, SOURCE_ID)

    ok = check_mapped_evidence(
        evidence_items=[
            {
                "documentPublicRef": SOURCE_PUBLIC_REF,
                "excerpt": "lockout",
                "label": "Drill Manual",
            }
        ],
        citations=[{"anchor": "block:1"}],
    )
    assert ok.ok is True

    missing = check_mapped_evidence(evidence_items=[])
    assert missing.ok is False
    assert missing.detail == "evidence_missing"

    absence = check_mapped_evidence(evidence_items=[], contracted_absence=True)
    assert absence.ok is True
    assert absence.detail == "contracted_absence"

    unmapped = check_mapped_evidence(
        evidence_items=[{"documentPublicRef": "doc_other", "rawHit": True}]
    )
    assert unmapped.ok is False


def test_dry_run_defaults_plan_without_docker(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        [
            "--runtime-root",
            "/tmp/ce-p12-04-live-runtime-empty",
            "--store-kind",
            "s3",
            "--dry-run",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "plan:compose_config" in captured.out
    assert "compose.stack.live.yml" in captured.out
    assert "compose.stack.minio.yml" in captured.out
    assert "plan:domain_start" in captured.out
    assert "plan:index_retry" in captured.out
    status = json.loads(_extract_json_object(captured.out))
    assert status["pytestOnlyNonDone"] is True
    assert status["done"] is False
    assert "non-DONE" in captured.err

    # Named-volume-only refuses even in dry-run.
    assert (
        main(
            [
                "--runtime-root",
                "/tmp/ce-p12-04-live-runtime-empty",
                "--named-volume-only",
                "--dry-run",
            ]
        )
        == 1
    )


def test_execute_hooks_with_injected_runners(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "stale").write_text("x", encoding="utf-8")
    ran: list[list[str]] = []

    def runner(argv: list[str] | tuple[str, ...]) -> int:
        ran.append(list(argv))
        return 0

    rc = run_lightrag_rebuild_drill(
        runtime_root=root,
        store_kind="minio",
        dry_run=False,
        clear_runtime=True,
        evidence_items=[
            {"documentPublicRef": SOURCE_PUBLIC_REF, "excerpt": "ok"},
        ],
        citations=[{"anchor": "p1"}],
        command_runner=runner,
        archive_listing=["pg.dump", "objects/a.bin"],
        manifest={"storeKind": "minio", "runtimeVolumeExcluded": True},
    )
    assert rc == 0
    assert assert_runtime_root_empty(root) == []
    assert any(cmd[-1] == "config" for cmd in ran)
    assert any("up" in cmd for cmd in ran)
    assert any("start" in " ".join(cmd) for cmd in ran)
    assert any("index/retry" in " ".join(cmd) for cmd in ran)


def _extract_json_object(text: str) -> str:
    # Curl plan lines may contain `${…}`; anchor on the DONE payload key.
    marker = '"topologyCredit"'
    idx = text.find(marker)
    if idx < 0:
        raise AssertionError(f"no AE4 status JSON in output:\n{text}")
    start = text.rfind("{", 0, idx)
    end = text.find("}", idx)
    if start < 0 or end < 0:
        raise AssertionError(f"unbalanced AE4 status JSON:\n{text}")
    # Extend to the matching closing brace for the status object.
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]
    raise AssertionError(f"unclosed AE4 status JSON:\n{text}")
