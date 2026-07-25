from __future__ import annotations

from fastapi import FastAPI

from context_engine.api.catalog_schemas import authoritative_component_schemas
from context_engine.api.routes import api_router, health_router

API_TITLE = "Context Engine API"
API_VERSION = "0.1.0"
CANONICAL_API_PREFIX = "/api/v1"
CANONICAL_REQUEST_ID_HEADER = "X-Request-ID"


def register_contract_routes(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(api_router, prefix=CANONICAL_API_PREFIX)
    _install_authoritative_components(app)


def _install_authoritative_components(app: FastAPI) -> None:
    default_openapi = app.openapi

    def contract_openapi() -> dict[str, object]:
        document = default_openapi()
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        for name, component in authoritative_component_schemas().items():
            # Closed catalog DTOs are authoritative. FastAPI may emit a near-duplicate
            # when the same model is nested under a route response_model (for example
            # omitting an optional property default); the catalog component wins.
            schemas[name] = component
        return document

    app.openapi = contract_openapi
