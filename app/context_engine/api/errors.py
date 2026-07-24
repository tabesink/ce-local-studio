from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, fields: Mapping[str, str] | None = None, headers: Mapping[str, str] | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields
        self.headers = headers
        super().__init__(message)


def request_id_from(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_body(request: Request, code: str, message: str, fields: Mapping[str, str] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id_from(request),
            "fields": dict(fields or {}),
        }
    }
    return body


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    fields: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    response_headers = {"Cache-Control": "private, no-store, no-transform"}
    response_headers.update(headers or {})
    return JSONResponse(
        status_code=status_code,
        content=error_body(request, code, message, fields),
        headers=response_headers,
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(request, exc.status_code, exc.code, exc.message, exc.fields, exc.headers)


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 401:
        return error_response(request, 401, "unauthenticated", "Authentication required.")
    if exc.status_code == 403:
        return error_response(request, 403, "forbidden", "Forbidden.")
    if exc.status_code == 404:
        return error_response(request, 404, "not_found", "Not found.")
    return error_response(request, exc.status_code, "http_error", "Request failed.")


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", [])]
        field_name = location[-1] if location else "request"
        fields[field_name] = "Invalid value."
    return error_response(request, 422, "validation_error", "Request validation failed.", fields)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(request, 500, "internal_error", "Internal server error.")
