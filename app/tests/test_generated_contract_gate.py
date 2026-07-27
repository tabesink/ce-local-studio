from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from context_engine.api.contract_app import CANONICAL_API_PREFIX

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "app" / "contracts" / "openapi.json"
GENERATOR = ROOT / "scripts" / "generate_openapi.py"


def test_openapi_generator_check_accepts_committed_artifact() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_openapi_generator_check_rejects_stale_artifact(tmp_path: Path) -> None:
    stale = tmp_path / "openapi.json"
    stale.write_bytes(OPENAPI.read_bytes() + b" ")

    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check", "--output", str(stale)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "generated OpenAPI is stale" in result.stderr


def test_root_gate_runs_generated_contract_snapshot_check() -> None:
    verify = (ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")

    assert 'run_check "generated contract snapshots"' in verify
    assert "scripts/check-generated-contracts.sh" in verify
    assert 'run_check "generated contract snapshot fixtures"' in verify
    assert "scripts/tests/check-generated-contracts.sh" in verify


def test_login_request_uses_generated_openapi_type() -> None:
    auth_types = (ROOT / "app" / "client" / "src" / "types" / "auth.ts").read_text(encoding="utf-8")
    auth_api = (ROOT / "app" / "client" / "src" / "lib" / "api" / "auth.ts").read_text(encoding="utf-8")

    assert 'import type { components } from "@/lib/api/generated/openapi";' in auth_types
    assert 'type LoginRequest = components["schemas"]["LoginRequest"]' in auth_types
    assert 'import type { LoginRequest, SessionUserResponse } from "@/types/auth";' in auth_api
    assert "login(payload: LoginRequest)" in auth_api


def test_capability_request_bodies_use_generated_openapi_types() -> None:
    capability_files = {
        "domains": ROOT / "app" / "client" / "src" / "features" / "domains" / "api.ts",
        "settings": ROOT / "app" / "client" / "src" / "features" / "settings-panel" / "api.ts",
        "chat": ROOT / "app" / "client" / "src" / "features" / "chat-shell" / "api.ts",
    }
    sources = {name: path.read_text(encoding="utf-8") for name, path in capability_files.items()}

    for source in sources.values():
        assert 'import type { components } from "@/lib/api/generated/openapi";' in source

    assert 'type DomainCreateRequest = components["schemas"]["DomainCreateRequest"]' in sources["domains"]
    assert "createDomain(input: DomainCreateRequest)" in sources["domains"]

    for schema_name in (
        "ModelProfileCreateRequest",
        "ProviderCredentialRequest",
        "RuntimeSettingsPatchRequest",
    ):
        assert f'type {schema_name} = components["schemas"]["{schema_name}"]' in sources["settings"]
    assert "patchRuntimeSettings(patch: RuntimeSettingsPatchRequest)" in sources["settings"]
    assert "createModelProfile(input: ModelProfileCreateRequest)" in sources["settings"]

    for schema_name in ("ComposerRefDiscoverRequest", "ConversationTitleRequest", "TurnStreamRequest"):
        assert f'type {schema_name} = components["schemas"]["{schema_name}"]' in sources["chat"]
    assert "discoverComposerRefs(input: ComposerRefDiscoverRequest)" in sources["chat"]
    assert "type TurnStreamInput = TurnStreamRequest &" in sources["chat"]


def test_production_and_generator_share_contract_route_registration() -> None:
    production = (ROOT / "app" / "context_engine" / "app.py").read_text(encoding="utf-8")
    generator = GENERATOR.read_text(encoding="utf-8")

    assert "register_contract_routes(app)" in production
    assert "register_contract_routes(app)" in generator
    assert "api_prefix=" not in production
    assert "api_prefix=" not in generator


def test_registered_route_delta_is_explicit() -> None:
    methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    catalog = (ROOT / "docs" / "contracts" / "http-api-catalog.md").read_text(encoding="utf-8")

    def normalize(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    registered = {
        (method.upper(), normalize(path))
        for path, path_item in document["paths"].items()
        for method in path_item
        if method in methods
    }
    authoritative = {
        (method, normalize(path if path.startswith("/health/") else f"{CANONICAL_API_PREFIX}{path}"))
        for method, path in re.findall(r"`(GET|POST|PUT|PATCH|DELETE) (/[^` ]+)`", catalog)
    }

    assert registered - authoritative == set()
    assert authoritative - registered == set()


def test_registered_path_parameters_are_camel_case() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    catalog = (ROOT / "docs" / "contracts" / "http-api-catalog.md").read_text(encoding="utf-8")
    observed: set[str] = set()
    authoritative_paths = {
        (method, re.sub(r"\{[^}]+\}", "{}", path)): path
        for method, path in re.findall(r"`(GET|POST|PUT|PATCH|DELETE) (/[^` ]+)`", catalog)
    }

    for path, path_item in document["paths"].items():
        placeholders = set(re.findall(r"\{([^}]+)\}", path))
        if not placeholders:
            continue
        assert all(re.fullmatch(r"[a-z][A-Za-z0-9]*", name) for name in placeholders)
        for method, operation in path_item.items():
            if method not in {"get", "put", "post", "delete", "patch"}:
                continue
            parameter_names = {
                parameter["name"]
                for parameter in operation.get("parameters", [])
                if parameter.get("in") == "path"
            }
            assert parameter_names == placeholders
            observed.update(parameter_names)
            relative_path = path.removeprefix(CANONICAL_API_PREFIX)
            normalized = re.sub(r"\{[^}]+\}", "{}", relative_path)
            authoritative_path = authoritative_paths.get((method.upper(), normalized))
            if authoritative_path is not None:
                assert re.findall(r"\{([^}]+)\}", relative_path) == re.findall(
                    r"\{([^}]+)\}", authoritative_path
                )

    assert observed == {
        "conversationId",
        "documentRef",
        "domainId",
        "evidenceRef",
        "id",
        "kind",
        "sourceId",
        "turnId",
    }


def test_conversation_mutation_preconditions_and_list_default_match_catalog() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    paths = document["paths"]

    list_parameters = paths[f"{CANONICAL_API_PREFIX}/conversations"]["get"]["parameters"]
    limit = next(parameter for parameter in list_parameters if parameter["name"] == "limit")
    assert limit["schema"]["default"] == 50

    for method in ("patch", "delete"):
        parameters = paths[f"{CANONICAL_API_PREFIX}/conversations/{{conversationId}}"][method][
            "parameters"
        ]
        if_match = next(parameter for parameter in parameters if parameter["name"] == "If-Match")
        assert if_match["in"] == "header"
        assert if_match["required"] is True
        assert if_match["schema"]["type"] == "string"
        assert "anyOf" not in if_match["schema"]


def test_stateless_evidence_route_uses_authoritative_generated_components() -> None:
    document = json.loads(OPENAPI.read_text(encoding="utf-8"))
    operation = document["paths"][f"{CANONICAL_API_PREFIX}/domains/{{domainId}}/evidence"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RetrievalEvidenceRequestDto"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RetrievalEvidenceResponseDto"
    }
    assert "EvidenceRequest" not in document["components"]["schemas"]
    assert "EvidenceItemResponse" not in document["components"]["schemas"]
    assert "EvidenceResponse" not in document["components"]["schemas"]


def test_uncataloged_lifted_operations_have_no_active_call_sites() -> None:
    active_sources = (
        ROOT / "app" / "context_engine",
        ROOT / "app" / "client" / "src",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for source_root in active_sources
        for path in source_root.rglob("*")
        if path.suffix in {".py", ".ts", ".tsx"}
    )

    for marker in (
        '"/admin/users/{userId}"',
        '"/domains/{domainId}/sources"',
        '"/domains/{domainId}/sources/{sourceId}/preview"',
        '"/evidence-refs/{evidenceRefId}/source"',
        "updateUserDisabled",
        "listMemberSources",
        "fetchSourcePreview",
        "resolveEvidenceSourceRef",
        "set_user_disabled",
        "list_member_sources",
        "read_source_preview",
        "resolve_evidence_source_ref",
    ):
        assert marker not in combined
