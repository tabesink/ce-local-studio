"""P12-07 U8: immutable graph-extraction binding, latch, private shim graph contract."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from context_engine.config import Settings
from context_engine.models import (
    DOMAIN_STATE_STOPPED,
    PARSER_DOCLING,
    PROFILE_EMBEDDING,
    PROFILE_SYNTHESIS,
    PROVIDER_OPENAI,
    Domain,
    ModelProfile,
    ProviderConfig,
    RuntimeSettings,
)
from context_engine.services.audit import AuditContext
from context_engine.services.domains import DomainError, assign_graph_extraction_profile
from context_engine.services.runtime_config import (
    DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
    RuntimeConfigError,
    SecretCrypto,
    TrustedRuntimeResolver,
    delete_model_profile,
    safe_model_profile,
    update_model_profile,
)
from test_runtime_config_service import RecordingSession


def test_catalog_projects_supports_graph_extraction() -> None:
    from context_engine.services.runtime_config import MODEL_CATALOG

    by_id = {entry.seed_id: entry for entry in MODEL_CATALOG}
    assert by_id["openai-synthesis-default"].supports_graph_extraction is True
    assert by_id["openai-gpt-4-1-nano"].supports_graph_extraction is False
    assert by_id["openai-embedding-default"].supports_graph_extraction is False


def test_resolve_extraction_profile_rejects_unsupported_and_wrong_kind() -> None:
    session = RecordingSession()
    crypto = SecretCrypto(Fernet.generate_key().decode("utf-8"))
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            credential_ciphertext=crypto.encrypt_secret("sk-test"),
        )
    )
    session.add(
        ModelProfile(
            id="openai-gpt-4-1-nano",
            name="OpenAI GPT-4.1 Nano",
            profile_kind=PROFILE_SYNTHESIS,
            provider_kind=PROVIDER_OPENAI,
            model_name="gpt-4.1-nano",
            vector_dimensions=None,
        )
    )
    session.add(
        ModelProfile(
            id="openai-embedding-default",
            name="OpenAI Default Embedding",
            profile_kind=PROFILE_EMBEDDING,
            provider_kind=PROVIDER_OPENAI,
            model_name="text-embedding-3-small",
            vector_dimensions=1536,
        )
    )
    resolver = TrustedRuntimeResolver(session, crypto)

    with pytest.raises(RuntimeConfigError) as unsupported:
        resolver.resolve_extraction_profile("openai-gpt-4-1-nano")
    assert unsupported.value.code == "graph_extraction_profile_unsupported"

    with pytest.raises(RuntimeConfigError) as wrong_kind:
        resolver.resolve_extraction_profile("openai-embedding-default")
    assert wrong_kind.value.code == "graph_extraction_profile_invalid"


def test_extraction_bound_synthesis_profile_reports_in_use_and_rejects_mutation() -> None:
    session = RecordingSession()
    profile = ModelProfile(
        id="openai-gpt-4o",
        name="OpenAI GPT-4o",
        profile_kind=PROFILE_SYNTHESIS,
        provider_kind=PROVIDER_OPENAI,
        model_name="gpt-4o",
        vector_dimensions=None,
        version=1,
    )
    session.add(profile)
    session.add(
        Domain(
            id="domain_manuals",
            display_name="Equipment Manuals",
            state=DOMAIN_STATE_STOPPED,
            embedding_profile_id="openai-embedding-default",
            graph_extraction_profile_id=profile.id,
            runtime_instance_id="runtime-1",
            control_generation=1,
        )
    )
    session.add(RuntimeSettings(id=1, active_parser_kind=PARSER_DOCLING))

    projected = safe_model_profile(session, profile)
    assert projected["supportsGraphExtraction"] is True
    assert projected["inUse"] is True

    with pytest.raises(RuntimeConfigError) as exc_info:
        update_model_profile(
            session,
            profile.id,
            {"name": "Renamed"},
            expected_version=1,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert exc_info.value.code == "model_profile_in_use"
    assert session.commit_count == 0

    with pytest.raises(RuntimeConfigError) as delete_info:
        delete_model_profile(
            session,
            profile.id,
            audit_context=AuditContext(actor_kind="administrator"),
        )
    assert delete_info.value.code == "model_profile_in_use"


def test_assign_graph_extraction_rejects_when_indexing_ever_started() -> None:
    session = RecordingSession()
    settings = Settings(testing=True)
    crypto = SecretCrypto.from_settings(settings)
    session.add(
        ProviderConfig(
            provider_kind=PROVIDER_OPENAI,
            display_name="OpenAI",
            requires_credentials=True,
            credential_ciphertext=crypto.encrypt_secret("sk-test"),
        )
    )
    session.add(
        ModelProfile(
            id=DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
            name="OpenAI Default Synthesis",
            profile_kind=PROFILE_SYNTHESIS,
            provider_kind=PROVIDER_OPENAI,
            model_name="gpt-4.1-mini",
            vector_dimensions=None,
        )
    )
    domain = Domain(
        id="legacy-domain",
        display_name="Legacy",
        state=DOMAIN_STATE_STOPPED,
        embedding_profile_id="openai-embedding-default",
        graph_extraction_profile_id=None,
        indexing_ever_started=True,
        runtime_instance_id=str(uuid4()),
        control_generation=1,
        version=1,
        created_at=datetime(2026, 7, 28, 12, 0, 0),
        updated_at=datetime(2026, 7, 28, 12, 0, 0),
    )
    session.add(domain)

    with pytest.raises(DomainError) as exc_info:
        assign_graph_extraction_profile(
            session,
            settings=settings,
            domain_id=domain.id,
            graph_extraction_profile_id=DEFAULT_GRAPH_EXTRACTION_PROFILE_ID,
            expected_version=1,
        )
    assert exc_info.value.code == "graph_extraction_assignment_ineligible"


def test_shim_private_graph_snapshot_and_labels_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("CE_EMBEDDING_ALLOW_SYNTHETIC", "1")
    monkeypatch.setenv("CE_EMBEDDING_DIMENSIONS", "4")
    monkeypatch.setenv("CE_EXTRACTION_ALLOW_SYNTHETIC", "1")
    monkeypatch.setenv("CE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("WORKING_DIR", str(tmp_path / "runtime" / "lightrag"))

    import hashlib
    import sys
    import types

    import context_engine.tools.ce_lightrag_shim as shim

    captured: dict[str, object] = {}

    class _FakeDocStatus:
        async def get_by_id(self, _request_id):
            return {"status": "processed"}

    class _FakeLightRAG:
        def __init__(self, **kwargs) -> None:
            captured["llm"] = kwargs["llm_model_func"]
            self.doc_status = _FakeDocStatus()

        async def initialize_storages(self) -> None:
            return None

        async def ainsert(self, text, ids=None, file_paths=None, track_id=None):
            captured["inserted"] = text
            return ids

        async def adelete_by_doc_id(self, _request_id) -> None:
            return None

        async def get_graph_labels(self):
            return ["Pump", "Relief Valve"]

    fake_lightrag = types.ModuleType("lightrag")
    fake_lightrag.LightRAG = _FakeLightRAG
    fake_utils = types.ModuleType("lightrag.utils")
    fake_utils.Tokenizer = lambda *a, **k: None
    fake_utils.wrap_embedding_func_with_attrs = lambda **attrs: (lambda fn: fn)
    monkeypatch.setitem(sys.modules, "lightrag", fake_lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", fake_utils)
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.ensure_vendored_lightrag_import_path",
        lambda: None,
    )
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.assert_vendored_lightrag_loaded",
        lambda _mod: None,
    )

    app = shim.create_app()
    llm = captured["llm"]
    assert llm is not None
    extraction = asyncio.run(llm("The relief valve is downstream of the pump."))  # type: ignore[misc]
    assert "Pump" in extraction
    assert "Relief Valve" in extraction
    assert extraction.strip() != "entity"

    client = TestClient(app)
    content = "The relief valve is downstream of the pump."
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    submitted = client.post(
        "/v1/index/submit",
        json={
            "request_id": "src-1-gen-1-abcdef0123456789",
            "content_hash": digest,
            "rendered_text": content,
            "corpus_generation": 3,
        },
    )
    assert submitted.status_code == 200

    snapshot = client.get("/v1/graph/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["appliedGeneration"] == 3
    labels = {node["label"] for node in body["nodes"]}
    assert "Pump" in labels
    assert "Relief Valve" in labels
    assert any(edge.get("label") == "downstream_of" for edge in body["edges"])

    search = client.get("/v1/graph/labels", params={"q": "relief", "limit": 10})
    assert search.status_code == 200
    assert any(item["label"] == "Relief Valve" for item in search.json()["items"])


def test_shim_requires_extraction_binding(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("CE_EMBEDDING_ALLOW_SYNTHETIC", "1")
    monkeypatch.setenv("CE_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.delenv("CE_EXTRACTION_ALLOW_SYNTHETIC", raising=False)
    monkeypatch.delenv("CE_EXTRACTION_PROVIDER_KIND", raising=False)
    monkeypatch.delenv("CE_EXTRACTION_MODEL_NAME", raising=False)
    monkeypatch.delenv("CE_EXTRACTION_CREDENTIAL", raising=False)
    monkeypatch.setenv("CE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("WORKING_DIR", str(tmp_path / "runtime" / "lightrag"))

    import sys
    import types

    import context_engine.tools.ce_lightrag_shim as shim

    fake_lightrag = types.ModuleType("lightrag")
    fake_lightrag.LightRAG = lambda **kwargs: None
    fake_utils = types.ModuleType("lightrag.utils")
    fake_utils.Tokenizer = lambda *a, **k: None
    fake_utils.wrap_embedding_func_with_attrs = lambda **attrs: (lambda fn: fn)
    monkeypatch.setitem(sys.modules, "lightrag", fake_lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.utils", fake_utils)
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.ensure_vendored_lightrag_import_path",
        lambda: None,
    )
    monkeypatch.setattr(
        "context_engine.services.lightrag_runtime.assert_vendored_lightrag_loaded",
        lambda _mod: None,
    )

    with pytest.raises(RuntimeError, match="Graph extraction provider is not configured"):
        shim.create_app()
