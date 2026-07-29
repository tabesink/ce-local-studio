"""P12-06 unit tests for release manifest generation and verify diagnostics.

No live Docker or Syft required — fixture inspect JSON and mock SBOM files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_release_manifest import (
    ManifestError,
    PLACEHOLDER_CONTROLLER_IMAGES,
    RELEASE_GATES,
    build_role_map,
    check_manifest_file,
    distinct_digests,
    generate_manifest,
    is_placeholder_controller,
    main,
    normalize_digest,
    parse_compose_image_tag,
    scan_deny_patterns,
    validate_manifest_shape,
    write_manifest,
)
from scripts.stack_image_rollback_drill import parse_image_inspect_digest

DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)


def _inspect_json(image_id: str = DIGEST_A) -> str:
    return json.dumps([{"Id": image_id, "RepoDigests": []}])


def _sbom_entry(tmp_path: Path, digest: str, name: str = "web.cdx.json") -> dict[str, str]:
    path = tmp_path / name
    path.write_text(
        json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [{"name": "x"}]}),
        encoding="utf-8",
    )
    from scripts.generate_release_manifest import sha256_file

    return {
        "subjectDigest": digest,
        "path": str(path),
        "sha256": sha256_file(path),
    }


def test_pr_profile_emits_without_image_digests() -> None:
    manifest = generate_manifest(profile="pr")
    assert manifest["profile"] == "pr"
    assert manifest["schemaVersion"] == "1"
    assert "roles" not in manifest or not manifest.get("roles")
    assert manifest["locks"]["uvLockSha256"]
    assert manifest["schema"]["alembicHead"]
    assert manifest["contracts"]["apiVersion"]
    assert manifest["contracts"]["sseSchemaVersion"]
    assert manifest["lightrag"]["pinnedVersion"] == manifest["lightrag"]["vendoredVersion"]
    assert "production-supported" not in json.dumps(manifest.get("packages") or {})
    assert "LibreOffice" not in json.dumps(manifest)


def test_release_missing_roles_fails() -> None:
    with pytest.raises(ManifestError) as exc:
        generate_manifest(profile="release", allow_dirty_release=True)
    assert exc.value.code == "role_digest_missing"


def test_release_stub_controller_fails(tmp_path: Path) -> None:
    with pytest.raises(ManifestError) as exc:
        build_role_map(
            web_digest=DIGEST_A,
            controller_digest=DIGEST_B,
            controller_ref="alpine:3.20",
        )
    assert exc.value.code == "lightrag_stub_controller"
    assert "alpine:3.20" in PLACEHOLDER_CONTROLLER_IMAGES
    assert is_placeholder_controller("alpine:3.20")


def test_release_empty_controller_ref_fails() -> None:
    with pytest.raises(ManifestError) as exc:
        build_role_map(
            web_digest=DIGEST_A,
            controller_digest=DIGEST_B,
            controller_ref="",
        )
    assert exc.value.code == "controller_ref_required"


def test_release_complete_fixture(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    sboms = [
        _sbom_entry(tmp_path, DIGEST_A, "web.cdx.json"),
        _sbom_entry(tmp_path, DIGEST_B, "controller.cdx.json"),
    ]
    manifest = generate_manifest(
        profile="release",
        role_digests=roles,
        upstream_digests={"minio": DIGEST_C, "mc": DIGEST_C, "postgres": DIGEST_C},
        sboms=sboms,
        syft_version="v1.20.0",
        allow_dirty_release=True,
    )
    assert manifest["profile"] == "release"
    assert manifest["roles"]["worker"]["digest"] == DIGEST_B
    assert manifest["roles"]["worker"]["sameAs"] == "api"
    assert manifest["roles"]["lightragRuntime"]["sameAs"] == "api"
    assert manifest["imageGates"] == RELEASE_GATES
    assert set(distinct_digests(manifest["roles"])) == {DIGEST_A, DIGEST_B}
    assert len(manifest["sboms"]) == 2
    assert manifest["provenance"]["syftVersion"] == "v1.20.0"
    assert "ce-preview-v1" in manifest["rendererIds"]
    assert "ce-preview-text-v1" in manifest["rendererIds"]
    assert "ce-preview-pdf-passthrough-v1" in manifest["rendererIds"]


def test_release_missing_minio_digest_fails(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    with pytest.raises(ManifestError) as exc:
        generate_manifest(
            profile="release",
            role_digests=roles,
            upstream_digests={},
            sboms=[
                _sbom_entry(tmp_path, DIGEST_A, "w.cdx.json"),
                _sbom_entry(tmp_path, DIGEST_B, "c.cdx.json"),
            ],
            allow_dirty_release=True,
        )
    assert exc.value.code == "upstream_digest_missing"


def test_release_missing_sbom_fails(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    with pytest.raises(ManifestError) as exc:
        generate_manifest(
            profile="release",
            role_digests=roles,
            upstream_digests={"minio": DIGEST_C, "mc": DIGEST_C, "postgres": DIGEST_C},
            sboms=[],
            allow_dirty_release=True,
        )
    assert exc.value.code == "sbom_missing_for_digest"


def test_mutate_digest_fails_validate(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    sboms = [
        _sbom_entry(tmp_path, DIGEST_A, "web.cdx.json"),
        _sbom_entry(tmp_path, DIGEST_B, "controller.cdx.json"),
    ]
    manifest = generate_manifest(
        profile="release",
        role_digests=roles,
        upstream_digests={"minio": DIGEST_C, "mc": DIGEST_C, "postgres": DIGEST_C},
        sboms=sboms,
        allow_dirty_release=True,
    )
    manifest["roles"]["web"]["digest"] = "sha256:" + ("e" * 64)
    # SBOM still lists DIGEST_A → missing for new digest / orphan
    errors = validate_manifest_shape(manifest, profile="release")
    assert "sbom_missing_for_digest" in errors


def test_sbom_hash_mismatch_detected(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    sboms = [
        _sbom_entry(tmp_path, DIGEST_A, "web.cdx.json"),
        _sbom_entry(tmp_path, DIGEST_B, "controller.cdx.json"),
    ]
    manifest = generate_manifest(
        profile="release",
        role_digests=roles,
        upstream_digests={"minio": DIGEST_C, "mc": DIGEST_C, "postgres": DIGEST_C},
        sboms=sboms,
        allow_dirty_release=True,
    )
    out = tmp_path / "release-manifest.json"
    write_manifest(manifest, out)
    # Tamper SBOM bytes after write
    Path(sboms[0]["path"]).write_text('{"bomFormat":"CycloneDX","components":[]}', encoding="utf-8")
    errors = check_manifest_file(out, profile="release")
    assert "sbom_hash_mismatch" in errors


def test_schema_version_missing_fails() -> None:
    manifest = generate_manifest(profile="pr")
    del manifest["schemaVersion"]
    errors = validate_manifest_shape(manifest, profile="pr")
    assert "schema_version_invalid" in errors


def test_privacy_deny_pattern() -> None:
    assert scan_deny_patterns('{"x":"CONFIG_ENCRYPTION_KEY=abc"}')
    assert not scan_deny_patterns('{"gitSha":"abc","locks":{}}')


def test_parse_inspect_and_compose_helpers() -> None:
    assert normalize_digest("a" * 64) == "sha256:" + ("a" * 64)
    assert parse_image_inspect_digest(_inspect_json(DIGEST_A)) == DIGEST_A
    tag = parse_compose_image_tag(
        "services:\n  minio:\n    image: minio/minio:RELEASE.2024-12-18T13-15-44Z\n",
        "minio/minio:",
    )
    assert tag.startswith("minio/minio:")


def test_main_pr_writes(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    assert main(["--profile", "pr", "--output", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["profile"] == "pr"


def test_main_release_stub_exits(tmp_path: Path) -> None:
    web = tmp_path / "web.json"
    ctl = tmp_path / "ctl.json"
    web.write_text(_inspect_json(DIGEST_A), encoding="utf-8")
    ctl.write_text(_inspect_json(DIGEST_B), encoding="utf-8")
    code = main(
        [
            "--profile",
            "release",
            "--assert-release-gates",
            "--allow-dirty-release",
            "--web-inspect",
            str(web),
            "--controller-inspect",
            str(ctl),
            "--controller-ref",
            "alpine:3.20",
            "--minio-digest",
            DIGEST_C,
            "--mc-digest",
            DIGEST_C,
            "--postgres-digest",
            DIGEST_C,
            "--sbom",
            f"{DIGEST_A}={_sbom_entry(tmp_path, DIGEST_A)['path']}",
            "--sbom",
            f"{DIGEST_B}={_sbom_entry(tmp_path, DIGEST_B, 'c.cdx.json')['path']}",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == 1


def test_main_release_requires_gate_attestation(tmp_path: Path) -> None:
    code = main(
        [
            "--profile",
            "release",
            "--allow-dirty-release",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert code == 1


def test_release_check_detects_lock_drift(tmp_path: Path) -> None:
    roles = {
        "web": {"digest": DIGEST_A, "imageRef": "ce-web:local"},
        "api": {"digest": DIGEST_B, "imageRef": "context-engine-live:local"},
    }
    sboms = [
        _sbom_entry(tmp_path, DIGEST_A, "web.cdx.json"),
        _sbom_entry(tmp_path, DIGEST_B, "controller.cdx.json"),
    ]
    manifest = generate_manifest(
        profile="release",
        role_digests=roles,
        upstream_digests={"minio": DIGEST_C, "mc": DIGEST_C, "postgres": DIGEST_C},
        sboms=sboms,
        allow_dirty_release=True,
    )
    manifest["locks"]["uvLockSha256"] = "0" * 64
    out = tmp_path / "release.json"
    write_manifest(manifest, out)
    errors = check_manifest_file(
        out,
        profile="release",
        expected=generate_manifest(profile="pr", allow_dirty_release=True),
        allow_dirty=True,
    )
    assert any(e.startswith("pin_drift:") for e in errors)
