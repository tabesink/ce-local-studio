#!/usr/bin/env python3
"""P12-06 immutable release artifact manifest generator.

Profiles:
- ``pr`` — regeneratable repo pins (locks, heads, contract versions, tags)
- ``release`` — fails closed without digests, non-placeholder controller,
  MinIO/mc digests, SBOM hashes, and allowlisted provenance

Does not invent product SBOM UI. Does not elevate packaging to
production-supported. P12-04 drill digests are not release authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# Reuse inspect digest parsing (credit — not release truth).
from scripts.stack_image_rollback_drill import parse_image_inspect_digest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "app"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "releases" / "release-manifest.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "releases" / "release-manifest.schema.json"

RELEASE_MANIFEST_SCHEMA_VERSION = "1"
GENERATOR_NAME = "generate_release_manifest.py"
DEFAULT_SYFT_VERSION = os.environ.get("CE_SYFT_VERSION", "v1.20.0")
PLATFORM = "linux/amd64"

PLACEHOLDER_CONTROLLER_IMAGES = frozenset(
    {"alpine:3.20", "alpine", "alpine:latest"}
)

RELEASE_GATES = {
    "CE_STACK_LIVE_IMAGE": "1",
    "CE_STACK_PARSERS_IMAGE": "1",
    "CE_STACK_OBJECT_STORE_IMAGE": "1",
    "CE_STACK_PREVIEW_IMAGE": "1",
}

PR_GATES_PRESENT = {
    "CE_STACK_LIVE_IMAGE": "0",
    "CE_STACK_PARSERS_IMAGE": "0",
    "CE_STACK_OBJECT_STORE_IMAGE": "0",
    "CE_STACK_PREVIEW_IMAGE": "0",
}

RENDERER_IDS = (
    "ce-preview-v1",
    "ce-preview-text-v1",
    "ce-preview-pdf-passthrough-v1",
)

PACKAGE_PIN_NAMES = (
    "docling",
    "reductoai",
    "openai",
    "python-docx",
    "boto3",
    "httpx",
)

PROVENANCE_ALLOWLIST = frozenset(
    {
        "gitSha",
        "dirty",
        "builtAt",
        "ciRunId",
        "syftVersion",
        "generator",
        "subjectDigests",
        "sbomSha256s",
        "lockSha256s",
        "imageGates",
    }
)

DENY_SUBSTRINGS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "CONFIG_ENCRYPTION_KEY",
    "CE_CSRF",
    "password=",
    "secret=",
    "api_key",
    "apiKey",
    "/var/run/",
    "C:\\Users\\",
)


class ManifestError(Exception):
    """Fail-closed generation or check failure with a stable diagnostic class."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        msg = code if not detail else f"{code}: {detail}"
        super().__init__(msg)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_alembic_head(readiness_path: Path | None = None) -> str:
    path = readiness_path or (APP_DIR / "context_engine" / "services" / "readiness.py")
    match = re.search(
        r'^SUPPORTED_ALEMBIC_HEAD\s*=\s*["\']([^"\']+)["\']',
        _read_text(path),
        re.MULTILINE,
    )
    if not match:
        raise ManifestError("alembic_head_missing", str(path))
    return match.group(1)


def read_api_version(contract_path: Path | None = None) -> str:
    path = contract_path or (APP_DIR / "context_engine" / "api" / "contract_app.py")
    match = re.search(
        r'^API_VERSION\s*=\s*["\']([^"\']+)["\']',
        _read_text(path),
        re.MULTILINE,
    )
    if not match:
        raise ManifestError("api_version_missing", str(path))
    return match.group(1)


def read_sse_schema_version(models_path: Path | None = None) -> str:
    path = models_path or (APP_DIR / "context_engine" / "models.py")
    match = re.search(
        r'^TURN_EVENT_SCHEMA_VERSION\s*=\s*["\']([^"\']+)["\']',
        _read_text(path),
        re.MULTILINE,
    )
    if not match:
        raise ManifestError("sse_schema_version_missing", str(path))
    return match.group(1)


def read_lightrag_versions(
    runtime_path: Path | None = None,
    vendor_path: Path | None = None,
) -> tuple[str, str]:
    runtime = runtime_path or (
        APP_DIR / "context_engine" / "services" / "lightrag_runtime.py"
    )
    vendor = vendor_path or (APP_DIR / "vendor" / "lightrag" / "_version.py")
    pinned = re.search(
        r'^PINNED_LIGHTRAG_VERSION\s*=\s*["\']([^"\']+)["\']',
        _read_text(runtime),
        re.MULTILINE,
    )
    vendored = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        _read_text(vendor),
        re.MULTILINE,
    )
    if not pinned or not vendored:
        raise ManifestError("lightrag_version_missing")
    return pinned.group(1), vendored.group(1)


def parse_compose_image_tag(compose_text: str, image_prefix: str) -> str:
    """Extract ``image: <prefix>...`` tag from compose YAML text."""
    pattern = rf"^\s*image:\s*({re.escape(image_prefix)}[^\s#]+)"
    match = re.search(pattern, compose_text, re.MULTILINE)
    if not match:
        raise ManifestError("compose_image_tag_missing", image_prefix)
    return match.group(1).strip().strip("\"'")


def read_upstream_tags(
    minio_compose: Path | None = None,
    stack_compose: Path | None = None,
) -> dict[str, str]:
    minio_path = minio_compose or (APP_DIR / "compose.stack.minio.yml")
    stack_path = stack_compose or (APP_DIR / "compose.stack.yml")
    minio_text = _read_text(minio_path)
    stack_text = _read_text(stack_path)
    return {
        "minio": parse_compose_image_tag(minio_text, "minio/minio:"),
        "mc": parse_compose_image_tag(minio_text, "minio/mc:"),
        "postgres": parse_compose_image_tag(stack_text, "postgres:"),
    }


def parse_uv_lock_versions(
    lock_path: Path | None = None,
    names: Sequence[str] = PACKAGE_PIN_NAMES,
) -> dict[str, str]:
    path = lock_path or (APP_DIR / "uv.lock")
    text = _read_text(path)
    versions: dict[str, str] = {}
    for name in names:
        # uv.lock package stanzas: [[package]]\nname = "docling"\nversion = "..."
        pattern = (
            rf'\[\[package\]\]\s*\nname\s*=\s*"{re.escape(name)}"\s*\n'
            rf'version\s*=\s*"([^"]+)"'
        )
        match = re.search(pattern, text)
        if match:
            versions[name] = match.group(1)
    return versions


def git_source(repo_root: Path | None = None) -> tuple[str, bool]:
    root = repo_root or REPO_ROOT
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ManifestError("git_unavailable", str(exc)) from exc
    return sha, bool(dirty_out.strip())


def normalize_digest(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("sha256:") and len(text) == 71:
        return text
    if re.fullmatch(r"[a-f0-9]{64}", text):
        return f"sha256:{text}"
    raise ManifestError("digest_invalid", text)


def is_placeholder_controller(image_ref: str | None, digest: str | None = None) -> bool:
    ref = (image_ref or "").strip().lower()
    if ref in PLACEHOLDER_CONTROLLER_IMAGES or ref.startswith("alpine:"):
        return True
    # Digest alone cannot prove Alpine; imageRef is authoritative for stub detect.
    _ = digest
    return False


def build_role_map(
    *,
    web_digest: str,
    controller_digest: str,
    web_ref: str = "",
    controller_ref: str = "",
) -> dict[str, dict[str, Any]]:
    web = normalize_digest(web_digest)
    controller = normalize_digest(controller_digest)
    if is_placeholder_controller(controller_ref, controller):
        raise ManifestError("lightrag_stub_controller", controller_ref or controller)
    return {
        "web": {"digest": web, "imageRef": web_ref},
        "api": {"digest": controller, "imageRef": controller_ref},
        "worker": {
            "digest": controller,
            "imageRef": controller_ref,
            "sameAs": "api",
        },
        "lightragRuntime": {
            "digest": controller,
            "imageRef": controller_ref,
            "sameAs": "api",
        },
    }


def distinct_digests(roles: Mapping[str, Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for role in ("web", "api", "worker", "lightragRuntime"):
        pin = roles.get(role) or {}
        digest = str(pin.get("digest") or "")
        if digest and digest not in seen:
            seen.append(digest)
    return seen


def build_provenance(
    *,
    git_sha: str,
    dirty: bool,
    locks: Mapping[str, str],
    image_gates: Mapping[str, str],
    subject_digests: Sequence[str],
    sbom_sha256s: Sequence[str],
    syft_version: str | None,
    built_at: str | None = None,
    ci_run_id: str | None = None,
) -> dict[str, Any]:
    prov = {
        "gitSha": git_sha,
        "dirty": dirty,
        "builtAt": built_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ciRunId": ci_run_id,
        "syftVersion": syft_version,
        "generator": GENERATOR_NAME,
        "subjectDigests": list(subject_digests),
        "sbomSha256s": list(sbom_sha256s),
        "lockSha256s": dict(locks),
        "imageGates": dict(image_gates),
    }
    unknown = set(prov) - PROVENANCE_ALLOWLIST
    if unknown:
        raise ManifestError("provenance_allowlist_violation", ",".join(sorted(unknown)))
    return prov


def scan_deny_patterns(text: str) -> list[str]:
    hits: list[str] = []
    lowered = text.lower()
    for pattern in DENY_SUBSTRINGS:
        if pattern.lower() in lowered:
            hits.append(pattern)
    return hits


def validate_manifest_shape(
    manifest: Mapping[str, Any],
    *,
    profile: str,
    allow_dirty: bool = False,
) -> list[str]:
    """Return diagnostic codes; empty means OK for the profile."""
    errors: list[str] = []
    if manifest.get("schemaVersion") != RELEASE_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if manifest.get("profile") != profile:
        errors.append("profile_mismatch")
    if not manifest.get("source", {}).get("gitSha"):
        errors.append("git_sha_missing")
    locks = manifest.get("locks") or {}
    if not locks.get("uvLockSha256") or not locks.get("packageLockSha256"):
        errors.append("lock_digest_missing")
    if not (manifest.get("schema") or {}).get("alembicHead"):
        errors.append("alembic_head_missing")
    contracts = manifest.get("contracts") or {}
    if not contracts.get("apiVersion") or not contracts.get("sseSchemaVersion"):
        errors.append("contract_version_missing")
    lightrag = manifest.get("lightrag") or {}
    if not lightrag.get("pinnedVersion") or not lightrag.get("vendoredVersion"):
        errors.append("lightrag_version_missing")
    if lightrag.get("pinnedVersion") != lightrag.get("vendoredVersion"):
        errors.append("lightrag_version_mismatch")

    if profile == "release":
        if manifest.get("source", {}).get("dirty") and not allow_dirty:
            errors.append("dirty_tree")
        roles = manifest.get("roles") or {}
        for role in ("web", "api", "worker", "lightragRuntime"):
            pin = roles.get(role) or {}
            if not pin.get("digest"):
                errors.append(f"role_digest_missing:{role}")
            if is_placeholder_controller(str(pin.get("imageRef") or "")):
                errors.append("lightrag_stub_controller")
        gates = manifest.get("imageGates") or {}
        for key, expected in RELEASE_GATES.items():
            if gates.get(key) != expected:
                errors.append(f"image_gate_incomplete:{key}")
        upstream = manifest.get("upstreamImages") or {}
        for name in ("minio", "mc"):
            pin = upstream.get(name) or {}
            if not pin.get("digest"):
                errors.append(f"upstream_digest_missing:{name}")
        postgres = upstream.get("postgres") or {}
        if not postgres.get("digest") and not postgres.get("residual"):
            errors.append("postgres_pin_incomplete")
        if not manifest.get("rendererIds"):
            errors.append("renderer_ids_missing")
        if "production-supported" in json.dumps(manifest.get("packages") or {}):
            errors.append("support_label_forbidden")
        sboms = manifest.get("sboms") or []
        needed = set(distinct_digests(roles))
        have = {str(item.get("subjectDigest")) for item in sboms if isinstance(item, dict)}
        if needed - have:
            errors.append("sbom_missing_for_digest")
        if not manifest.get("provenance"):
            errors.append("provenance_missing")
        else:
            unknown = set(manifest["provenance"]) - PROVENANCE_ALLOWLIST
            if unknown:
                errors.append("provenance_allowlist_violation")

    blob = json.dumps(manifest, sort_keys=True)
    deny_hits = scan_deny_patterns(blob)
    if deny_hits:
        errors.append("privacy_deny_pattern:" + ",".join(deny_hits))
    return errors


def generate_manifest(
    *,
    profile: str,
    repo_root: Path | None = None,
    role_digests: Mapping[str, Any] | None = None,
    upstream_digests: Mapping[str, str] | None = None,
    sboms: Sequence[Mapping[str, str]] | None = None,
    syft_version: str | None = None,
    ci_run_id: str | None = None,
    allow_dirty_release: bool = False,
) -> dict[str, Any]:
    if profile not in {"pr", "release"}:
        raise ManifestError("profile_invalid", profile)
    root = repo_root or REPO_ROOT
    app = root / "app"

    git_sha, dirty = git_source(root)
    if profile == "release" and dirty and not allow_dirty_release:
        raise ManifestError("dirty_tree")

    uv_lock = app / "uv.lock"
    pkg_lock = app / "client" / "package-lock.json"
    locks = {
        "uvLockSha256": sha256_file(uv_lock),
        "packageLockSha256": sha256_file(pkg_lock),
    }
    pinned, vendored = read_lightrag_versions(
        runtime_path=app / "context_engine" / "services" / "lightrag_runtime.py",
        vendor_path=app / "vendor" / "lightrag" / "_version.py",
    )
    tags = read_upstream_tags(
        minio_compose=app / "compose.stack.minio.yml",
        stack_compose=app / "compose.stack.yml",
    )

    upstream: dict[str, dict[str, Any]] = {
        "minio": {"tag": tags["minio"]},
        "mc": {"tag": tags["mc"]},
        "postgres": {"tag": tags["postgres"]},
    }
    if upstream_digests:
        for key, digest in upstream_digests.items():
            if key not in upstream:
                continue
            if digest:
                upstream[key]["digest"] = normalize_digest(digest)

    image_gates = dict(RELEASE_GATES if profile == "release" else PR_GATES_PRESENT)
    packages = parse_uv_lock_versions(uv_lock)

    roles: dict[str, dict[str, Any]] | None = None
    if role_digests:
        roles = build_role_map(
            web_digest=str(role_digests["web"]["digest"]),
            controller_digest=str(role_digests["api"]["digest"]),
            web_ref=str(role_digests.get("web", {}).get("imageRef") or ""),
            controller_ref=str(role_digests.get("api", {}).get("imageRef") or ""),
        )
    elif profile == "release":
        raise ManifestError("role_digest_missing", "web/api")

    if profile == "release":
        for key in ("minio", "mc"):
            if "digest" not in upstream[key]:
                raise ManifestError("upstream_digest_missing", key)
        if "digest" not in upstream["postgres"]:
            upstream["postgres"]["residual"] = (
                "postgres:16 tag recorded; digest resolve deferred to operator "
                "release-full when registry inspect unavailable"
            )

    sbom_list = [dict(item) for item in (sboms or [])]
    subjects = distinct_digests(roles or {})
    if profile == "release":
        if not sbom_list:
            raise ManifestError("sbom_missing_for_digest")
        have = {str(item.get("subjectDigest")) for item in sbom_list}
        if set(subjects) - have:
            raise ManifestError("sbom_missing_for_digest")

    provenance = None
    if profile == "release":
        provenance = build_provenance(
            git_sha=git_sha,
            dirty=dirty,
            locks=locks,
            image_gates=image_gates,
            subject_digests=subjects,
            sbom_sha256s=[str(item.get("sha256")) for item in sbom_list],
            syft_version=syft_version or DEFAULT_SYFT_VERSION,
            ci_run_id=ci_run_id,
        )

    manifest: dict[str, Any] = {
        "schemaVersion": RELEASE_MANIFEST_SCHEMA_VERSION,
        "profile": profile,
        "source": {"gitSha": git_sha, "dirty": dirty},
        "platform": PLATFORM,
        "upstreamImages": upstream,
        "locks": locks,
        "schema": {
            "alembicHead": read_alembic_head(
                app / "context_engine" / "services" / "readiness.py"
            )
        },
        "contracts": {
            "apiVersion": read_api_version(
                app / "context_engine" / "api" / "contract_app.py"
            ),
            "sseSchemaVersion": read_sse_schema_version(app / "context_engine" / "models.py"),
        },
        "lightrag": {"pinnedVersion": pinned, "vendoredVersion": vendored},
        "imageGates": image_gates,
        "packages": packages,
        "rendererIds": list(RENDERER_IDS),
        "generator": {
            "name": GENERATOR_NAME,
            "syftVersion": syft_version or (DEFAULT_SYFT_VERSION if profile == "release" else None),
        },
    }
    if roles is not None:
        manifest["roles"] = roles
    if sbom_list:
        manifest["sboms"] = sbom_list
    if provenance is not None:
        manifest["provenance"] = provenance

    errors = validate_manifest_shape(
        manifest, profile=profile, allow_dirty=allow_dirty_release
    )
    if errors:
        raise ManifestError(errors[0], ",".join(errors[1:]) if len(errors) > 1 else "")
    return manifest


def load_inspect_digest(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    return normalize_digest(parse_image_inspect_digest(raw))


def check_manifest_file(
    path: Path,
    *,
    profile: str | None = None,
    expected: Mapping[str, Any] | None = None,
) -> list[str]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest_unreadable:{exc}"]
    prof = profile or str(manifest.get("profile") or "")
    if not prof:
        return ["profile_missing"]
    errors = validate_manifest_shape(manifest, profile=prof)
    if expected is not None:
        # Compare regeneratable pin fields against a freshly generated baseline.
        for key in ("locks", "schema", "contracts", "lightrag"):
            if manifest.get(key) != expected.get(key):
                errors.append(f"pin_drift:{key}")
    # SBOM file hash binding
    for item in manifest.get("sboms") or []:
        rel = str(item.get("path") or "")
        expected_hash = str(item.get("sha256") or "")
        if not rel or not expected_hash:
            errors.append("sbom_entry_incomplete")
            continue
        sbom_path = (REPO_ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
        if not sbom_path.is_file():
            errors.append("sbom_file_missing")
            continue
        actual = sha256_file(sbom_path)
        if actual != expected_hash:
            errors.append("sbom_hash_mismatch")
    return errors


def write_manifest(manifest: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("pr", "release"), default="pr")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", type=Path, help="Validate an existing manifest path")
    parser.add_argument("--web-inspect", type=Path, help="docker image inspect JSON for web")
    parser.add_argument(
        "--controller-inspect",
        type=Path,
        help="docker image inspect JSON for api/worker/lightrag controller",
    )
    parser.add_argument("--web-ref", default="")
    parser.add_argument("--controller-ref", default="")
    parser.add_argument("--minio-digest", default="")
    parser.add_argument("--mc-digest", default="")
    parser.add_argument("--postgres-digest", default="")
    parser.add_argument(
        "--sbom",
        action="append",
        default=[],
        help="subjectDigest=path (sha256 computed from file)",
    )
    parser.add_argument("--syft-version", default=DEFAULT_SYFT_VERSION)
    parser.add_argument("--ci-run-id", default=None)
    parser.add_argument(
        "--allow-dirty-release",
        action="store_true",
        help="Escape hatch for local evidence runs on a dirty worktree",
    )
    return parser.parse_args(argv)


def _parse_sbom_args(items: Sequence[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in items:
        if "=" not in item:
            raise ManifestError("sbom_arg_invalid", item)
        digest, path_s = item.split("=", 1)
        path = Path(path_s)
        if not path.is_file():
            raise ManifestError("sbom_file_missing", path_s)
        rel = path.as_posix()
        try:
            rel = str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
        except ValueError:
            pass
        out.append(
            {
                "subjectDigest": normalize_digest(digest),
                "path": rel,
                "sha256": sha256_file(path),
            }
        )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check:
            expected = None
            if args.profile == "pr":
                expected = generate_manifest(profile="pr")
            errors = check_manifest_file(
                args.check, profile=args.profile, expected=expected
            )
            if errors:
                print("FAIL " + " ".join(errors), file=sys.stderr)
                return 1
            print(f"OK {args.check}")
            return 0

        role_digests = None
        if args.web_inspect or args.controller_inspect:
            if not args.web_inspect or not args.controller_inspect:
                raise ManifestError(
                    "role_digest_missing", "need --web-inspect and --controller-inspect"
                )
            role_digests = {
                "web": {
                    "digest": load_inspect_digest(args.web_inspect),
                    "imageRef": args.web_ref,
                },
                "api": {
                    "digest": load_inspect_digest(args.controller_inspect),
                    "imageRef": args.controller_ref,
                },
            }
        upstream = {
            "minio": args.minio_digest,
            "mc": args.mc_digest,
            "postgres": args.postgres_digest,
        }
        sboms = _parse_sbom_args(args.sbom)
        manifest = generate_manifest(
            profile=args.profile,
            role_digests=role_digests,
            upstream_digests={k: v for k, v in upstream.items() if v},
            sboms=sboms,
            syft_version=args.syft_version,
            ci_run_id=args.ci_run_id,
            allow_dirty_release=args.allow_dirty_release,
        )
        write_manifest(manifest, args.output)
        print(f"wrote {args.output}")
        return 0
    except ManifestError as exc:
        print(f"FAIL {exc.code}" + (f" {exc.detail}" if exc.detail else ""), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
