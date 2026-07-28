#!/usr/bin/env python3
"""P12-04 schema-compatible image rollback drill (Compose-matrix).

Records two local image digests at the same Alembic head, documents swapping
api/worker (and optionally frontend) to the prior digest, then ready + smoke.

Production rollback reverts images only while schema-compatible. Destructive
rollback uses restore, not an improvised down migration / ``alembic downgrade``.

Authority (credit):
- docs/architecture/deployment-topology.md — rollback reverts images only while
  declared schema/contract ranges include the current versions; destructive
  rollback uses restore, not an improvised down migration.
- docs/architecture/security-operations-and-quality.md — roll back application
  images only while schema remains backward compatible; do not improvise down
  migrations for redaction/deletion data.
- docs/_scratch/p1-01-foundation-evidence.md — do not run ``downgrade base``
  against populated production state; restore or ship a reviewed forward fix.

P12-06/08 own immutable release digests. This drill records Compose-matrix
local digests only (AE5), not staging/prod registry acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


IMAGE_ROLLBACK_RECORD_SCHEMA_VERSION = 1
DEFAULT_ROLLBACK_SERVICES = ("api", "worker")
OPTIONAL_LOCKSTEP_SERVICE = "frontend"

REFUSE_DOWNGRADE_MESSAGE = """\
REFUSE: Improvised down migration / alembic downgrade is not a production rollback path.

Rollback reverts application images only while their declared schema/contract
ranges include the current versions (same Alembic head). Destructive rollback
uses restore (P12-04 F1/F2 consistency capture → isolated restore), not
`alembic downgrade` or an improvised down migration.

Authority:
- docs/architecture/deployment-topology.md
- docs/architecture/security-operations-and-quality.md
- docs/_scratch/p1-01-foundation-evidence.md

Go/no-go: if a prior image cannot ready against the current head, stop and use
the restore path — do not force a schema downgrade.
""".strip()


def refuse_improvised_downgrade_message() -> str:
    """Stable refuse text for scripts, runbook, and unit assertions."""
    return REFUSE_DOWNGRADE_MESSAGE


def parse_image_inspect_digest(payload: str | list[Any] | dict[str, Any]) -> str:
    """Extract a digest from ``docker image inspect`` JSON (no Docker required).

    Prefers RepoDigests[0] (registry@sha256:...), falls back to Id (sha256:...).
    """
    if isinstance(payload, str):
        raw: Any = json.loads(payload)
    else:
        raw = payload
    if isinstance(raw, list):
        if not raw:
            raise ValueError("empty_inspect")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise ValueError("inspect_must_be_object")
    digests = raw.get("RepoDigests") or []
    if isinstance(digests, list):
        for item in digests:
            text = str(item or "").strip()
            if "@sha256:" in text:
                return text.split("@", 1)[1]
            if text.startswith("sha256:"):
                return text
    image_id = str(raw.get("Id") or "").strip()
    if image_id.startswith("sha256:"):
        return image_id
    raise ValueError("digest_missing")


def assert_same_alembic_head(current_head: str, prior_head: str) -> list[str]:
    """Hard-fail reasons when current/prior digests are not at one Alembic head."""
    current = str(current_head or "").strip()
    prior = str(prior_head or "").strip()
    if not current or not prior:
        return ["alembic_head_missing"]
    if current != prior:
        return [f"alembic_head_mismatch:{current}!={prior}"]
    return []


def build_image_digest_record(
    *,
    alembic_head: str,
    current_digests: dict[str, str],
    prior_digests: dict[str, str],
    services: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Record current + prior digests at one Alembic head for AE5 evidence.

    Shape is Compose-matrix local digests only — not P12-06/08 release manifests.
    """
    head = str(alembic_head or "").strip()
    if not head:
        raise ValueError("alembic_head_required")
    svc_list = list(services) if services is not None else list(DEFAULT_ROLLBACK_SERVICES)
    if not svc_list:
        raise ValueError("services_required")

    current = {str(k): str(v).strip() for k, v in sorted(current_digests.items())}
    prior = {str(k): str(v).strip() for k, v in sorted(prior_digests.items())}
    for name in svc_list:
        if name not in current or not current[name]:
            raise ValueError(f"current_digest_missing:{name}")
        if name not in prior or not prior[name]:
            raise ValueError(f"prior_digest_missing:{name}")

    return {
        "schemaVersion": IMAGE_ROLLBACK_RECORD_SCHEMA_VERSION,
        "alembicHead": head,
        "services": list(svc_list),
        "currentDigests": {name: current[name] for name in svc_list},
        "priorDigests": {name: prior[name] for name in svc_list},
        "schemaCompatible": True,
        "notes": (
            "Local Compose-matrix digests at the same Alembic head. "
            "P12-06/08 own immutable release digests."
        ),
    }


def incompatible_image_go_no_go(*, prior_ready: bool) -> dict[str, Any]:
    """Go/no-go when evaluating a prior image against the current head.

    Compatible prior image → swap path. Incompatible → restore (F1/F2), never
    ``alembic downgrade`` / improvised down migration.
    """
    if prior_ready:
        return {
            "decision": "go",
            "action": "swap_prior_images",
            "path": "image_rollback",
            "refuseDowngrade": True,
        }
    return {
        "decision": "no-go",
        "action": "restore",
        "path": "restore",
        "refuseDowngrade": True,
        "refuse": "alembic_downgrade",
        "message": refuse_improvised_downgrade_message(),
    }


def document_swap_steps(
    *,
    prior_digests: dict[str, str],
    include_frontend: bool = False,
    compose_files: Sequence[str] | None = None,
    project: str | None = None,
) -> list[str]:
    """Operator-facing steps to pin api/worker/(frontend) to prior digests."""
    files = list(
        compose_files
        if compose_files is not None
        else ("compose.stack.yml", "compose.stack.minio.yml")
    )
    file_args = " ".join(f"-f {name}" for name in files)
    project_arg = f" -p {project}" if project else ""
    services = list(DEFAULT_ROLLBACK_SERVICES)
    if include_frontend:
        services.append(OPTIONAL_LOCKSTEP_SERVICE)

    steps = [
        "Confirm current and prior digests share the same Alembic head "
        "(schema-compatible image rollback only).",
        "Do not run alembic downgrade or an improvised down migration.",
    ]
    for service in services:
        digest = str(prior_digests.get(service) or "").strip()
        if not digest:
            steps.append(f"Missing prior digest for {service} — abort.")
            continue
        image_ref = digest if digest.startswith("sha256:") else f"sha256:{digest}"
        steps.append(
            f"Pin {service} to prior image {image_ref} "
            f"(docker compose{project_arg} {file_args} up -d --no-deps {service} "
            f"after setting the service image/digest)."
        )
    steps.append(
        "Restart api/worker"
        + ("/frontend" if include_frontend else "")
        + " so the prior digests are the running images."
    )
    return steps


def document_ready_smoke_steps(*, include_worker_smoke: bool = True) -> list[str]:
    """Document /health/ready + stack smoke checks after the image swap."""
    steps = [
        "Wait for api /health/ready to return ready against the current Alembic head.",
        "Run python -m scripts.stack_smoke_core against the ingress-wired stack.",
    ]
    if include_worker_smoke:
        steps.append(
            "If CE_INLINE_TURN_WORKERS=false, run python -m scripts.stack_smoke_worker."
        )
    steps.append(
        "Confirm Alembic head is unchanged (rollback drill must not mutate schema)."
    )
    steps.append(
        "If ready fails for the prior image, treat as incompatible: "
        "no-go → restore path (stack_backup_capture / stack_restore_recon), "
        "not alembic downgrade."
    )
    return steps


def _parse_digest_pairs(values: Sequence[str]) -> dict[str, str]:
    """Parse service=digest pairs from CLI."""
    out: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"digest_pair_invalid:{raw}")
        service, digest = raw.split("=", 1)
        service = service.strip()
        digest = digest.strip()
        if not service or not digest:
            raise ValueError(f"digest_pair_invalid:{raw}")
        out[service] = digest
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "P12-04 schema-compatible image rollback drill. "
            "Records digests at one Alembic head, documents api/worker "
            "(optional frontend) swap + ready/smoke, and refuses "
            "alembic downgrade / improvised down migration. "
            "Authority: docs/architecture/deployment-topology.md; "
            "docs/_scratch/p1-01-foundation-evidence.md."
        )
    )
    parser.add_argument(
        "--attempt-downgrade",
        action="store_true",
        help=(
            "Explicit refuse path: print that alembic downgrade / improvised "
            "down migration is not production rollback, then exit non-zero. "
            "Credit deployment-topology.md and P1-01."
        ),
    )
    parser.add_argument(
        "--alembic-head",
        default="",
        help="Shared Alembic head for current and prior digests.",
    )
    parser.add_argument(
        "--current-digest",
        action="append",
        default=[],
        metavar="SERVICE=DIGEST",
        help="Current image digest for a service (repeatable).",
    )
    parser.add_argument(
        "--prior-digest",
        action="append",
        default=[],
        metavar="SERVICE=DIGEST",
        help="Prior schema-compatible image digest for a service (repeatable).",
    )
    parser.add_argument(
        "--include-frontend",
        action="store_true",
        help="Include frontend in lockstep digest record and swap documentation.",
    )
    parser.add_argument(
        "--record-out",
        type=Path,
        default=None,
        help="Write digest record JSON to this path.",
    )
    parser.add_argument(
        "--prior-ready",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Evaluate go/no-go for prior image readiness against current head.",
    )
    parser.add_argument(
        "--print-steps",
        action="store_true",
        help="Print swap + ready/smoke operator steps.",
    )
    parser.add_argument(
        "--inspect-json",
        type=Path,
        default=None,
        help="Parse a docker image inspect JSON file and print the digest (no Docker).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.attempt_downgrade:
        print(refuse_improvised_downgrade_message(), file=sys.stderr)
        return 1

    if args.inspect_json is not None:
        try:
            payload = args.inspect_json.read_text(encoding="utf-8")
            digest = parse_image_inspect_digest(payload)
        except Exception as exc:
            print(f"inspect_failed:{exc}", file=sys.stderr)
            return 1
        print(digest)
        return 0

    if args.prior_ready is not None:
        decision = incompatible_image_go_no_go(prior_ready=args.prior_ready)
        print(json.dumps(decision, indent=2, sort_keys=True))
        if decision["decision"] == "no-go":
            print(refuse_improvised_downgrade_message(), file=sys.stderr)
            return 1
        return 0

    services = list(DEFAULT_ROLLBACK_SERVICES)
    if args.include_frontend:
        services.append(OPTIONAL_LOCKSTEP_SERVICE)

    want_record = bool(args.current_digest or args.prior_digest or args.record_out)
    if want_record:
        try:
            current = _parse_digest_pairs(args.current_digest)
            prior = _parse_digest_pairs(args.prior_digest)
            record = build_image_digest_record(
                alembic_head=args.alembic_head,
                current_digests=current,
                prior_digests=prior,
                services=services,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
        if args.record_out is not None:
            args.record_out.parent.mkdir(parents=True, exist_ok=True)
            args.record_out.write_text(payload, encoding="utf-8")
        print(payload, end="")

    if args.print_steps or not want_record:
        prior = {}
        if args.prior_digest:
            try:
                prior = _parse_digest_pairs(args.prior_digest)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        print("## Swap steps")
        for step in document_swap_steps(
            prior_digests=prior,
            include_frontend=args.include_frontend,
        ):
            print(f"- {step}")
        print("## Ready + smoke steps")
        for step in document_ready_smoke_steps():
            print(f"- {step}")
        print("## Refuse downgrade")
        print(refuse_improvised_downgrade_message())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
