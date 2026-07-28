"""P10-01 contract: Compose/image/env ingress-wired HTTP profile (no live smoke)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
DOCKERFILE = APP_ROOT / "Dockerfile"
DOCKERIGNORE = APP_ROOT / ".dockerignore"
COMPOSE = APP_ROOT / "compose.stack.yml"
COMPOSE_LIVE = APP_ROOT / "compose.stack.live.yml"
COMPOSE_MINIO = APP_ROOT / "compose.stack.minio.yml"
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
    assert 'command: ["python", "-m", "context_engine.migrate_release"]' in text
    assert 'command: ["alembic", "upgrade", "head"]' not in text
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


def test_default_compose_keeps_local_controller_and_client() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND: local" in text
    assert "CE_LIGHTRAG_CLIENT_KIND: local" in text
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND: docker" not in text
    assert "CE_LIGHTRAG_CLIENT_KIND: native" not in text


def test_live_overlay_exists_and_pins_docker_native() -> None:
    assert COMPOSE_LIVE.is_file()
    text = COMPOSE_LIVE.read_text(encoding="utf-8")
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND: docker" in text
    assert "CE_LIGHTRAG_CLIENT_KIND: native" in text
    assert "CE_STACK_LIVE_IMAGE" in text
    assert "ce-domain-runtimes" in text
    assert "/var/run/docker.sock" in text
    assert "CE_STACK_LIVE_RUNTIME_ROOT" in text


def test_env_example_documents_live_docker_native_lane() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "compose.stack.live.yml" in text
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND=docker" in text or "CONTROLLER_KIND=docker" in text
    assert "CE_LIGHTRAG_CLIENT_KIND=native" in text or "CLIENT_KIND=native" in text
    assert "CE_STACK_LIVE_RUNTIME_ROOT" in text
    assert "local/local" in text or "stays local/local" in text


def _compose_config_env(
    *,
    live_runtime_root: str | None = None,
    minio: bool = False,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "POSTGRES_DB": "ce",
            "POSTGRES_USER": "ce",
            "POSTGRES_PASSWORD": "ce-password",
            "CONFIG_ENCRYPTION_KEY": "test-encryption-key-32-bytes-min!",
            "CE_ADMIN_USERNAME": "admin",
            "CE_ADMIN_PASSWORD": "admin-password-for-compose-config",
            "CE_STACK_PUBLIC_ORIGIN": STACK_PUBLIC_ORIGIN,
            "CE_INTERNAL_HOSTS": "api",
            "CE_TRUSTED_BFF_PEERS": FRONTEND_PEER,
            "CE_CSRF_SIGNING_KEY": "test-csrf-signing-key-32-bytes-min!!",
        }
    )
    if live_runtime_root is not None:
        env["CE_STACK_LIVE_RUNTIME_ROOT"] = live_runtime_root
        env["CE_DOMAIN_CONTROLLER_IMAGE"] = "context-engine-live:local"
    if minio:
        env.update(
            {
                "MINIO_ROOT_USER": "minio-root",
                "MINIO_ROOT_PASSWORD": "minio-root-password-min-8",
                "CE_S3_BUCKET": "ce-objects",
                "CE_S3_ACCESS_KEY": "ce-app-access",
                "CE_S3_SECRET_KEY": "ce-app-secret-key-min",
                "CE_S3_RECON_ACCESS_KEY": "ce-recon-access",
                "CE_S3_RECON_SECRET_KEY": "ce-recon-secret-key",
            }
        )
    return env


def test_compose_config_default_resolves_local_kinds() -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config"],
        cwd=str(APP_ROOT),
        env=_compose_config_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND: local" in result.stdout
    assert "CE_LIGHTRAG_CLIENT_KIND: local" in result.stdout


def test_compose_live_overlay_config_resolves_docker_native() -> None:
    live_root = "/tmp/ce-p5-04-live-runtime-config"
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "-f",
            str(COMPOSE_LIVE),
            "config",
        ],
        cwd=str(APP_ROOT),
        env=_compose_config_env(live_runtime_root=live_root),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CE_DOMAIN_RUNTIME_CONTROLLER_KIND: docker" in result.stdout
    assert "CE_LIGHTRAG_CLIENT_KIND: native" in result.stdout
    assert "context-engine-live:local" in result.stdout
    assert "ce-domain-runtimes" in result.stdout
    assert live_root in result.stdout


def test_compose_live_overlay_fails_closed_without_runtime_root() -> None:
    env = _compose_config_env()
    env.pop("CE_STACK_LIVE_RUNTIME_ROOT", None)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "-f",
            str(COMPOSE_LIVE),
            "config",
        ],
        cwd=str(APP_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "ce_stack_live_runtime_root" in combined


def test_minio_overlay_exists_and_pins_s3_kind() -> None:
    assert COMPOSE_MINIO.is_file()
    text = COMPOSE_MINIO.read_text(encoding="utf-8")
    assert "CE_OBJECT_STORE_KIND: s3" in text
    assert "CE_STACK_OBJECT_STORE_IMAGE" in text
    assert "minio-init" in text
    assert "MINIO_ROOT_USER" in text
    assert "CE_S3_RECON_ACCESS_KEY" in text
    assert "stack-source-local" in text


def test_env_example_documents_minio_overlay() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "compose.stack.minio.yml" in text
    assert "CE_OBJECT_STORE_KIND=s3" in text or "CE_OBJECT_STORE_KIND" in text
    assert "MINIO_ROOT_USER" in text
    assert "CE_S3_RECON_ACCESS_KEY" in text
    assert "CE_STACK_OBJECT_STORE_IMAGE" in text


def test_compose_config_default_has_no_minio() -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config"],
        cwd=str(APP_ROOT),
        env=_compose_config_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CE_OBJECT_STORE_KIND: s3" not in result.stdout
    assert "image: minio/minio" not in result.stdout
    assert "stack-source-storage" in result.stdout


def test_compose_minio_overlay_config_resolves_s3() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "-f",
            str(COMPOSE_MINIO),
            "config",
        ],
        cwd=str(APP_ROOT),
        env=_compose_config_env(minio=True),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CE_OBJECT_STORE_KIND: s3" in result.stdout
    assert "CE_S3_ENDPOINT: http://minio:9000" in result.stdout
    assert "CE_STACK_OBJECT_STORE_IMAGE" in result.stdout or "object-store" in result.stdout.lower() or "CE_STACK_OBJECT_STORE_IMAGE: \"1\"" in result.stdout or 'CE_STACK_OBJECT_STORE_IMAGE: "1"' in result.stdout or "CE_STACK_OBJECT_STORE_IMAGE: '1'" in result.stdout or "CE_STACK_OBJECT_STORE_IMAGE: 1" in result.stdout
    # App secrets on api/worker; root + recon must not appear on frontend.
    assert "MINIO_ROOT_PASSWORD" not in _service_env_block(result.stdout, "frontend")
    assert "CE_S3_SECRET_KEY" not in _service_env_block(result.stdout, "frontend")
    assert "CE_S3_RECON_SECRET_KEY" not in _service_env_block(result.stdout, "api")
    assert "CE_S3_RECON_SECRET_KEY" not in _service_env_block(result.stdout, "worker")
    assert "MINIO_ROOT_PASSWORD" not in _service_env_block(result.stdout, "api")
    assert "stack-source-local" in result.stdout


def test_compose_minio_overlay_fails_closed_without_bucket() -> None:
    env = _compose_config_env(minio=True)
    env.pop("CE_S3_BUCKET", None)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "-f",
            str(COMPOSE_MINIO),
            "config",
        ],
        cwd=str(APP_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "ce_s3_bucket" in combined


def _service_env_block(compose_config: str, service: str) -> str:
    """Best-effort extract of a service stanza from `docker compose config` YAML."""
    marker = f"  {service}:\n"
    start = compose_config.find(marker)
    if start < 0:
        return ""
    rest = compose_config[start + len(marker) :]
    # Next top-level service under services: is indented with two spaces then name.
    next_service = re.search(r"\n  [a-z0-9_-]+:\n", rest)
    if next_service:
        return rest[: next_service.start()]
    return rest
