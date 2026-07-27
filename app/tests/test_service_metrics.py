from __future__ import annotations

import json
from io import StringIO
import logging

from context_engine.app import create_app
from context_engine.config import Settings
from context_engine.services.metrics import (
    reset_metrics,
    safe_increment,
    snapshot_metrics,
)
from context_engine.services.structured_logging import JsonLogFormatter


def setup_function() -> None:
    reset_metrics()


def test_safe_increment_records_allowlisted_labels() -> None:
    safe_increment(
        "http_request",
        http_method="POST",
        http_route="/api/v1/auth/login",
        outcome="failed",
        actor_kind="public",
        status_class="4xx",
        safe_error_code="invalid_credentials",
    )

    samples = snapshot_metrics()
    assert len(samples) == 1
    assert samples[0].name == "http_request"
    assert samples[0].value == 1
    assert samples[0].labels["http_route"] == "/api/v1/auth/login"
    assert samples[0].labels["safe_error_code"] == "invalid_credentials"


def test_unknown_metric_name_is_dropped() -> None:
    safe_increment("not_a_metric", outcome="succeeded")
    assert snapshot_metrics() == []


def test_identity_bearing_label_keys_are_rejected() -> None:
    safe_increment(
        "worker_operation",
        operation_type="source_preparation",
        outcome="succeeded",
        domain_id="domain-secret",
        request_id="req-secret",
    )
    assert snapshot_metrics() == []


def test_identity_bearing_label_values_are_rejected() -> None:
    safe_increment(
        "http_request",
        http_method="GET",
        http_route="/api/v1/conversations/conv_abc12345deadbeef/turns",
        outcome="succeeded",
        actor_kind="member",
        status_class="2xx",
    )
    assert snapshot_metrics() == []


def test_best_effort_failure_does_not_raise_and_logs_outage() -> None:
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    metrics_logger = logging.getLogger("context_engine.services.metrics")
    metrics_logger.handlers = [handler]
    metrics_logger.propagate = False
    metrics_logger.setLevel(logging.INFO)

    class BoomRegistry:
        def increment(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("PRIVATE-STACK-SENTINEL-metrics-boom")

    import context_engine.services.metrics as metrics_module

    original = metrics_module._REGISTRY
    metrics_module._REGISTRY = BoomRegistry()  # type: ignore[assignment]
    try:
        safe_increment(
            "http_request",
            http_method="GET",
            http_route="/api/v1/health/live",
            outcome="succeeded",
            actor_kind="public",
            status_class="2xx",
        )
    finally:
        metrics_module._REGISTRY = original

    payload = json.loads(output.getvalue())
    assert payload["event"] == "metrics.outage"
    assert payload["safe_error_code"] == "metrics_unavailable"
    assert "PRIVATE-STACK-SENTINEL" not in output.getvalue()
    assert "Traceback" not in output.getvalue()


def test_no_metrics_scrape_routes_registered(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'metrics-routes.db'}",
        testing=True,
    )
    app = create_app(settings)
    paths = {getattr(route, "path", None) for route in app.routes}
    forbidden = {"/metrics", "/metrics/", "/prometheus", "/prometheus/"}
    assert paths.isdisjoint(forbidden)
