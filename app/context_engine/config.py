from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    return int(value)


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_bool(name: str) -> bool | None:
    """Return None when unset so callers can fall back to another default."""
    value = _env(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env(
            "CONTEXT_ENGINE_DATABASE_URL",
            "postgresql+psycopg://context_engine@localhost/context_engine",
        )
        or "postgresql+psycopg://context_engine@localhost/context_engine"
    )
    admin_username: str | None = field(default_factory=lambda: _env("CE_ADMIN_USERNAME"))
    admin_password: str | None = field(default_factory=lambda: _env("CE_ADMIN_PASSWORD"), repr=False)
    config_encryption_key: str | None = field(default_factory=lambda: _env("CONFIG_ENCRYPTION_KEY"), repr=False)
    testing: bool = field(default_factory=lambda: _env_bool("CONTEXT_ENGINE_TESTING", False))
    # Tri-state: unset → follow testing when testing=true; never inline when testing=false.
    inline_turn_workers: bool | None = field(default_factory=lambda: _env_optional_bool("CE_INLINE_TURN_WORKERS"))
    session_cookie_name: str = "ce_session"
    csrf_cookie_name: str = "ce_csrf"
    session_cookie_secure: bool = field(default_factory=lambda: _env_bool("CE_SESSION_COOKIE_SECURE", True))
    session_cookie_samesite: str = field(default_factory=lambda: _env("CE_SESSION_COOKIE_SAMESITE", "lax") or "lax")
    session_ttl_seconds: int = field(default_factory=lambda: _env_int("CE_SESSION_TTL_SECONDS", 60 * 60 * 8))
    session_idle_ttl_seconds: int = field(default_factory=lambda: _env_int("CE_SESSION_IDLE_TTL_SECONDS", 60 * 30))
    session_touch_interval_seconds: int = field(default_factory=lambda: _env_int("CE_SESSION_TOUCH_INTERVAL_SECONDS", 60))
    public_origin: str | None = field(default_factory=lambda: _env("CE_PUBLIC_ORIGIN"))
    internal_hosts: str | None = field(default_factory=lambda: _env("CE_INTERNAL_HOSTS"))
    trusted_bff_peers: str | None = field(default_factory=lambda: _env("CE_TRUSTED_BFF_PEERS"))
    csrf_signing_key: str | None = field(default_factory=lambda: _env("CE_CSRF_SIGNING_KEY"), repr=False)
    login_throttle_window_seconds: int = field(default_factory=lambda: _env_int("CE_LOGIN_THROTTLE_WINDOW_SECONDS", 300))
    login_throttle_max_failures: int = field(default_factory=lambda: _env_int("CE_LOGIN_THROTTLE_MAX_FAILURES", 5))
    login_throttle_block_seconds: int = field(default_factory=lambda: _env_int("CE_LOGIN_THROTTLE_BLOCK_SECONDS", 900))
    domain_runtime_root: str = field(default_factory=lambda: _env("CE_DOMAIN_RUNTIME_ROOT", ".data/domain-runtimes") or ".data/domain-runtimes")
    domain_runtime_controller_kind: str = field(default_factory=lambda: _env("CE_DOMAIN_RUNTIME_CONTROLLER_KIND", "docker") or "docker")
    domain_controller_command: str | None = field(default_factory=lambda: _env("CE_DOMAIN_CONTROLLER_COMMAND"))
    domain_controller_timeout_seconds: int = field(default_factory=lambda: _env_int("CE_DOMAIN_CONTROLLER_TIMEOUT_SECONDS", 30))
    domain_controller_image: str = field(
        default_factory=lambda: _env("CE_DOMAIN_CONTROLLER_IMAGE", "alpine:3.20") or "alpine:3.20"
    )
    domain_controller_network: str = field(
        default_factory=lambda: _env("CE_DOMAIN_CONTROLLER_NETWORK", "ce-domain-runtimes") or "ce-domain-runtimes"
    )
    domain_lightrag_port: int = field(default_factory=lambda: _env_int("CE_DOMAIN_LIGHTRAG_PORT", 9621))
    domain_delete_worker_id: str = field(default_factory=lambda: _env("CE_DOMAIN_DELETE_WORKER_ID", "domain-delete-worker") or "domain-delete-worker")
    domain_delete_lease_seconds: int = field(default_factory=lambda: _env_int("CE_DOMAIN_DELETE_LEASE_SECONDS", 60))
    domain_lifecycle_worker_id: str = field(
        default_factory=lambda: _env("CE_DOMAIN_LIFECYCLE_WORKER_ID", "domain-lifecycle") or "domain-lifecycle"
    )
    domain_lifecycle_lease_seconds: int = field(default_factory=lambda: _env_int("CE_DOMAIN_LIFECYCLE_LEASE_SECONDS", 60))
    source_storage_root: str = field(default_factory=lambda: _env("CE_SOURCE_STORAGE_ROOT", ".data/source-storage") or ".data/source-storage")
    domain_storage_limit_bytes: int = field(default_factory=lambda: _env_int("CE_DOMAIN_STORAGE_LIMIT_BYTES", 5 * 1024 * 1024 * 1024))
    source_prep_worker_id: str = field(default_factory=lambda: _env("CE_SOURCE_PREP_WORKER_ID", "source-prep-worker") or "source-prep-worker")
    source_prep_lease_seconds: int = field(default_factory=lambda: _env_int("CE_SOURCE_PREP_LEASE_SECONDS", 180))
    source_parser_timeout_seconds: int = field(default_factory=lambda: _env_int("CE_SOURCE_PARSER_TIMEOUT_SECONDS", 120))
    source_delete_worker_id: str = field(
        default_factory=lambda: _env("CE_SOURCE_DELETE_WORKER_ID", "source-delete-worker") or "source-delete-worker"
    )
    source_delete_lease_seconds: int = field(default_factory=lambda: _env_int("CE_SOURCE_DELETE_LEASE_SECONDS", 60))
    source_index_worker_id: str = field(default_factory=lambda: _env("CE_SOURCE_INDEX_WORKER_ID", "source-index-worker") or "source-index-worker")
    source_index_lease_seconds: int = field(default_factory=lambda: _env_int("CE_SOURCE_INDEX_LEASE_SECONDS", 180))
    source_index_timeout_seconds: int = field(default_factory=lambda: _env_int("CE_SOURCE_INDEX_TIMEOUT_SECONDS", 120))
    source_index_poll_backoff_seconds: int = field(
        default_factory=lambda: _env_int("CE_SOURCE_INDEX_POLL_BACKOFF_SECONDS", 5)
    )
    retrieval_timeout_seconds: int = field(default_factory=lambda: _env_int("CE_RETRIEVAL_TIMEOUT_SECONDS", 30))
    retrieval_global_concurrency: int = field(default_factory=lambda: _env_int("CE_RETRIEVAL_GLOBAL_CONCURRENCY", 8))
    retrieval_per_domain_concurrency: int = field(
        default_factory=lambda: _env_int("CE_RETRIEVAL_PER_DOMAIN_CONCURRENCY", 2)
    )
    retrieval_max_candidates: int = field(default_factory=lambda: _env_int("CE_RETRIEVAL_MAX_CANDIDATES", 10))
    retrieval_max_candidate_bytes: int = field(
        default_factory=lambda: _env_int("CE_RETRIEVAL_MAX_CANDIDATE_BYTES", 256 * 1024)
    )
    retrieval_max_aggregate_bytes: int = field(
        default_factory=lambda: _env_int("CE_RETRIEVAL_MAX_AGGREGATE_BYTES", 1024 * 1024)
    )
    synthesis_timeout_seconds: int = field(default_factory=lambda: _env_int("CE_SYNTHESIS_TIMEOUT_SECONDS", 60))
    synthesis_max_output_tokens: int = field(default_factory=lambda: _env_int("CE_SYNTHESIS_MAX_OUTPUT_TOKENS", 4096))
    turn_worker_id: str = field(default_factory=lambda: _env("CE_TURN_WORKER_ID", "turn-worker") or "turn-worker")
    turn_lease_seconds: int = field(default_factory=lambda: _env_int("CE_TURN_LEASE_SECONDS", 180))
    turn_tail_poll_milliseconds: int = field(default_factory=lambda: _env_int("CE_TURN_TAIL_POLL_MILLISECONDS", 250))
    turn_tail_idle_seconds: int = field(default_factory=lambda: _env_int("CE_TURN_TAIL_IDLE_SECONDS", 30))
    lightrag_client_kind: str = field(default_factory=lambda: _env("CE_LIGHTRAG_CLIENT_KIND", "native") or "native")
    # Residual/dev only: in-process synthetic LightRAG behind the process-wide lock.
    # Production live lane uses private HTTP (PrivateHttpLightRAGClient) when this is false.
    lightrag_inprocess_synthetic: bool = field(
        default_factory=lambda: _env_bool("CE_LIGHTRAG_INPROCESS_SYNTHETIC", False)
    )
    worker_idle_seconds: int = field(default_factory=lambda: _env_int("CE_WORKER_IDLE_SECONDS", 2))

    def __post_init__(self) -> None:
        samesite = self.session_cookie_samesite.strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            raise ValueError("session_cookie_samesite must be one of 'lax', 'strict', or 'none'.")
        if samesite == "none" and not self.session_cookie_secure:
            # Browsers reject SameSite=None cookies without Secure; failing fast
            # beats silently shipping a session cookie the browser will drop.
            raise ValueError("session_cookie_samesite='none' requires session_cookie_secure=True.")
        object.__setattr__(self, "session_cookie_samesite", samesite)
        if self.session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be positive.")
        if self.session_idle_ttl_seconds <= 0 or self.session_idle_ttl_seconds > self.session_ttl_seconds:
            raise ValueError("session_idle_ttl_seconds must be positive and no greater than session_ttl_seconds.")
        if self.session_touch_interval_seconds <= 0 or self.session_touch_interval_seconds >= self.session_idle_ttl_seconds:
            raise ValueError("session_touch_interval_seconds must be positive and less than session_idle_ttl_seconds.")
        if self.login_throttle_window_seconds <= 0:
            raise ValueError("login_throttle_window_seconds must be positive.")
        if self.login_throttle_max_failures <= 0:
            raise ValueError("login_throttle_max_failures must be positive.")
        if self.login_throttle_block_seconds <= 0:
            raise ValueError("login_throttle_block_seconds must be positive.")
        if self.domain_storage_limit_bytes <= 0:
            raise ValueError("domain_storage_limit_bytes must be positive.")
        if self.source_prep_lease_seconds <= 0:
            raise ValueError("source_prep_lease_seconds must be positive.")
        if self.source_parser_timeout_seconds <= 0:
            raise ValueError("source_parser_timeout_seconds must be positive.")
        if self.source_prep_lease_seconds <= self.source_parser_timeout_seconds:
            raise ValueError("source_prep_lease_seconds must exceed source_parser_timeout_seconds.")
        if self.source_index_lease_seconds <= 0:
            raise ValueError("source_index_lease_seconds must be positive.")
        if self.source_index_timeout_seconds <= 0:
            raise ValueError("source_index_timeout_seconds must be positive.")
        if self.source_index_lease_seconds <= self.source_index_timeout_seconds:
            raise ValueError("source_index_lease_seconds must exceed source_index_timeout_seconds.")
        if self.source_index_poll_backoff_seconds <= 0:
            raise ValueError("source_index_poll_backoff_seconds must be positive.")
        if self.source_index_poll_backoff_seconds >= self.source_index_lease_seconds:
            raise ValueError("source_index_poll_backoff_seconds must be less than source_index_lease_seconds.")
        if self.retrieval_timeout_seconds <= 0:
            raise ValueError("retrieval_timeout_seconds must be positive.")
        if self.retrieval_global_concurrency <= 0:
            raise ValueError("retrieval_global_concurrency must be positive.")
        if self.retrieval_per_domain_concurrency <= 0:
            raise ValueError("retrieval_per_domain_concurrency must be positive.")
        if self.retrieval_max_candidates <= 0 or self.retrieval_max_candidates > 10:
            raise ValueError("retrieval_max_candidates must be between 1 and 10.")
        if self.retrieval_max_candidate_bytes <= 0:
            raise ValueError("retrieval_max_candidate_bytes must be positive.")
        if self.retrieval_max_aggregate_bytes < self.retrieval_max_candidate_bytes:
            raise ValueError("retrieval_max_aggregate_bytes must cover at least one candidate.")
        if self.synthesis_timeout_seconds <= 0:
            raise ValueError("synthesis_timeout_seconds must be positive.")
        if self.synthesis_max_output_tokens <= 0:
            raise ValueError("synthesis_max_output_tokens must be positive.")
        if self.turn_lease_seconds <= 0:
            raise ValueError("turn_lease_seconds must be positive.")
        if self.turn_lease_seconds <= self.synthesis_timeout_seconds:
            raise ValueError("turn_lease_seconds must exceed synthesis_timeout_seconds.")
        if self.turn_tail_poll_milliseconds <= 0:
            raise ValueError("turn_tail_poll_milliseconds must be positive.")
        if self.turn_tail_idle_seconds <= 0:
            raise ValueError("turn_tail_idle_seconds must be positive.")

    def inline_turn_workers_enabled(self) -> bool:
        """API may inline turn workers only under testing with the inline flag on."""
        if not self.testing:
            return False
        if self.inline_turn_workers is None:
            return True
        return bool(self.inline_turn_workers)

    @classmethod
    def from_env(cls) -> Settings:
        return cls()
