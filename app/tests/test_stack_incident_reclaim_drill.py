"""P12-04 U5 unit tests for incident reclaim drill helpers.

Credit P10-03 single-worker reclaim — do not re-own. Algorithm authority:
``app/tests/test_postgres_turn_leases.py``. Compose kill+reclaim:
``docs/operations/compose-stack-runbook.md`` § Kill + single-worker turn-lease reclaim.
"""

from __future__ import annotations

import pytest

from scripts.stack_incident_reclaim_drill import (
    DRILL_MODES,
    FORBIDDEN_FORCE_COMPLETE_FLAGS,
    assert_missing_object_fail_safe,
    assert_no_force_complete_flags,
    collect_forbidden_force_complete_flags,
    compose_kill_command,
    compose_start_command,
    compute_lease_wait_seconds,
    evaluate_reclaim_observables,
    main,
    normalize_mode,
    run_api_worker_kill,
    run_missing_object,
    run_restore_then_reclaim,
    select_mode,
)


def test_mode_selection_accepts_matrix_modes() -> None:
    assert select_mode("api_worker_kill") == "api_worker_kill"
    assert select_mode("restore-then-reclaim") == "restore_then_reclaim"
    assert select_mode("MISSING_OBJECT") == "missing_object"
    assert DRILL_MODES == {"api_worker_kill", "restore_then_reclaim", "missing_object"}


def test_mode_selection_rejects_unknown_and_ha_claims() -> None:
    with pytest.raises(ValueError, match="unsupported_mode"):
        normalize_mode("ha_multi_replica")
    with pytest.raises(ValueError, match="unsupported_mode"):
        select_mode("single_worker_reclaim")  # P10-03 credited, not re-owned
    with pytest.raises(ValueError, match="unsupported_mode"):
        select_mode("force_complete")


def test_lease_wait_calculation_uses_shortened_lease_plus_pad() -> None:
    assert compute_lease_wait_seconds(10, pad_seconds=1) == 11.0
    assert compute_lease_wait_seconds(0.5, pad_seconds=0.1) == pytest.approx(0.6)
    # Zero lease still waits pad (never "force clear")
    assert compute_lease_wait_seconds(0, pad_seconds=2) == 2.0
    assert compute_lease_wait_seconds(5, pad_seconds=0, min_wait_seconds=8) == 8.0


def test_lease_wait_rejects_negative() -> None:
    with pytest.raises(ValueError, match="negative_lease"):
        compute_lease_wait_seconds(-1)
    with pytest.raises(ValueError, match="negative_pad"):
        compute_lease_wait_seconds(1, pad_seconds=-0.5)


def test_missing_object_fails_closed_on_silent_empty_and_eligibility() -> None:
    assert assert_missing_object_fail_safe(content_status=404) == []
    assert assert_missing_object_fail_safe(content_status=503, content_body=b"") == []
    assert assert_missing_object_fail_safe(
        content_status=200,
        content_body=b"",
    ) == ["silent_empty_success"]
    assert "eligibility_restored" in assert_missing_object_fail_safe(
        content_status=404,
        eligibility_restored=True,
    )
    assert "content_available_after_missing_object" in assert_missing_object_fail_safe(
        content_status=200,
        content_body=b"%PDF-1.4",
    )
    assert "recon_reported_ok" in assert_missing_object_fail_safe(
        content_status=404,
        recon_ok=True,
    )


def test_no_force_complete_flags_allowed() -> None:
    assert assert_no_force_complete_flags(["--dry-run", "--lease-seconds=10"]) == []
    assert "forbidden_flag:force-complete" in assert_no_force_complete_flags(
        ["--force-complete"]
    )
    assert "forbidden_flag:clear_lease" in assert_no_force_complete_flags(
        ["clear_lease=1"]
    )
    assert "forbidden_flag:bypass-generation" in assert_no_force_complete_flags(
        ["--bypass-generation"]
    )
    # Module constant covers R18 surface
    assert "force-complete" in FORBIDDEN_FORCE_COMPLETE_FLAGS
    assert "scrub-lease" in FORBIDDEN_FORCE_COMPLETE_FLAGS
    found = collect_forbidden_force_complete_flags(
        ["--force_complete", "--pad-seconds=1", "scrub_lease"]
    )
    assert found == ["force_complete", "scrub_lease"]


def test_reclaim_observables_reject_double_terminal_and_force_complete() -> None:
    assert (
        evaluate_reclaim_observables(
            services_restarted=True,
            reclaim_progressed=True,
        )
        == []
    )
    assert "double_terminal" in evaluate_reclaim_observables(
        services_restarted=True,
        double_terminal=True,
    )
    assert "force_complete_used" in evaluate_reclaim_observables(
        services_restarted=True,
        force_complete_used=True,
    )
    assert "leases_scrubbed_early" in evaluate_reclaim_observables(
        services_restarted=True,
        leases_scrubbed_early=True,
    )
    assert "services_not_restarted" in evaluate_reclaim_observables(
        services_restarted=False,
    )


def test_compose_kill_and_start_commands_target_api_and_worker() -> None:
    kill_cmd = compose_kill_command(
        compose_files=["compose.stack.yml", "compose.stack.minio.yml"],
        env_file=".env.stack.local",
        project="ce-drill",
    )
    assert kill_cmd[:2] == ["docker", "compose"]
    assert "kill" in kill_cmd
    assert kill_cmd[-2:] == ["api", "worker"]
    assert "--env-file" in kill_cmd
    assert "-p" in kill_cmd

    start_cmd = compose_start_command(
        compose_files=["compose.stack.yml"],
        services=("api", "worker"),
    )
    assert "up" in start_cmd
    assert "-d" in start_cmd
    assert start_cmd[-2:] == ["api", "worker"]


def test_run_api_worker_kill_waits_then_checks_hooks() -> None:
    slept: list[float] = []
    ran: list[list[str]] = []

    def runner(argv: list[str] | tuple[str, ...]) -> int:
        ran.append(list(argv))
        return 0

    rc = run_api_worker_kill(
        compose_files=["compose.stack.yml"],
        lease_seconds=3,
        pad_seconds=1,
        sleep_fn=slept.append,
        command_runner=runner,
        observables={"reclaim_progressed": True},
    )
    assert rc == 0
    assert slept == [4.0]
    assert any("kill" in cmd for cmd in ran)
    assert any("up" in cmd for cmd in ran)


def test_run_restore_then_reclaim_rejects_force_complete_flags() -> None:
    slept: list[float] = []
    rc = run_restore_then_reclaim(
        lease_seconds=2,
        pad_seconds=0,
        sleep_fn=slept.append,
        extra_flags=["--force-complete"],
    )
    assert rc == 1
    assert slept == []


def test_run_missing_object_fail_safe_exit_codes() -> None:
    deleted: list[str] = []

    assert (
        run_missing_object(
            object_key="obj_missing",
            delete_object=deleted.append,
            content_status=404,
        )
        == 0
    )
    assert deleted == ["obj_missing"]

    assert (
        run_missing_object(
            object_key="obj_missing",
            delete_object=lambda _k: None,
            content_status=200,
            content_body="",
        )
        == 1
    )


def test_cli_dry_run_and_mode_errors() -> None:
    assert main(["--mode", "api_worker_kill", "--dry-run", "--lease-seconds", "5"]) == 0
    assert main(["--mode", "restore_then_reclaim", "--dry-run"]) == 0
    assert (
        main(
            [
                "--mode",
                "missing_object",
                "--dry-run",
                "--object-key",
                "k1",
            ]
        )
        == 0
    )
    assert main(["--mode", "ha_failover", "--dry-run"]) == 1


def test_module_docstring_credits_p10_03_and_lease_authority() -> None:
    from scripts import stack_incident_reclaim_drill as mod

    doc = mod.__doc__ or ""
    assert "P10-03" in doc
    assert "test_postgres_turn_leases.py" in doc
    assert "compose-stack-runbook.md" in doc
    assert "do not re-own" in doc.lower() or "does **not** re-own" in doc
    assert "HA" in doc or "multi-replica" in doc
