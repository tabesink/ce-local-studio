from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from context_engine.api.catalog_schemas import authoritative_component_schemas  # noqa: E402
from context_engine.api.sse_schemas import canonical_sse_json_schema  # noqa: E402

PUBLIC_OUTPUT = APP_DIR / "contracts" / "public-dtos.schema.json"
SSE_OUTPUT = APP_DIR / "contracts" / "sse-events.schema.json"
SSE_OPENAPI_OUTPUT = APP_DIR / "contracts" / "sse-events.openapi.json"


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def public_schema() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:context-engine:public-dtos:1.0",
        "title": "Context Engine Public DTO Catalog",
        "$defs": authoritative_component_schemas(ref_template="#/$defs/{model}"),
    }


def sse_schema() -> dict[str, object]:
    schema = canonical_sse_json_schema()
    schema.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:context-engine:sse-events:1.0",
        "title": "Context Engine Canonical Turn Stream Event",
    })
    return schema


def sse_openapi() -> dict[str, object]:
    root = canonical_sse_json_schema(ref_template="#/components/schemas/{model}")
    definitions = root.pop("$defs", {})
    return {
        "openapi": "3.1.0",
        "info": {"title": "Context Engine SSE Types", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": {**definitions, "TurnStreamEvent": root}},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Context Engine public DTO and SSE schemas.")
    parser.add_argument("--public-output", type=Path, default=PUBLIC_OUTPUT)
    parser.add_argument("--sse-output", type=Path, default=SSE_OUTPUT)
    parser.add_argument("--sse-openapi-output", type=Path, default=SSE_OPENAPI_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = {
        args.public_output.resolve(): encoded(public_schema()),
        args.sse_output.resolve(): encoded(sse_schema()),
        args.sse_openapi_output.resolve(): encoded(sse_openapi()),
    }
    stale = False
    for path, content in outputs.items():
        if args.check:
            try:
                current = path.read_bytes()
            except OSError:
                current = None
            if current != content:
                print(f"generated JSON Schema is stale: {path}", file=sys.stderr)
                stale = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
