from __future__ import annotations

import pytest

from context_engine.adapters.synthesis import (
    OpenAISynthesisAdapter,
    SynthesisAdapterError,
    SynthesisEvidenceItem,
    SynthesisRequest,
    UnsupportedSynthesisAdapter,
    default_synthesis_registry,
    resolve_synthesis_adapter,
)
from context_engine.config import Settings
from context_engine.models import PROVIDER_BEDROCK, PROVIDER_OLLAMA, PROVIDER_OPENAI
from context_engine.services.runtime_config import TrustedModelRuntimeConfig


def _request(
    *,
    mode: str = "direct",
    credential: str | None = "sk-test",
    evidence: tuple[SynthesisEvidenceItem, ...] = (),
    timeout_seconds: float = 5.0,
    max_output_tokens: int = 256,
) -> SynthesisRequest:
    return SynthesisRequest(
        mode=mode,  # type: ignore[arg-type]
        message="What is the policy?",
        model_name="gpt-4.1-mini",
        credential=credential,
        prior_user_questions=(),
        evidence=evidence,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


def test_openai_adapter_happy_path_yields_ordered_tokens_without_forbidden_keys() -> None:
    tokens_in = ("Hello ", "world.")

    def transport(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        return iter(tokens_in)

    adapter = OpenAISynthesisAdapter(transport=transport)
    tokens = list(adapter.stream(_request()))
    assert tokens == ["Hello ", "world."]
    joined = "".join(tokens)
    assert "credential" not in joined.lower()
    assert "sk-" not in joined
    assert "https://" not in joined


def test_openai_adapter_timeout_maps_to_typed_safe_error() -> None:
    def boom(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        raise TimeoutError("provider hung; credential=sk-secret https://api.openai.com/v1")

    with pytest.raises(SynthesisAdapterError) as raised:
        list(OpenAISynthesisAdapter(transport=boom).stream(_request()))
    assert raised.value.code == "synthesis_timeout"
    text = f"{raised.value} {raised.value.message}"
    assert "sk-secret" not in text
    assert "https://" not in text
    assert "credential=" not in text


def test_openai_adapter_missing_credential_fails_closed() -> None:
    with pytest.raises(SynthesisAdapterError) as raised:
        list(
            OpenAISynthesisAdapter(transport=lambda _r, _m: iter(("x",))).stream(
                _request(credential=None)
            )
        )
    assert raised.value.code == "synthesis_not_ready"
    assert "sk-" not in raised.value.message


def test_openai_adapter_malformed_stream_and_unexpected_exception_are_safe() -> None:
    def malformed(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        raise SynthesisAdapterError(
            "synthesis_malformed_response",
            "Synthesis response could not be normalized.",
        )

    with pytest.raises(SynthesisAdapterError) as malformed_err:
        list(OpenAISynthesisAdapter(transport=malformed).stream(_request()))
    assert malformed_err.value.code == "synthesis_malformed_response"

    def unexpected(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        raise RuntimeError("boom prompt=SECRET url=https://evil.example/job/1")

    with pytest.raises(SynthesisAdapterError) as unexpected_err:
        list(OpenAISynthesisAdapter(transport=unexpected).stream(_request()))
    assert unexpected_err.value.code == "synthesis_unavailable"
    text = f"{unexpected_err.value} {unexpected_err.value.message}"
    assert "SECRET" not in text
    assert "https://evil.example" not in text


def test_openai_adapter_empty_token_stream_raises_distinguishable_empty_error() -> None:
    def empty(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        return iter(())

    with pytest.raises(SynthesisAdapterError) as raised:
        list(OpenAISynthesisAdapter(transport=empty).stream(_request()))
    assert raised.value.code == "synthesis_empty_output"


def test_unsupported_provider_kinds_fail_closed_never_stand_in_success() -> None:
    for kind in (PROVIDER_BEDROCK, PROVIDER_OLLAMA):
        adapter = resolve_synthesis_adapter(kind, registry=default_synthesis_registry())
        assert isinstance(adapter, UnsupportedSynthesisAdapter)
        with pytest.raises(SynthesisAdapterError) as raised:
            list(adapter.stream(_request()))
        assert raised.value.code == "synthesis_not_ready"
        assert "I can help with that." not in raised.value.message
        assert "supported by the current evidence" not in raised.value.message


def test_privacy_sentinels_in_transport_errors_cannot_leak_into_error_surfaces() -> None:
    sentinel_url = "https://api.openai.invalid/v1/chat/completions"
    sentinel_job = "job_priv_9f3a"
    sentinel_key = "sk-live-PRIVACY-SENTINEL"

    def leaky(_request: SynthesisRequest, _messages: list[dict[str, str]]):
        # Transport may yield ordinary answer text (including URLs in docs).
        # Provider exception text must not escape into typed error messages.
        yield "See https://example.com/policy for the credential rotation steps."
        raise RuntimeError(
            f"upstream failed url={sentinel_url} job_id={sentinel_job} api_key={sentinel_key}"
        )

    with pytest.raises(SynthesisAdapterError) as raised:
        list(OpenAISynthesisAdapter(transport=leaky).stream(_request()))
    assert raised.value.code == "synthesis_unavailable"
    surfaces = f"{raised.value.code} {raised.value.message} {raised.value}"
    assert sentinel_url not in surfaces
    assert sentinel_job not in surfaces
    assert sentinel_key not in surfaces
    assert raised.value.__cause__ is None


def test_settings_require_positive_synthesis_timeout_and_max_output() -> None:
    with pytest.raises(ValueError):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            testing=True,
            synthesis_timeout_seconds=0,
        )
    with pytest.raises(ValueError):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            testing=True,
            synthesis_max_output_tokens=0,
        )


def test_registry_resolves_openai_and_uses_runtime_provider_kind() -> None:
    def transport(request: SynthesisRequest, _messages: list[dict[str, str]]):
        assert request.mode == "grounded"
        assert request.evidence[0].excerpt == "Authorized excerpt."
        assert "blk_" not in request.evidence[0].excerpt
        return iter(("Grounded ", "ok."))

    registry = {
        PROVIDER_OPENAI: OpenAISynthesisAdapter(transport=transport),
        PROVIDER_BEDROCK: UnsupportedSynthesisAdapter(PROVIDER_BEDROCK),
        PROVIDER_OLLAMA: UnsupportedSynthesisAdapter(PROVIDER_OLLAMA),
    }
    adapter = resolve_synthesis_adapter(PROVIDER_OPENAI, registry=registry)
    tokens = list(
        adapter.stream(
            _request(
                mode="grounded",
                evidence=(
                    SynthesisEvidenceItem(
                        citation_label="[1]",
                        source_label="Policy.pdf",
                        excerpt="Authorized excerpt.",
                    ),
                ),
            )
        )
    )
    assert tokens == ["Grounded ", "ok."]

    runtime = TrustedModelRuntimeConfig(
        profile_id="openai-synthesis-default",
        provider_kind=PROVIDER_OPENAI,
        model_name="gpt-4.1-mini",
        credential="sk-test",
    )
    assert runtime.provider_kind == PROVIDER_OPENAI
