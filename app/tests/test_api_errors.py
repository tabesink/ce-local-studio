from fastapi import Request

from context_engine.api.errors import error_body


def _request_with_id(request_id: str) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.request_id = request_id
    return request


def test_error_body_always_uses_closed_fields_record() -> None:
    body = error_body(_request_with_id("req_123"), "validation_error", "Request validation failed.")

    assert body == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
            "requestId": "req_123",
            "fields": {},
        }
    }


def test_error_body_projects_only_string_field_messages() -> None:
    body = error_body(
        _request_with_id("req_123"),
        "validation_error",
        "Request validation failed.",
        {"username": "Invalid value.", "password": "Invalid value."},
    )

    assert body["error"]["fields"] == {"username": "Invalid value.", "password": "Invalid value."}
