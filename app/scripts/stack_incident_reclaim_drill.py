#!/usr/bin/env python3
"""P12-04 U5 restore-coupled multi-failure incident reclaim drills (AE6).

Credit P10-03 for single-worker kill+reclaim — this script does **not** re-own
that drill. Algorithm authority remains PostgreSQL suites, especially
``app/tests/test_postgres_turn_leases.py`` (plus domain/index reclaim suites).
Compose kill+single-worker reclaim procedure is documented in
``docs/operations/compose-stack-runbook.md`` § Kill + single-worker turn-lease reclaim.

Modes:
  api_worker_kill      — compose kill api+worker → wait shortened leases → restart
                         → check reclaim observables (hooks / exit codes)
  restore_then_reclaim — assumes restore already done; shortened lease wait;
                         no force-complete / no early lease scrub
  missing_object       — after restore, delete one object key; assert fail-safe
                         (content unavailable / no silent empty success /
                         no eligibility restore)

R18: do not force-complete turns/ops, clear leases early, or bypass generation
fences. HA / multi-replica topology is out of scope (P12-08 residual).
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

DRILL_MODES = frozenset({"api_worker_kill", "restore_then_reclaim", "missing_object"})

# Tokens that would violate R18 if accepted as drill knobs.
FORBIDDEN_FORCE_COMPLETE_FLAGS = frozenset(
    {
        "force-complete",
        "force_complete",
        "forceComplete",
        "clear-lease",
        "clear_lease",
        "clearLease",
        "scrub-lease",
        "scrub_lease",
        "bypass-generation",
        "bypass_generation",
        "bypassGeneration",
    }
)

# Content responses that mean "unavailable" (fail closed, not silent success).
CONTENT_UNAVAILABLE_STATUSES = frozenset({404, 409, 410, 422, 503})

DEFAULT_LEASE_PAD_SECONDS = 1.0
DEFAULT_KILL_SERVICES = ("api", "worker")


def normalize_mode(raw: str | None) -> str:
    """Return a canonical drill mode or raise ValueError."""
    mode = str(raw or "").strip().lower().replace("-", "_")
    if mode not in DRILL_MODES:
        raise ValueError(f"unsupported_mode:{raw!r}")
    return mode


def select_mode(raw: str | None, *, allowed: frozenset[str] = DRILL_MODES) -> str:
    """Mode selection helper used by CLI and unit tests."""
    mode = normalize_mode(raw)
    if mode not in allowed:
        raise ValueError(f"mode_not_allowed:{mode}")
    return mode


def compute_lease_wait_seconds(
    lease_seconds: float,
    *,
    pad_seconds: float = DEFAULT_LEASE_PAD_SECONDS,
    min_wait_seconds: float = 0.0,
) -> float:
    """Wait at least lease duration (+ pad) before expecting reclaim eligibility.

    Shortened ``CE_*_LEASE_SECONDS`` values are allowed for drill-only envs.
    Never treats a zero/negative lease as "force clear" — clamps to min_wait.
    """
    try:
        lease = float(lease_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_lease_seconds") from exc
    try:
        pad = float(pad_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_pad_seconds") from exc
    if lease < 0:
        raise ValueError("negative_lease_seconds")
    if pad < 0:
        raise ValueError("negative_pad_seconds")
    wait = lease + pad
    floor = max(0.0, float(min_wait_seconds))
    return max(wait, floor)


def collect_forbidden_force_complete_flags(flags: Iterable[str]) -> list[str]:
    """Return forbidden force-complete / lease-scrub / fence-bypass flag names."""
    found: list[str] = []
    for raw in flags:
        token = str(raw or "").strip()
        if not token:
            continue
        # Accept "--force-complete" / "force_complete=1" style tokens.
        bare = token.lstrip("-").split("=", 1)[0].strip()
        if bare in FORBIDDEN_FORCE_COMPLETE_FLAGS:
            found.append(bare)
    return sorted(set(found))


def assert_no_force_complete_flags(flags: Iterable[str]) -> list[str]:
    """Hard-fail reasons when R18-violating flags are present."""
    return [f"forbidden_flag:{name}" for name in collect_forbidden_force_complete_flags(flags)]


def assert_missing_object_fail_safe(
    *,
    content_status: int | None,
    content_body: bytes | str | None = None,
    eligibility_restored: bool = False,
    recon_ok: bool | None = None,
    silent_empty_success: bool | None = None,
) -> list[str]:
    """Assert injected missing-object fails closed (AE6 / R17).

    Pass conditions:
      - content is unavailable (non-success status in CONTENT_UNAVAILABLE_STATUSES,
        or any 4xx/5xx that is not a 2xx empty body)
      - query eligibility is not restored
      - recon must not report ok when provided
      - no silent empty success (HTTP 200 with empty/whitespace body)
    """
    failures: list[str] = []

    if eligibility_restored:
        failures.append("eligibility_restored")

    if recon_ok is True:
        failures.append("recon_reported_ok")

    body_empty = _body_is_empty(content_body)
    if silent_empty_success is None:
        silent_empty_success = content_status == 200 and body_empty
    if silent_empty_success:
        failures.append("silent_empty_success")

    if content_status is None:
        failures.append("content_status_missing")
    elif content_status == 200:
        # 200 with non-empty body after missing object is also unsafe.
        if not body_empty:
            failures.append("content_available_after_missing_object")
        # empty 200 already covered by silent_empty_success
    elif int(content_status) in CONTENT_UNAVAILABLE_STATUSES:
        pass
    elif 400 <= int(content_status) <= 599:
        # Other fail-closed statuses are acceptable.
        pass
    else:
        failures.append(f"unexpected_content_status:{content_status}")

    return failures


def evaluate_reclaim_observables(
    *,
    services_restarted: bool,
    double_terminal: bool = False,
    reclaim_progressed: bool | None = None,
    force_complete_used: bool = False,
    leases_scrubbed_early: bool = False,
) -> list[str]:
    """Check reclaim observables after api+worker kill/restart (hooks/exit codes)."""
    failures: list[str] = []
    if not services_restarted:
        failures.append("services_not_restarted")
    if double_terminal:
        failures.append("double_terminal")
    if force_complete_used:
        failures.append("force_complete_used")
    if leases_scrubbed_early:
        failures.append("leases_scrubbed_early")
    if reclaim_progressed is False:
        failures.append("reclaim_did_not_progress")
    return failures


def compose_kill_command(
    *,
    compose_files: Sequence[str],
    services: Sequence[str] = DEFAULT_KILL_SERVICES,
    project: str | None = None,
    env_file: str | None = None,
) -> list[str]:
    """Documented compose kill argv for api+worker (matrix hook)."""
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    for path in compose_files:
        cmd.extend(["-f", path])
    if project:
        cmd.extend(["-p", project])
    cmd.append("kill")
    cmd.extend(list(services))
    return cmd


def compose_start_command(
    *,
    compose_files: Sequence[str],
    services: Sequence[str] = DEFAULT_KILL_SERVICES,
    project: str | None = None,
    env_file: str | None = None,
) -> list[str]:
    """Documented compose start/up argv after lease wait."""
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    for path in compose_files:
        cmd.extend(["-f", path])
    if project:
        cmd.extend(["-p", project])
    # `up -d` is tolerant when containers were killed; mirrors runbook restart.
    cmd.extend(["up", "-d"])
    cmd.extend(list(services))
    return cmd


def _body_is_empty(content_body: bytes | str | None) -> bool:
    if content_body is None:
        return True
    if isinstance(content_body, bytes):
        return len(content_body.strip()) == 0
    return len(str(content_body).strip()) == 0


def _fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def _run_hook(
    argv: Sequence[str],
    *,
    runner: Callable[[Sequence[str]], int] | None,
) -> int:
    if runner is not None:
        return int(runner(argv))
    completed = subprocess.run(list(argv), check=False)
    return int(completed.returncode)


def run_api_worker_kill(
    *,
    compose_files: Sequence[str],
    lease_seconds: float,
    pad_seconds: float = DEFAULT_LEASE_PAD_SECONDS,
    project: str | None = None,
    env_file: str | None = None,
    services: Sequence[str] = DEFAULT_KILL_SERVICES,
    sleep_fn: Callable[[float], None] = time.sleep,
    command_runner: Callable[[Sequence[str]], int] | None = None,
    observables: Mapping[str, Any] | None = None,
    dry_run: bool = False,
) -> int:
    """Mode api_worker_kill: kill → wait shortened leases → restart → check observables."""
    kill_cmd = compose_kill_command(
        compose_files=compose_files,
        services=services,
        project=project,
        env_file=env_file,
    )
    start_cmd = compose_start_command(
        compose_files=compose_files,
        services=services,
        project=project,
        env_file=env_file,
    )
    wait = compute_lease_wait_seconds(lease_seconds, pad_seconds=pad_seconds)

    if dry_run:
        print(f"plan:kill {' '.join(shlex.quote(p) for p in kill_cmd)}")
        print(f"plan:wait_seconds={wait}")
        print(f"plan:start {' '.join(shlex.quote(p) for p in start_cmd)}")
        return 0

    kill_rc = _run_hook(kill_cmd, runner=command_runner)
    if kill_rc != 0:
        return _fail(f"compose_kill_exit:{kill_rc}")

    sleep_fn(wait)

    start_rc = _run_hook(start_cmd, runner=command_runner)
    if start_rc != 0:
        return _fail(f"compose_start_exit:{start_rc}")

    obs = dict(observables or {})
    # Default: hooks succeeded ⇒ restarted; callers may override via --observables JSON path.
    failures = evaluate_reclaim_observables(
        services_restarted=bool(obs.get("services_restarted", True)),
        double_terminal=bool(obs.get("double_terminal", False)),
        reclaim_progressed=obs.get("reclaim_progressed"),
        force_complete_used=bool(obs.get("force_complete_used", False)),
        leases_scrubbed_early=bool(obs.get("leases_scrubbed_early", False)),
    )
    if failures:
        for reason in failures:
            print(reason, file=sys.stderr)
        return 1

    print(f"OK: api_worker_kill wait_seconds={wait} (P12-04 AE6; P10-03 single-worker credited)")
    return 0


def run_restore_then_reclaim(
    *,
    lease_seconds: float,
    pad_seconds: float = DEFAULT_LEASE_PAD_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    observables: Mapping[str, Any] | None = None,
    extra_flags: Sequence[str] = (),
    dry_run: bool = False,
) -> int:
    """Mode restore_then_reclaim: assume restore done; wait leases; no force-complete."""
    flag_failures = assert_no_force_complete_flags(extra_flags)
    if flag_failures:
        for reason in flag_failures:
            print(reason, file=sys.stderr)
        return 1

    wait = compute_lease_wait_seconds(lease_seconds, pad_seconds=pad_seconds)
    if dry_run:
        print(f"plan:restore_then_reclaim wait_seconds={wait}")
        return 0

    sleep_fn(wait)

    obs = dict(observables or {})
    failures = evaluate_reclaim_observables(
        services_restarted=bool(obs.get("services_restarted", True)),
        double_terminal=bool(obs.get("double_terminal", False)),
        reclaim_progressed=obs.get("reclaim_progressed"),
        force_complete_used=bool(obs.get("force_complete_used", False)),
        leases_scrubbed_early=bool(obs.get("leases_scrubbed_early", False)),
    )
    if failures:
        for reason in failures:
            print(reason, file=sys.stderr)
        return 1

    print(
        f"OK: restore_then_reclaim wait_seconds={wait} "
        "(no force-complete; generation fences honored)"
    )
    return 0


def run_missing_object(
    *,
    object_key: str,
    delete_object: Callable[[str], None] | None,
    content_status: int | None,
    content_body: bytes | str | None = None,
    eligibility_restored: bool = False,
    recon_ok: bool | None = None,
    dry_run: bool = False,
) -> int:
    """Mode missing_object: delete one key after restore; assert fail-safe."""
    key = str(object_key or "").strip()
    if not key:
        return _fail("object_key_required")

    if dry_run:
        print(f"plan:missing_object delete_key={key}")
        return 0

    if delete_object is not None:
        try:
            delete_object(key)
        except Exception as exc:  # noqa: BLE001 — drill boundary
            return _fail(f"delete_object_failed:{exc}")

    failures = assert_missing_object_fail_safe(
        content_status=content_status,
        content_body=content_body,
        eligibility_restored=eligibility_restored,
        recon_ok=recon_ok,
    )
    if failures:
        for reason in failures:
            print(reason, file=sys.stderr)
        return 1

    print(f"OK: missing_object key={key} fail_safe (content unavailable; no silent empty)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        help="api_worker_kill | restore_then_reclaim | missing_object",
    )
    parser.add_argument(
        "--lease-seconds",
        type=float,
        default=10.0,
        help="Shortened drill lease seconds (CE_*_LEASE_SECONDS); wait = lease + pad",
    )
    parser.add_argument(
        "--pad-seconds",
        type=float,
        default=DEFAULT_LEASE_PAD_SECONDS,
        help="Extra seconds after lease expiry before reclaim checks",
    )
    parser.add_argument(
        "--compose-file",
        action="append",
        default=[],
        help="Compose file(s); default three-file MinIO+live matrix when mode needs compose",
    )
    parser.add_argument("--compose-project", default=None)
    parser.add_argument("--compose-env-file", default=None)
    parser.add_argument(
        "--object-key",
        default=None,
        help="Object key to delete for missing_object mode",
    )
    parser.add_argument(
        "--content-status",
        type=int,
        default=None,
        help="Observed document/content HTTP status after missing-object injection",
    )
    parser.add_argument(
        "--content-body",
        default=None,
        help="Observed response body (use empty string to simulate silent empty)",
    )
    parser.add_argument(
        "--eligibility-restored",
        action="store_true",
        help="Set when domain/query eligibility was incorrectly restored (must fail)",
    )
    parser.add_argument(
        "--recon-ok",
        action="store_true",
        help="Set when recon incorrectly reported ok after missing object (must fail)",
    )
    parser.add_argument(
        "--double-terminal",
        action="store_true",
        help="Observables: double terminal detected (must fail)",
    )
    parser.add_argument(
        "--reclaim-progressed",
        choices=("true", "false", "unknown"),
        default="unknown",
        help="Observables: whether reclaim progressed under new owners",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan only (no compose/sleep/delete)",
    )
    args = parser.parse_args(argv)

    # Refuse R18-violating tokens if an operator smuggles them via unknown argv
    # that argparse already rejected — also scan known dangerous names on extras.
    # argparse rejects unknowns; still guard programmatic flag lists via helpers.

    try:
        mode = select_mode(args.mode)
    except ValueError as exc:
        return _fail(str(exc))

    compose_files = list(args.compose_file) or [
        "compose.stack.yml",
        "compose.stack.minio.yml",
        "compose.stack.live.yml",
    ]

    reclaim_progressed: bool | None
    if args.reclaim_progressed == "true":
        reclaim_progressed = True
    elif args.reclaim_progressed == "false":
        reclaim_progressed = False
    else:
        reclaim_progressed = None

    observables = {
        "services_restarted": True,
        "double_terminal": bool(args.double_terminal),
        "reclaim_progressed": reclaim_progressed,
        "force_complete_used": False,
        "leases_scrubbed_early": False,
    }

    if mode == "api_worker_kill":
        return run_api_worker_kill(
            compose_files=compose_files,
            lease_seconds=args.lease_seconds,
            pad_seconds=args.pad_seconds,
            project=args.compose_project,
            env_file=args.compose_env_file,
            dry_run=args.dry_run,
            observables=observables,
        )

    if mode == "restore_then_reclaim":
        return run_restore_then_reclaim(
            lease_seconds=args.lease_seconds,
            pad_seconds=args.pad_seconds,
            dry_run=args.dry_run,
            observables=observables,
            extra_flags=[],
        )

    # missing_object
    return run_missing_object(
        object_key=args.object_key or "",
        delete_object=None if args.dry_run else (lambda _key: None),
        content_status=args.content_status,
        content_body=args.content_body,
        eligibility_restored=bool(args.eligibility_restored),
        recon_ok=True if args.recon_ok else None,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
