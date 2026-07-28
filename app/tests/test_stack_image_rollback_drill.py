"""P12-04 U4 unit tests for schema-compatible image rollback helpers.

No live Docker required — pure digest recording, refuse-downgrade, and go/no-go.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.stack_image_rollback_drill import (
    IMAGE_ROLLBACK_RECORD_SCHEMA_VERSION,
    assert_same_alembic_head,
    build_image_digest_record,
    document_ready_smoke_steps,
    document_swap_steps,
    incompatible_image_go_no_go,
    main,
    parse_image_inspect_digest,
    refuse_improvised_downgrade_message,
)


def test_refuse_downgrade_path_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    message = refuse_improvised_downgrade_message()
    assert "alembic downgrade" in message
    assert "improvised down migration" in message.lower() or "Improvised down migration" in message
    assert "deployment-topology.md" in message
    assert "p1-01-foundation-evidence.md" in message
    assert "restore" in message.lower()

    assert main(["--attempt-downgrade"]) == 1
    captured = capsys.readouterr()
    assert "REFUSE" in captured.err
    assert "alembic downgrade" in captured.err
    assert "deployment-topology.md" in captured.err


def test_digest_record_shape(tmp_path: Path) -> None:
    record = build_image_digest_record(
        alembic_head="rev_head_abc",
        current_digests={
            "api": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "worker": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        },
        prior_digests={
            "api": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "worker": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        },
    )
    assert record["schemaVersion"] == IMAGE_ROLLBACK_RECORD_SCHEMA_VERSION
    assert record["alembicHead"] == "rev_head_abc"
    assert record["services"] == ["api", "worker"]
    assert record["schemaCompatible"] is True
    assert set(record["currentDigests"]) == {"api", "worker"}
    assert set(record["priorDigests"]) == {"api", "worker"}
    assert record["currentDigests"]["api"].startswith("sha256:")
    assert "P12-06/08" in record["notes"]

    out = tmp_path / "image-rollback-digests.json"
    assert (
        main(
            [
                "--alembic-head",
                "rev_head_abc",
                "--current-digest",
                "api=sha256:aa",
                "--current-digest",
                "worker=sha256:bb",
                "--prior-digest",
                "api=sha256:cc",
                "--prior-digest",
                "worker=sha256:dd",
                "--record-out",
                str(out),
            ]
        )
        == 0
    )
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["alembicHead"] == "rev_head_abc"
    assert loaded["priorDigests"]["api"] == "sha256:cc"


def test_digest_record_requires_head_and_services() -> None:
    with pytest.raises(ValueError, match="alembic_head_required"):
        build_image_digest_record(
            alembic_head="",
            current_digests={"api": "sha256:a", "worker": "sha256:b"},
            prior_digests={"api": "sha256:c", "worker": "sha256:d"},
        )
    with pytest.raises(ValueError, match="prior_digest_missing:worker"):
        build_image_digest_record(
            alembic_head="head1",
            current_digests={"api": "sha256:a", "worker": "sha256:b"},
            prior_digests={"api": "sha256:c"},
        )
    assert assert_same_alembic_head("head1", "head1") == []
    assert "alembic_head_mismatch" in assert_same_alembic_head("head1", "head2")[0]


def test_incompatible_image_go_no_go_points_to_restore(
    capsys: pytest.CaptureFixture[str],
) -> None:
    go = incompatible_image_go_no_go(prior_ready=True)
    assert go["decision"] == "go"
    assert go["path"] == "image_rollback"
    assert go["refuseDowngrade"] is True

    no_go = incompatible_image_go_no_go(prior_ready=False)
    assert no_go["decision"] == "no-go"
    assert no_go["action"] == "restore"
    assert no_go["path"] == "restore"
    assert no_go["refuse"] == "alembic_downgrade"
    assert "alembic downgrade" in no_go["message"]
    assert "restore" in no_go["message"].lower()

    assert main(["--no-prior-ready"]) == 1
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["decision"] == "no-go"
    assert body["path"] == "restore"
    assert "REFUSE" in captured.err

    assert main(["--prior-ready"]) == 0
    go_body = json.loads(capsys.readouterr().out)
    assert go_body["decision"] == "go"


def test_parse_inspect_and_document_steps() -> None:
    inspect = [
        {
            "Id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "RepoDigests": [
                "ce-api@sha256:2222222222222222222222222222222222222222222222222222222222222222"
            ],
        }
    ]
    assert (
        parse_image_inspect_digest(inspect)
        == "sha256:2222222222222222222222222222222222222222222222222222222222222222"
    )
    assert (
        parse_image_inspect_digest({"Id": "sha256:abcdef", "RepoDigests": []})
        == "sha256:abcdef"
    )

    swap = document_swap_steps(
        prior_digests={
            "api": "sha256:cc",
            "worker": "sha256:dd",
            "frontend": "sha256:ee",
        },
        include_frontend=True,
    )
    joined = "\n".join(swap)
    assert "api" in joined and "worker" in joined and "frontend" in joined
    assert "alembic downgrade" in joined

    ready = "\n".join(document_ready_smoke_steps())
    assert "/health/ready" in ready
    assert "stack_smoke_core" in ready
    assert "restore" in ready.lower()
