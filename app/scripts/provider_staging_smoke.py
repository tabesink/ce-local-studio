#!/usr/bin/env python3
"""P10-05 credential-gated parser/provider staging smoke.

Never wired into scripts/verify.sh. Refuses before network unless
CE_PROVIDER_STAGING_SMOKE=1 and the selected profile's credentials are present.
Optional --env-file (default app/.env.stack.local) merges OPENAI_API_KEY /
REDUCTO_API_KEY (and CE_* aliases) into process env; missing file soft-skips.

Modes:
  check     — validate gate/profile/env only (CI refuse proof)
  adapters  — fixture-altitude typed adapter proofs (no live provider network)
  live      — real Docling/Reducto/OpenAI boundary for the selected profile

Object-store altitude is recorded (filesystem vs s3) but not claimed as
production-store proof unless CE_OBJECT_STORE_KIND=s3.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

GATE_ENV = "CE_PROVIDER_STAGING_SMOKE"
_DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.stack.local"
_SECRET_ENV_KEYS = frozenset(
    {
        "OPENAI_API_KEY",
        "CE_OPENAI_API_KEY",
        "REDUCTO_API_KEY",
        "CE_REDUCTO_API_KEY",
    }
)
PROFILES = frozenset(
    {
        "docling",
        "reducto",
        "openai-embedding",
        "openai-synthesis",
        "matrix",
    }
)
CLOSED_ERRORS = frozenset(
    {
        "gate_refused",
        "profile_refused",
        "credential_refused",
        "adapter_failed",
        "live_failed",
    }
)


def _fail(code: str, message: str, exit_code: int = 1) -> int:
    if code not in CLOSED_ERRORS:
        code = "adapter_failed"
    print(f"FAIL: {code}: {message}", file=sys.stderr)
    return exit_code


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def require_gate() -> str | None:
    if not _truthy(os.environ.get(GATE_ENV)):
        return f"set {GATE_ENV}=1 to allow provider staging smoke"
    return None


def require_profile(profile: str) -> str | None:
    if profile not in PROFILES:
        return f"profile must be one of: {', '.join(sorted(PROFILES))}"
    return None


def _object_store_kind() -> str:
    kind = (os.environ.get("CE_OBJECT_STORE_KIND") or "filesystem").strip().lower()
    return kind if kind in {"filesystem", "s3"} else "filesystem"


def _credential_for_profile(profile: str) -> tuple[str | None, str | None]:
    """Return (env_name, value) or (None, None) when no credential required."""
    if profile == "docling":
        return None, None
    if profile == "reducto":
        for key in ("CE_REDUCTO_API_KEY", "REDUCTO_API_KEY"):
            value = os.environ.get(key)
            if value:
                return key, value
        return "CE_REDUCTO_API_KEY", None
    if profile in {"openai-embedding", "openai-synthesis"}:
        for key in ("CE_OPENAI_API_KEY", "OPENAI_API_KEY"):
            value = os.environ.get(key)
            if value:
                return key, value
        return "CE_OPENAI_API_KEY", None
    if profile == "matrix":
        return "CE_OPENAI_API_KEY", os.environ.get("CE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    return "credential", None


def require_live_credentials(profile: str) -> str | None:
    if profile == "docling":
        return None
    if profile == "matrix":
        # Matrix live requires at least one parser path; Reducto optional.
        # OpenAI credential required for embedding/synthesis legs.
        _name, value = _credential_for_profile("openai-embedding")
        if not value:
            return "CE_OPENAI_API_KEY or OPENAI_API_KEY is required for matrix live"
        return None
    name, value = _credential_for_profile(profile)
    if name and not value:
        return f"{name} is required for profile={profile}"
    return None


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _merge_env_file(env: dict[str, str]) -> None:
    """Merge allowlisted keys into os.environ without logging values."""
    for key, value in env.items():
        if not value or value == "<set locally>":
            continue
        if key in _SECRET_ENV_KEYS:
            if key not in os.environ:
                os.environ[key] = value
            continue
        os.environ.setdefault(key, value)


def _maybe_merge_env_file(path: Path) -> None:
    """Soft-skip when missing (unlike SSE proof hard-fail)."""
    if not path.is_file():
        return
    _merge_env_file(_load_env_file(path))


def run_adapters_fixture_proofs(profile: str) -> dict[str, Any]:
    """Network-free typed proofs using fixtures / injectable transports."""
    from context_engine.adapters.embeddings import (
        EmbeddingRequest,
        OpenAIEmbeddingAdapter,
        resolve_embedding_adapter,
    )
    from context_engine.adapters.parser_runtime import resolve_reducto_url_result
    from context_engine.adapters.parsers import (
        PARSER_DOCLING,
        PARSER_REDUCTO,
        DoclingDocumentParser,
        ParserRequest,
        dump_prepared_source_for_privacy_scan,
        normalize_reducto_parse_response,
        validate_prepared_source,
    )
    from context_engine.adapters.synthesis import (
        SynthesisRequest,
        default_synthesis_registry,
    )
    from context_engine.models import PROVIDER_BEDROCK, PROVIDER_OLLAMA, PROVIDER_OPENAI

    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "parsers"
    results: dict[str, Any] = {"profile": profile, "proofs": []}

    if profile in {"docling", "matrix"}:
        payload = json.loads((fixtures / "docling_export_dict.json").read_text(encoding="utf-8"))
        prepared = DoclingDocumentParser(convert=lambda *_a, **_k: payload).parse(
            ParserRequest(
                source_document_id="smoke-docling",
                parser_kind=PARSER_DOCLING,
                original_bytes=b"%PDF-1.4",
                filename="smoke.pdf",
            )
        )
        validate_prepared_source(prepared)
        scanned = dump_prepared_source_for_privacy_scan(prepared)
        assert "self_ref" not in scanned
        results["proofs"].append({"kind": "docling", "blocks": len(prepared.blocks)})

    if profile in {"reducto", "matrix"}:
        pointer = json.loads((fixtures / "reducto_url_pointer.json").read_text(encoding="utf-8"))
        resolved_body = json.loads((fixtures / "reducto_url_resolved_body.json").read_text(encoding="utf-8"))

        def _fake_get_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
            del timeout_seconds
            if "presigned" not in url:
                raise AssertionError("unexpected url")
            return resolved_body

        import context_engine.adapters.parser_runtime as runtime

        original = runtime._httpx_get_json
        runtime._httpx_get_json = _fake_get_json  # type: ignore[method-assign]
        try:
            resolved = resolve_reducto_url_result(pointer, timeout_seconds=5.0)
        finally:
            runtime._httpx_get_json = original  # type: ignore[method-assign]
        prepared = normalize_reducto_parse_response("smoke-reducto", PARSER_REDUCTO, resolved)
        validate_prepared_source(prepared)
        scanned = dump_prepared_source_for_privacy_scan(prepared)
        assert "example.invalid" not in scanned
        assert "job-secret" not in scanned
        results["proofs"].append({"kind": "reducto", "blocks": len(prepared.blocks)})

    if profile in {"openai-embedding", "matrix"}:
        adapter = OpenAIEmbeddingAdapter(
            transport=lambda req: [[0.0] * req.dimensions for _ in req.texts]
        )
        vectors = adapter.embed(
            EmbeddingRequest(
                texts=("smoke",),
                model_name="text-embedding-3-small",
                dimensions=8,
                credential="sk-fixture",
            )
        )
        assert len(vectors[0]) == 8
        for kind in (PROVIDER_BEDROCK, PROVIDER_OLLAMA):
            try:
                resolve_embedding_adapter(kind).embed(
                    EmbeddingRequest(
                        texts=("x",),
                        model_name="m",
                        dimensions=8,
                        credential="x",
                    )
                )
                raise AssertionError(f"{kind} must fail closed")
            except Exception as exc:
                assert getattr(exc, "code", "") == "embedding_not_ready"
        results["proofs"].append({"kind": "openai-embedding", "dimensions": 8})

    if profile in {"openai-synthesis", "matrix"}:
        registry = default_synthesis_registry(
            transport=lambda _req, _messages: iter(("ok",))
        )
        assert PROVIDER_OPENAI in registry
        for kind in (PROVIDER_BEDROCK, PROVIDER_OLLAMA):
            try:
                list(
                    registry[kind].stream(
                        SynthesisRequest(
                            mode="direct",
                            message="hi",
                            model_name="m",
                            credential="x",
                        )
                    )
                )
                raise AssertionError(f"{kind} must fail closed")
            except Exception as exc:
                assert getattr(exc, "code", "") == "synthesis_not_ready"
        results["proofs"].append({"kind": "openai-synthesis", "tokens": 1})

    return results


def run_live_profile(profile: str) -> dict[str, Any]:
    """Live boundary smoke for one profile. Never prints credentials."""
    started = time.time()
    out: dict[str, Any] = {"profile": profile, "live": True, "proofs": []}

    if profile in {"docling", "matrix"}:
        from context_engine.adapters.parsers import (
            PARSER_DOCLING,
            DoclingDocumentParser,
            ParserRequest,
            validate_prepared_source,
        )

        sample = (
            Path(__file__).resolve().parents[1]
            / "tests"
            / "fixtures"
            / "parsers"
            / "docling_export_dict.json"
        )
        # Prefer a tiny PDF if present under fixtures/documents; else exercise killable path
        # with the default converter on a minimal PDF header (may fail closed if Docling
        # rejects it — that still proves packaging/timeout mapping).
        pdf_candidates = list(
            (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "documents").glob("*.pdf")
        ) if (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "documents").is_dir() else []
        if pdf_candidates:
            raw = pdf_candidates[0].read_bytes()
            prepared = DoclingDocumentParser(timeout_seconds=60.0).parse(
                ParserRequest(
                    source_document_id="live-docling",
                    parser_kind=PARSER_DOCLING,
                    original_bytes=raw,
                    content_type="application/pdf",
                    filename=pdf_candidates[0].name,
                )
            )
            validate_prepared_source(prepared)
            out["proofs"].append({"kind": "docling", "blocks": len(prepared.blocks), "source": "pdf"})
        else:
            # Packaging import + killable path smoke without a corpus PDF.
            DoclingDocumentParser(timeout_seconds=5.0)
            out["proofs"].append(
                {
                    "kind": "docling",
                    "source": "import-only",
                    "note": "no fixtures/documents/*.pdf; full live PDF deferred to U8",
                    "fixture": str(sample.name),
                }
            )

    if profile == "reducto":
        from context_engine.adapters.parsers import (
            PARSER_REDUCTO,
            ReductoDocumentParser,
            ParserRequest,
            validate_prepared_source,
        )

        _name, credential = _credential_for_profile("reducto")
        assert credential
        sample_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        prepared = ReductoDocumentParser(timeout_seconds=60.0).parse(
            ParserRequest(
                source_document_id="live-reducto",
                parser_kind=PARSER_REDUCTO,
                original_bytes=sample_pdf,
                content_type="application/pdf",
                filename="smoke.pdf",
                credential=credential,
            )
        )
        validate_prepared_source(prepared)
        out["proofs"].append({"kind": "reducto", "blocks": len(prepared.blocks)})

    if profile in {"openai-embedding", "matrix"}:
        from context_engine.adapters.embeddings import EmbeddingRequest, OpenAIEmbeddingAdapter

        _name, credential = _credential_for_profile("openai-embedding")
        assert credential
        vectors = OpenAIEmbeddingAdapter().embed(
            EmbeddingRequest(
                texts=("Context Engine staging smoke",),
                model_name=os.environ.get("CE_EMBEDDING_MODEL_NAME", "text-embedding-3-small"),
                dimensions=int(os.environ.get("CE_EMBEDDING_DIMENSIONS", "1536")),
                credential=credential,
                timeout_seconds=60.0,
            )
        )
        out["proofs"].append(
            {
                "kind": "openai-embedding",
                "dimensions": len(vectors[0]),
                "count": len(vectors),
            }
        )

    if profile in {"openai-synthesis", "matrix"}:
        from context_engine.adapters.synthesis import (
            SynthesisRequest,
            resolve_synthesis_adapter,
        )
        from context_engine.models import PROVIDER_OPENAI

        _name, credential = _credential_for_profile("openai-synthesis")
        assert credential
        adapter = resolve_synthesis_adapter(PROVIDER_OPENAI)
        tokens = list(
            adapter.stream(
                SynthesisRequest(
                    mode="direct",
                    message="Reply with the single word: ok",
                    model_name=os.environ.get("CE_SYNTHESIS_MODEL_NAME", "gpt-4o-mini"),
                    credential=credential,
                    timeout_seconds=60.0,
                )
            )
        )
        joined = "".join(tokens)
        out["proofs"].append(
            {
                "kind": "openai-synthesis",
                "token_count": len(tokens),
                "non_empty": bool(joined.strip()),
            }
        )

    out["elapsed_ms"] = int((time.time() - started) * 1000)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("check", "adapters", "live"),
        default="check",
        help="check=gate only; adapters=fixture proofs; live=real provider calls",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("CE_PROVIDER_STAGING_PROFILE", ""),
        help="docling|reducto|openai-embedding|openai-synthesis|matrix",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_DEFAULT_ENV_FILE,
        help="Optional gitignored stack env file (default: app/.env.stack.local). "
        "Missing file soft-skips; never prints secret values.",
    )
    args = parser.parse_args(argv)

    # Merge host credentials before live gate (process env wins if already set).
    _maybe_merge_env_file(args.env_file)

    gate_err = require_gate()
    if gate_err:
        return _fail("gate_refused", gate_err)

    profile = (args.profile or "").strip().lower()
    profile_err = require_profile(profile)
    if profile_err:
        return _fail("profile_refused", profile_err)

    store_kind = _object_store_kind()
    base_meta = {
        "gate": GATE_ENV,
        "mode": args.mode,
        "profile": profile,
        "objectStoreKind": store_kind,
        "productionObjectStoreClaim": store_kind == "s3",
    }

    if args.mode == "check":
        return _ok({**base_meta, "status": "gate_ok"})

    if args.mode == "live":
        cred_err = require_live_credentials(profile)
        if cred_err:
            return _fail("credential_refused", cred_err)
        try:
            result = run_live_profile(profile)
        except Exception as exc:  # noqa: BLE001 - closed CLI boundary
            return _fail("live_failed", f"{type(exc).__name__}: boundary failed")
        return _ok({**base_meta, "status": "live_ok", **result})

    # adapters
    try:
        result = run_adapters_fixture_proofs(profile)
    except Exception as exc:  # noqa: BLE001
        return _fail("adapter_failed", f"{type(exc).__name__}: fixture proof failed")
    return _ok({**base_meta, "status": "adapters_ok", **result})


if __name__ == "__main__":
    raise SystemExit(main())
