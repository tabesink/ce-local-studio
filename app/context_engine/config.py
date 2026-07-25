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
    lightrag_client_kind: str = field(default_factory=lambda: _env("CE_LIGHTRAG_CLIENT_KIND", "native") or "native")
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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
