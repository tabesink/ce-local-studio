from __future__ import annotations

from io import StringIO
import json
import logging

from context_engine.services.structured_logging import JsonLogFormatter, safe_log


FORBIDDEN_MARKER = "private-password-and-question-marker"


def _logger_with_json_output() -> tuple[logging.Logger, StringIO]:
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("context_engine.test.safe_logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, output


def test_safe_log_emits_only_allowlisted_fields() -> None:
    logger, output = _logger_with_json_output()

    safe_log(
        logger,
        "http_request",
        request_id="request-safe-1",
        actor_kind="member",
        http_method="POST",
        http_route="/api/v1/auth/login",
        http_status=401,
        outcome="failed",
        safe_error_code="invalid_credentials",
        password=FORBIDDEN_MARKER,
        username=FORBIDDEN_MARKER,
        request_body=FORBIDDEN_MARKER,
        exception=FORBIDDEN_MARKER,
    )

    payload = json.loads(output.getvalue())
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "request-safe-1"
    assert payload["http_route"] == "/api/v1/auth/login"
    assert payload["safe_error_code"] == "invalid_credentials"
    assert not ({"password", "username", "request_body", "exception"} & payload.keys())
    assert FORBIDDEN_MARKER not in output.getvalue()


def test_unclassified_log_record_never_uses_raw_message_as_event() -> None:
    logger, output = _logger_with_json_output()

    logger.error(FORBIDDEN_MARKER)

    payload = json.loads(output.getvalue())
    assert payload["event"] == "unclassified"
    assert FORBIDDEN_MARKER not in output.getvalue()
