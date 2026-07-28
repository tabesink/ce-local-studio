#!/usr/bin/env python3
"""P12-04 U6 / R14 — post-restore LightRAG rebuild drill (AE4 rebuild half).

After restore, empty the live host bind ``CE_STACK_LIVE_RUNTIME_ROOT`` (not only
a named ``stack-domain-runtimes`` volume), prove three-file Compose matrix
config/boot, drive product domain start → index retry paths, and check mapped
Evidence/citations (or contracted absence).

Credit (topology/algorithm only — not this drill):
  ``app/tests/test_lightrag_real_runtime_integration.py`` (P5-04)

Overlays (AE4 rebuild DONE altitude):
  ``compose.stack.yml`` + ``compose.stack.minio.yml`` + ``compose.stack.live.yml``

Pure helpers are unit-testable without Docker/LightRAG. Live Compose steps use
HTTP/subprocess hooks; CLI defaults to ``--dry-run`` for CI.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.stack_drill_seed import DOMAIN_ID, SOURCE_ID, SOURCE_PUBLIC_REF

# Three-file MinIO+live matrix — pairwise overlays alone are non-DONE for AE4.
THREE_FILE_COMPOSE_MATRIX: tuple[str, ...] = (
    "compose.stack.yml",
    "compose.stack.minio.yml",
    "compose.stack.live.yml",
)

# P5-04 live pytest: topology/algorithm credit only (KTD10 / R14).
TOPOLOGY_CREDIT_PATH = "app/tests/test_lightrag_real_runtime_integration.py"

CANONICAL_API_PREFIX = "/api/v1"
RUNTIME_ROOT_ENV = "CE_STACK_LIVE_RUNTIME_ROOT"
ALLOWED_REBUILD_STORE_KINDS = frozenset({"s3", "minio"})

# Paths that must not appear in the backup archive listing (runtime is rebuildable).
FORBIDDEN_BACKUP_RUNTIME_MARKERS = (
    "domain-runtimes",
    "stack-domain-runtimes",
    "CE_STACK_LIVE_RUNTIME_ROOT",
    "lightrag-runtime",
)


@dataclass(frozen=True)
class RebuildCheckResult:
    name: str
    ok: bool
    detail: str = ""


def three_file_compose_files() -> list[str]:
    """Canonical AE4 rebuild compose file list (stack + minio + live)."""
    return list(THREE_FILE_COMPOSE_MATRIX)


def assert_three_file_compose_matrix(
    compose_files: Sequence[str] | None = None,
) -> list[str]:
    """Hard-fail reasons when the three-file MinIO+live matrix is incomplete."""
    files = [str(p).replace("\\", "/").rsplit("/", 1)[-1] for p in (compose_files or [])]
    if not files:
        files = three_file_compose_files()
    present = set(files)
    missing = [name for name in THREE_FILE_COMPOSE_MATRIX if name not in present]
    if missing:
        return [f"three_file_matrix_missing:{','.join(missing)}"]
    return []


def compose_config_command(
    *,
    compose_files: Sequence[str] | None = None,
    project: str | None = None,
    env_file: str | None = None,
) -> list[str]:
    """``docker compose … config`` argv for three-file matrix boot check."""
    files = list(compose_files) if compose_files is not None else three_file_compose_files()
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    if project:
        cmd.extend(["-p", project])
    for path in files:
        cmd.extend(["-f", path])
    cmd.append("config")
    return cmd


def compose_up_command(
    *,
    compose_files: Sequence[str] | None = None,
    project: str | None = None,
    env_file: str | None = None,
    build: bool = True,
) -> list[str]:
    """Disposable three-file matrix ``up -d`` argv (operator compose drill path)."""
    files = list(compose_files) if compose_files is not None else three_file_compose_files()
    cmd = ["docker", "compose"]
    if env_file:
        cmd.extend(["--env-file", env_file])
    if project:
        cmd.extend(["-p", project])
    for path in files:
        cmd.extend(["-f", path])
    cmd.extend(["up", "-d"])
    if build:
        cmd.append("--build")
    return cmd


def assert_live_runtime_bind(
    *,
    runtime_root: str | None,
    using_named_volume_only: bool = False,
) -> list[str]:
    """Refuse named-volume-only empty; require ``CE_STACK_LIVE_RUNTIME_ROOT`` bind."""
    failures: list[str] = []
    if using_named_volume_only:
        failures.append("named_volume_only_refused")
    root = str(runtime_root or "").strip()
    if not root:
        failures.append(f"{RUNTIME_ROOT_ENV}_missing")
        return failures
    path = Path(root)
    # Compose matrix binds are host-absolute. Accept POSIX roots (`/…`) even when
    # pathlib on Windows does not treat them as absolute (drive-letter rule).
    if not path.is_absolute() and not root.startswith("/"):
        failures.append("runtime_root_not_absolute")
    return failures


def assert_runtime_root_empty(runtime_root: str | Path | None) -> list[str]:
    """Empty-runtime precondition before rebuild (host bind, not backup restore)."""
    failures = assert_live_runtime_bind(runtime_root=str(runtime_root) if runtime_root else None)
    if failures:
        return failures
    root = Path(str(runtime_root))
    if not root.exists():
        return []  # absent bind path is empty (mkdir before boot)
    if not root.is_dir():
        return ["runtime_root_not_directory"]
    try:
        children = list(root.iterdir())
    except OSError:
        return ["runtime_root_unreadable"]
    if children:
        return ["runtime_root_not_empty"]
    return []


def clear_runtime_root(
    runtime_root: str | Path,
    *,
    dry_run: bool = True,
) -> list[str]:
    """Empty ``CE_STACK_LIVE_RUNTIME_ROOT`` contents; dry-run only plans the clear."""
    bind_failures = assert_live_runtime_bind(runtime_root=str(runtime_root))
    if bind_failures:
        return bind_failures
    root = Path(str(runtime_root))
    if dry_run:
        return []
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return []
    if not root.is_dir():
        return ["runtime_root_not_directory"]
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    return assert_runtime_root_empty(root)


def assert_rebuild_store_kind(
    store_kind: str,
    *,
    require_minio: bool = True,
) -> list[str]:
    """Refuse filesystem-only rebuild as AE4 DONE evidence."""
    kind = str(store_kind or "").strip().lower()
    if not require_minio:
        return []
    if kind not in ALLOWED_REBUILD_STORE_KINDS:
        return [f"filesystem_rebuild_refused:{kind or 'missing'}"]
    return []


def assert_backup_excludes_runtime_paths(
    archive_listing: Sequence[str] | None = None,
    *,
    manifest: Mapping[str, Any] | None = None,
) -> list[str]:
    """Backup archive must not treat runtime disk as authority (edge / R14)."""
    failures: list[str] = []
    listing = [str(p) for p in (archive_listing or [])]
    for entry in listing:
        lowered = entry.replace("\\", "/").lower()
        for marker in FORBIDDEN_BACKUP_RUNTIME_MARKERS:
            if marker.lower() in lowered:
                failures.append(f"backup_contains_runtime:{entry}")
                break
    if manifest is not None:
        store_kind = str(manifest.get("storeKind") or manifest.get("store_kind") or "").strip().lower()
        store_failures = assert_rebuild_store_kind(store_kind, require_minio=True)
        failures.extend(store_failures)
        # Explicit runtime exclusion flag when present
        runtime_excluded = manifest.get("runtimeVolumeExcluded")
        if runtime_excluded is False:
            failures.append("runtime_volume_not_excluded")
    return failures


def domain_start_http_path(domain_id: str = DOMAIN_ID) -> str:
    """Product admin domain-start path (P5-04 / services.domains.start_domain)."""
    return f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}/start"


def index_retry_http_path(
    domain_id: str = DOMAIN_ID,
    source_id: str = SOURCE_ID,
) -> str:
    """Product admin index-retry path (SourceIndexWorker / indexing service)."""
    return (
        f"{CANONICAL_API_PREFIX}/admin/domains/{domain_id}"
        f"/sources/{source_id}/index/retry"
    )


def domain_start_curl_command(
    *,
    base_url: str,
    domain_id: str = DOMAIN_ID,
    csrf_header: str = "X-CSRF-Token",
) -> list[str]:
    """Subprocess hook argv for domain start (operator matrix; not executed in unit tests)."""
    url = f"{base_url.rstrip('/')}{domain_start_http_path(domain_id)}"
    return [
        "curl",
        "-sS",
        "-X",
        "POST",
        "-H",
        f"{csrf_header}: ${{CE_CSRF_TOKEN}}",
        "-H",
        "Content-Type: application/json",
        "-b",
        "ce_session=${CE_SESSION_COOKIE}",
        url,
    ]


def index_retry_curl_command(
    *,
    base_url: str,
    domain_id: str = DOMAIN_ID,
    source_id: str = SOURCE_ID,
    csrf_header: str = "X-CSRF-Token",
) -> list[str]:
    """Subprocess hook argv for index retry."""
    url = f"{base_url.rstrip('/')}{index_retry_http_path(domain_id, source_id)}"
    return [
        "curl",
        "-sS",
        "-X",
        "POST",
        "-H",
        f"{csrf_header}: ${{CE_CSRF_TOKEN}}",
        "-H",
        "Content-Type: application/json",
        "-b",
        "ce_session=${CE_SESSION_COOKIE}",
        url,
    ]


def check_mapped_evidence(
    *,
    evidence_items: Sequence[Mapping[str, Any]] | None = None,
    citations: Sequence[Mapping[str, Any]] | None = None,
    contracted_absence: bool = False,
    source_public_ref: str = SOURCE_PUBLIC_REF,
) -> RebuildCheckResult:
    """Mapped Evidence/citation check (or contracted absence after rebuild)."""
    items = list(evidence_items or [])
    cites = list(citations or [])

    if contracted_absence:
        if items or cites:
            return RebuildCheckResult(
                name="mapped_evidence",
                ok=False,
                detail="expected_contracted_absence",
            )
        return RebuildCheckResult(
            name="mapped_evidence",
            ok=True,
            detail="contracted_absence",
        )

    if not items:
        return RebuildCheckResult(
            name="mapped_evidence",
            ok=False,
            detail="evidence_missing",
        )

    # At least one item must map to an authorized source label/ref.
    mapped = False
    for item in items:
        ref = str(
            item.get("documentPublicRef")
            or item.get("document_public_ref")
            or item.get("sourcePublicRef")
            or item.get("source_public_ref")
            or item.get("publicRef")
            or item.get("public_ref")
            or ""
        )
        if source_public_ref and ref == source_public_ref:
            mapped = True
            break
        if item.get("mapped") is True or item.get("authorized") is True:
            mapped = True
            break
        # Safe projection with excerpt/label counts as mapped when present.
        if item.get("excerpt") or item.get("label") or item.get("safeLabel"):
            mapped = True
            break

    if not mapped:
        return RebuildCheckResult(
            name="mapped_evidence",
            ok=False,
            detail="unmapped_or_cross_domain",
        )

    # Citations optional when Evidence present; if supplied, require non-empty.
    if citations is not None and not cites:
        return RebuildCheckResult(
            name="mapped_evidence",
            ok=False,
            detail="citations_missing",
        )

    return RebuildCheckResult(
        name="mapped_evidence",
        ok=True,
        detail=f"evidence={len(items)};citations={len(cites)}",
    )


def evaluate_ae4_rebuild_done(
    *,
    three_file_matrix_ok: bool,
    runtime_emptied: bool,
    store_kind_ok: bool,
    mapped_evidence_ok: bool,
    compose_drill_path_exercised: bool,
    pytest_topology_credit: bool = True,
) -> dict[str, Any]:
    """AE4 rebuild DONE gate.

    Pytest-only topology credit without a Compose drill path is **non-DONE**.
    """
    done = bool(
        three_file_matrix_ok
        and runtime_emptied
        and store_kind_ok
        and mapped_evidence_ok
        and compose_drill_path_exercised
    )
    pytest_only_non_done = bool(pytest_topology_credit and not compose_drill_path_exercised)
    return {
        "done": done,
        "topologyCredit": TOPOLOGY_CREDIT_PATH,
        "pytestOnlyNonDone": pytest_only_non_done,
        "composeDrillRequired": True,
        "threeFileMatrixOk": three_file_matrix_ok,
        "runtimeEmptied": runtime_emptied,
        "storeKindOk": store_kind_ok,
        "mappedEvidenceOk": mapped_evidence_ok,
        "composeDrillPathExercised": compose_drill_path_exercised,
        "notes": (
            "P5-04 live pytest is topology/algorithm credit only. "
            "AE4 rebuild DONE requires the three-file Compose drill path."
        ),
    }


def document_rebuild_steps(
    *,
    domain_id: str = DOMAIN_ID,
    source_id: str = SOURCE_ID,
    base_url: str = "http://127.0.0.1:3000",
) -> list[str]:
    """Operator-facing AE4 rebuild half steps."""
    files = " ".join(f"-f {name}" for name in three_file_compose_files())
    return [
        f"Set host-absolute {RUNTIME_ROOT_ENV} (live bind; not only stack-domain-runtimes).",
        f"Empty/clear ${RUNTIME_ROOT_ENV} before rebuild (runtime disk is not backup authority).",
        f"Prove three-file config: docker compose {files} config >/dev/null",
        f"Boot disposable three-file matrix (MinIO + live): docker compose {files} up -d --build",
        "Confirm store kind is s3/minio — filesystem-only rebuild is non-evidence.",
        f"POST {domain_start_http_path(domain_id)} (product start_domain path).",
        f"POST {index_retry_http_path(domain_id, source_id)} (index retry / SourceIndexWorker).",
        "Assert mapped Evidence/citations (or contracted absence) against restored MinIO objects.",
        f"Credit topology only: {TOPOLOGY_CREDIT_PATH} — pytest alone is non-DONE for AE4.",
        f"Example start hook: {' '.join(shlex.quote(p) for p in domain_start_curl_command(base_url=base_url, domain_id=domain_id))}",
        f"Example index hook: {' '.join(shlex.quote(p) for p in index_retry_curl_command(base_url=base_url, domain_id=domain_id, source_id=source_id))}",
    ]


def _run_hook(
    argv: Sequence[str],
    *,
    runner: Callable[[Sequence[str]], int] | None,
) -> int:
    if runner is not None:
        return int(runner(argv))
    completed = subprocess.run(list(argv), check=False)
    return int(completed.returncode)


def run_lightrag_rebuild_drill(
    *,
    runtime_root: str | Path | None = None,
    compose_files: Sequence[str] | None = None,
    store_kind: str = "s3",
    project: str | None = None,
    env_file: str | None = None,
    base_url: str = "http://127.0.0.1:3000",
    domain_id: str = DOMAIN_ID,
    source_id: str = SOURCE_ID,
    dry_run: bool = True,
    clear_runtime: bool = True,
    using_named_volume_only: bool = False,
    evidence_items: Sequence[Mapping[str, Any]] | None = None,
    citations: Sequence[Mapping[str, Any]] | None = None,
    contracted_absence: bool = False,
    archive_listing: Sequence[str] | None = None,
    manifest: Mapping[str, Any] | None = None,
    compose_drill_path_exercised: bool | None = None,
    command_runner: Callable[[Sequence[str]], int] | None = None,
    start_hook: Callable[[], int] | None = None,
    index_hook: Callable[[], int] | None = None,
) -> int:
    """Drive AE4 rebuild half; defaults to dry-run (CI-safe, no Docker)."""
    files = list(compose_files) if compose_files is not None else three_file_compose_files()
    root = runtime_root if runtime_root is not None else os.environ.get(RUNTIME_ROOT_ENV)

    matrix_failures = assert_three_file_compose_matrix(files)
    if matrix_failures:
        for reason in matrix_failures:
            print(reason, file=sys.stderr)
        return 1

    bind_failures = assert_live_runtime_bind(
        runtime_root=str(root) if root else None,
        using_named_volume_only=using_named_volume_only,
    )
    if bind_failures:
        for reason in bind_failures:
            print(reason, file=sys.stderr)
        return 1

    store_failures = assert_rebuild_store_kind(store_kind, require_minio=True)
    if store_failures:
        for reason in store_failures:
            print(reason, file=sys.stderr)
        return 1

    backup_failures = assert_backup_excludes_runtime_paths(
        archive_listing,
        manifest=manifest,
    )
    if backup_failures:
        for reason in backup_failures:
            print(reason, file=sys.stderr)
        return 1

    config_cmd = compose_config_command(
        compose_files=files,
        project=project,
        env_file=env_file,
    )
    up_cmd = compose_up_command(
        compose_files=files,
        project=project,
        env_file=env_file,
    )
    start_cmd = domain_start_curl_command(base_url=base_url, domain_id=domain_id)
    index_cmd = index_retry_curl_command(
        base_url=base_url,
        domain_id=domain_id,
        source_id=source_id,
    )

    if dry_run:
        if clear_runtime:
            clear_rc_reasons = clear_runtime_root(str(root), dry_run=True)
            if clear_rc_reasons:
                for reason in clear_rc_reasons:
                    print(reason, file=sys.stderr)
                return 1
            print(f"plan:clear_runtime_root {root}")
        print(f"plan:compose_config {' '.join(shlex.quote(p) for p in config_cmd)}")
        print(f"plan:compose_up {' '.join(shlex.quote(p) for p in up_cmd)}")
        print(f"plan:domain_start {' '.join(shlex.quote(p) for p in start_cmd)}")
        print(f"plan:index_retry {' '.join(shlex.quote(p) for p in index_cmd)}")
        # Dry-run plans the compose drill path but does not exercise it.
        exercised = False if compose_drill_path_exercised is None else compose_drill_path_exercised
        status = evaluate_ae4_rebuild_done(
            three_file_matrix_ok=True,
            runtime_emptied=True,  # planned clear
            store_kind_ok=True,
            mapped_evidence_ok=True,  # hooks only in dry-run
            compose_drill_path_exercised=exercised,
            pytest_topology_credit=True,
        )
        print(json.dumps(status, indent=2, sort_keys=True))
        if status["pytestOnlyNonDone"]:
            print(
                "NOTE: dry-run / pytest-only credit is non-DONE for AE4 rebuild "
                "(compose drill path required).",
                file=sys.stderr,
            )
        print("OK: lightrag_rebuild_drill dry-run (P12-04 U6 / R14)")
        return 0

    if clear_runtime:
        clear_failures = clear_runtime_root(str(root), dry_run=False)
        if clear_failures:
            for reason in clear_failures:
                print(reason, file=sys.stderr)
            return 1
    empty_failures = assert_runtime_root_empty(root)
    if empty_failures:
        for reason in empty_failures:
            print(reason, file=sys.stderr)
        return 1

    config_rc = _run_hook(config_cmd, runner=command_runner)
    if config_rc != 0:
        print(f"compose_config_exit:{config_rc}", file=sys.stderr)
        return 1

    up_rc = _run_hook(up_cmd, runner=command_runner)
    if up_rc != 0:
        print(f"compose_up_exit:{up_rc}", file=sys.stderr)
        return 1

    if start_hook is not None:
        start_rc = int(start_hook())
    else:
        start_rc = _run_hook(start_cmd, runner=command_runner)
    if start_rc != 0:
        print(f"domain_start_exit:{start_rc}", file=sys.stderr)
        return 1

    if index_hook is not None:
        index_rc = int(index_hook())
    else:
        index_rc = _run_hook(index_cmd, runner=command_runner)
    if index_rc != 0:
        print(f"index_retry_exit:{index_rc}", file=sys.stderr)
        return 1

    evidence_result = check_mapped_evidence(
        evidence_items=evidence_items,
        citations=citations,
        contracted_absence=contracted_absence,
    )
    if not evidence_result.ok:
        print(f"{evidence_result.name}:{evidence_result.detail}", file=sys.stderr)
        return 1

    exercised = True if compose_drill_path_exercised is None else compose_drill_path_exercised
    status = evaluate_ae4_rebuild_done(
        three_file_matrix_ok=True,
        runtime_emptied=True,
        store_kind_ok=True,
        mapped_evidence_ok=evidence_result.ok,
        compose_drill_path_exercised=exercised,
        pytest_topology_credit=True,
    )
    print(json.dumps(status, indent=2, sort_keys=True))
    if not status["done"]:
        print("ae4_rebuild_not_done", file=sys.stderr)
        return 1
    print(
        f"OK: lightrag_rebuild_drill "
        f"(P12-04 AE4 rebuild; topology credit {TOPOLOGY_CREDIT_PATH})"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P12-04 post-restore LightRAG rebuild drill (AE4 rebuild half). "
            "Defaults to dry-run for CI; use --execute for Compose matrix. "
            f"Topology credit: {TOPOLOGY_CREDIT_PATH}."
        )
    )
    parser.add_argument(
        "--runtime-root",
        default="",
        help=f"Host-absolute {RUNTIME_ROOT_ENV} bind (defaults to env)",
    )
    parser.add_argument(
        "--compose-file",
        action="append",
        default=[],
        help="Compose file (-f); default three-file MinIO+live matrix",
    )
    parser.add_argument("--compose-project", default="", help="Compose -p project")
    parser.add_argument("--compose-env-file", default="", help="Compose --env-file")
    parser.add_argument(
        "--store-kind",
        default=os.environ.get("CE_OBJECT_STORE_KIND", "s3"),
        help="s3|minio required for AE4 rebuild evidence (filesystem refused)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:3000",
        help="Public origin for domain start / index retry hooks",
    )
    parser.add_argument("--domain-id", default=DOMAIN_ID)
    parser.add_argument("--source-id", default=SOURCE_ID)
    parser.add_argument(
        "--named-volume-only",
        action="store_true",
        help="Simulate named-volume-only runtime clear (must refuse)",
    )
    parser.add_argument(
        "--contracted-absence",
        action="store_true",
        help="Accept zero Evidence/citations as contracted absence",
    )
    parser.add_argument(
        "--evidence-json",
        type=Path,
        default=None,
        help="JSON list of Evidence items for mapped check (--execute)",
    )
    parser.add_argument(
        "--citations-json",
        type=Path,
        default=None,
        help="Optional JSON list of citations (--execute)",
    )
    parser.add_argument(
        "--archive-listing",
        type=Path,
        default=None,
        help="Optional text file of backup archive paths (one per line)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional consistency manifest JSON (storeKind / runtime exclusion)",
    )
    parser.add_argument(
        "--print-steps",
        action="store_true",
        help="Print operator rebuild steps and exit 0",
    )
    parser.add_argument(
        "--evaluate-done",
        action="store_true",
        help="Evaluate AE4 DONE flags from CLI booleans (unit/offline)",
    )
    parser.add_argument(
        "--three-file-ok",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--runtime-emptied",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--store-kind-ok",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--mapped-evidence-ok",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--compose-drill-exercised",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether the Compose drill path was actually exercised",
    )
    parser.add_argument(
        "--pytest-topology-credit",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Plan only (default true for CI). Use --no-dry-run / --execute.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Alias for --no-dry-run (run Compose/HTTP hooks)",
    )
    parser.add_argument(
        "--no-clear-runtime",
        action="store_true",
        help="Skip clearing runtime root (still assert empty when executing)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.print_steps:
        for step in document_rebuild_steps(
            domain_id=args.domain_id,
            source_id=args.source_id,
            base_url=args.base_url,
        ):
            print(f"- {step}")
        return 0

    if args.evaluate_done:
        status = evaluate_ae4_rebuild_done(
            three_file_matrix_ok=bool(args.three_file_ok),
            runtime_emptied=bool(args.runtime_emptied),
            store_kind_ok=bool(args.store_kind_ok),
            mapped_evidence_ok=bool(args.mapped_evidence_ok),
            compose_drill_path_exercised=bool(args.compose_drill_exercised),
            pytest_topology_credit=bool(args.pytest_topology_credit),
        )
        print(json.dumps(status, indent=2, sort_keys=True))
        if status["pytestOnlyNonDone"] or not status["done"]:
            print(
                "pytest-only topology credit is non-DONE without compose drill path",
                file=sys.stderr,
            )
            return 1
        return 0

    dry_run = False if args.execute else bool(args.dry_run)
    runtime_root = (args.runtime_root or os.environ.get(RUNTIME_ROOT_ENV) or "").strip()
    # Dry-run with missing runtime root: use a documented placeholder for planning.
    if dry_run and not runtime_root:
        runtime_root = "/tmp/ce-p12-04-live-runtime-empty"

    compose_files = list(args.compose_file) or three_file_compose_files()

    evidence_items = None
    if args.evidence_json is not None:
        evidence_items = json.loads(args.evidence_json.read_text(encoding="utf-8"))
    citations = None
    if args.citations_json is not None:
        citations = json.loads(args.citations_json.read_text(encoding="utf-8"))
    archive_listing = None
    if args.archive_listing is not None:
        archive_listing = [
            line.strip()
            for line in args.archive_listing.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    manifest = None
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    return run_lightrag_rebuild_drill(
        runtime_root=runtime_root or None,
        compose_files=compose_files,
        store_kind=str(args.store_kind),
        project=args.compose_project or None,
        env_file=args.compose_env_file or None,
        base_url=args.base_url,
        domain_id=args.domain_id,
        source_id=args.source_id,
        dry_run=dry_run,
        clear_runtime=not args.no_clear_runtime,
        using_named_volume_only=bool(args.named_volume_only),
        evidence_items=evidence_items,
        citations=citations,
        contracted_absence=bool(args.contracted_absence),
        archive_listing=archive_listing,
        manifest=manifest,
        compose_drill_path_exercised=bool(args.compose_drill_exercised) if args.evaluate_done else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
