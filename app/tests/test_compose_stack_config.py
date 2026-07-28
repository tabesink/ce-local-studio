"""P10-01 contract: Compose/image/env ingress-wired HTTP profile (no live smoke)."""

from __future__ import annotations

import re
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
DOCKERFILE = APP_ROOT / "Dockerfile"
DOCKERIGNORE = APP_ROOT / ".dockerignore"
COMPOSE = APP_ROOT / "compose.stack.yml"
ENV_EXAMPLE = APP_ROOT / ".env.stack.example"
VERIFY_SH = REPO_ROOT / "scripts" / "verify.sh"

STACK_PUBLIC_ORIGIN = "http://127.0.0.1:3000"
FRONTEND_PEER = "172.30.55.10/32"
STACK_SUBNET = "172.30.55.0/24"


def test_dockerfile_copies_alembic_migrations() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^\s*COPY\s+migrations\s+", text, flags=re.MULTILINE), (
        "backend Dockerfile must COPY migrations/ for Compose one-shot migrate"
    )


def test_dockerignore_does_not_exclude_migrations() -> None:
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert "migrations" not in lines
    assert "migrations/" not in lines
    assert not any(line == "migrations/**" for line in lines)


def test_compose_wires_shared_public_origin_to_api_and_frontend() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "CE_STACK_PUBLIC_ORIGIN" in text
    assert "CONTEXT_ENGINE_PUBLIC_ORIGIN: ${CE_STACK_PUBLIC_ORIGIN" in text
    assert "CE_PUBLIC_ORIGIN: ${CE_STACK_PUBLIC_ORIGIN" in text
    # Frontend must receive runtime public origin (production BFF fail-closed).
    frontend_block = text.split("frontend:", 1)[1]
    assert "CONTEXT_ENGINE_PUBLIC_ORIGIN" in frontend_block
    assert "CONTEXT_ENGINE_API_BASE: http://api:8000" in frontend_block


def test_compose_pins_frontend_peer_not_broad_private_cidr() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert STACK_SUBNET in text
    assert "ipv4_address: 172.30.55.10" in text
    assert "172.30.55.10/32" in text  # documented in compose comments
    assert f"CE_TRUSTED_BFF_PEERS={FRONTEND_PEER}" in example
    # Optional empty default preserves secondary bypass (partial CE_* must not default peers alone).
    assert "CE_TRUSTED_BFF_PEERS: ${CE_TRUSTED_BFF_PEERS:-}" in text
    assert "172.16.0.0/12" not in text
    assert "172.16.0.0/12" not in example


def test_compose_keeps_one_shot_migrate_before_api_worker() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert 'command: ["alembic", "upgrade", "head"]' in text
    assert 'condition: service_completed_successfully' in text
    assert 'restart: "no"' in text


def test_compose_bootstrap_before_api_with_admin_secrets_only_on_bootstrap() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "bootstrap:" in text
    assert 'command: ["python", "-m", "context_engine.bootstrap_admin"]' in text

    bootstrap_block = text.split("bootstrap:", 1)[1].split("\n  api:", 1)[0]
    assert "CE_ADMIN_USERNAME:" in bootstrap_block
    assert "CE_ADMIN_PASSWORD:" in bootstrap_block
    assert 'restart: "no"' in bootstrap_block
    assert "migrate:" in bootstrap_block or "condition: service_completed_successfully" in bootstrap_block

    api_block = text.split("\n  api:", 1)[1].split("\n  worker:", 1)[0]
    worker_block = text.split("\n  worker:", 1)[1].split("\n  frontend:", 1)[0]
    assert "CE_ADMIN_USERNAME" not in api_block
    assert "CE_ADMIN_PASSWORD" not in api_block
    assert "CE_ADMIN_USERNAME" not in worker_block
    assert "CE_ADMIN_PASSWORD" not in worker_block
    assert "bootstrap:" in api_block
    assert "service_completed_successfully" in api_block
    assert "bootstrap:" in worker_block
    assert "service_completed_successfully" in worker_block
    assert "stop_grace_period: 60s" in worker_block
    assert "CE_TURN_WORKER_ID:" in worker_block


def test_env_example_documents_worker_path_inline_split() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "CE_INLINE_TURN_WORKERS" in text
    assert "worker-path smoke" in text.casefold() or "worker path smoke" in text.casefold()
    assert "compose-stack-runbook" in text or "compose-stack-runbook.md" in text


def test_env_example_primary_is_ingress_wired_http_not_bypass() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "CE_STACK_PUBLIC_ORIGIN=" in text
    assert "CONTEXT_ENGINE_TESTING=true" in text
    assert "CE_INTERNAL_HOSTS=api" in text
    assert "CE_TRUSTED_BFF_PEERS=172.30.55.10/32" in text
    assert "CE_SESSION_COOKIE_SECURE=false" in text
    assert "ingress-wired" in text.casefold() or "ingress wired" in text.casefold()
    # Secondary bypass must remain documented, not the uncommented green path.
    assert "bypass" in text.casefold()
    assert "not deployment evidence" in text.casefold() or "not p12" in text.casefold()


def test_env_example_csrf_key_distinct_from_encryption_placeholder() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    csrf_match = re.search(r"^CE_CSRF_SIGNING_KEY=(.+)$", text, flags=re.MULTILINE)
    enc_match = re.search(r"^CONFIG_ENCRYPTION_KEY=(.+)$", text, flags=re.MULTILINE)
    assert csrf_match is not None
    assert enc_match is not None
    csrf = csrf_match.group(1).strip()
    enc = enc_match.group(1).strip()
    assert csrf and enc
    assert csrf != enc
    assert len(csrf.encode("utf-8")) >= 32


def test_verify_sh_compose_check_supplies_ingress_placeholders() -> None:
    text = VERIFY_SH.read_text(encoding="utf-8")
    assert "CE_STACK_PUBLIC_ORIGIN=" in text or "CE_PUBLIC_ORIGIN=" in text
    assert "CE_INTERNAL_HOSTS=" in text
    assert "CE_TRUSTED_BFF_PEERS=" in text
    assert "CE_CSRF_SIGNING_KEY=" in text
