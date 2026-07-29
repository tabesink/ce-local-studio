# Provider and Parser Deployment Profiles

**Altitude:** operator packaging / evidence matrix for P10-05.  
**Not** a browser-selectable provider UI. Members never choose models or runtimes.

Statuses below are honest labels. `production-supported` requires credential-gated
staging smoke (U4) plus full upload→Evidence proof (U8) for that kind. Packaging
or fixture proof alone never upgrades status.

## Image gates (`app/Dockerfile`)

| Build arg | Extras installed | Owning processes |
| --- | --- | --- |
| (default all `0`) | none beyond base package | default Compose / root CI |
| `CE_STACK_LIVE_IMAGE=1` | `lightrag-runtime`, `embeddings` (+ Docker CLI) | live overlay api/worker + per-domain LightRAG containers |
| `CE_STACK_PARSERS_IMAGE=1` | `parsers`, `synthesis` | live overlay api/worker (prep + chat synthesis) |
| `CE_STACK_OBJECT_STORE_IMAGE=1` | `object-store` | MinIO overlay api/worker |

Live overlay sets `CE_STACK_LIVE_IMAGE` and `CE_STACK_PARSERS_IMAGE`. MinIO overlay
sets `CE_STACK_OBJECT_STORE_IMAGE`. Combined three-file live+MinIO matrix remains
P12-04 residual unless proven separately.

## Parser kinds

| Kind | Packaged | Image when claimed | Network | Credential | Fixture proof | Live smoke | Full pipeline | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Docling | `parsers` (docling) | `CE_STACK_PARSERS_IMAGE` | none (local) | none | yes (sanitized dicts + killable timeout unit) | pending U4 | pending U8 | packaged / fixture-proven |
| Reducto | `parsers` (reductoai, httpx) | `CE_STACK_PARSERS_IMAGE` | egress to Reducto | provider credential | yes (URL resolve + asset materialize unit) | pending U4 | pending U8 | packaged / fixture-proven |

## Embedding kinds (LightRAG runtime)

| Kind | Packaged | Image when claimed | Network | Credential source | Fixture proof | Live smoke | Full pipeline | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | `embeddings` (openai) | `CE_STACK_LIVE_IMAGE` | egress to OpenAI | sealed `CE_EMBEDDING_*` from domain profile | yes (injectable transport) | pending U4 | pending U8 | packaged / fixture-proven |
| Bedrock | none | n/a | AWS egress | sealed profile | fail-closed registry | no | no | fail-closed |
| Ollama | none | n/a | local-only | sealed profile | fail-closed registry | no | no | fail-closed |
| Synthetic | n/a | explicit `CE_EMBEDDING_ALLOW_SYNTHETIC=1` only | none | none | topology lane | not production | not production | non-production only |

## Synthesis kinds (API/worker)

| Kind | Packaged | Image when claimed | Network | Credential | Fixture proof | Live smoke | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | `synthesis` (openai) | `CE_STACK_PARSERS_IMAGE` | egress to OpenAI | runtime provider config | yes | stack smoke may complete without live LLM | packaged / fixture-proven |
| Bedrock | none | n/a | AWS egress | runtime provider config | fail-closed | no | fail-closed |
| Ollama | none | n/a | local-only | runtime provider config | fail-closed | no | fail-closed |

## Graph-extraction capability (domain-sealed LightRAG LLM)

Extraction reuses a synthesis model profile that the closed catalog marks
`supportsGraphExtraction=true`. Provider kind or synthesis role alone is not
enough. New domains bind one immutable extraction-capable profile; the sealed
per-domain runtime receives `CE_EXTRACTION_*` alongside `CE_EMBEDDING_*`.

| Kind | Catalog capability | Runtime seal | Fixture proof | Live smoke | Full pipeline | Status |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI (selected synthesis models) | yes (`gpt-4.1`, `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini`) | sealed `CE_EXTRACTION_*` | deterministic synthetic shim (test-only) | pending U8/U11 release | pending `@release` | packaged / fixture-proven (deterministic); live pending |
| OpenAI nano / Bedrock / Ollama | no / fail-closed | rejected at assign/create/start/index | fail-closed | no | no | unsupported |
| Synthetic | test-only `CE_EXTRACTION_ALLOW_SYNTHETIC=1` | explicit gate | yes | not production | not production | non-production only |

## Object-store altitude (orthogonal)

| Profile | Store | When to claim |
| --- | --- | --- |
| Filesystem | `CE_SOURCE_STORAGE_ROOT` | default CI / default Compose |
| MinIO/S3 | `compose.stack.minio.yml` + `CE_OBJECT_STORE_KIND=s3` | production object-store staging claims only |

Filesystem-only success must not be labeled production object-store proof.

## Staging smoke

```bash
cd app
# Put OPENAI_API_KEY / REDUCTO_API_KEY in gitignored .env.stack.local
# (copy from .env.stack.example). Do not use app/.env. Never commit secrets.
# Host env keys are for these scripts only — not Compose api/worker injection,
# and not a substitute for sealed Settings provider credentials.

# Gate + profile check only (CI)
CE_PROVIDER_STAGING_SMOKE=1 python scripts/provider_staging_smoke.py \
  --mode check --profile docling

# Network-free fixture proofs
CE_PROVIDER_STAGING_SMOKE=1 python scripts/provider_staging_smoke.py \
  --mode adapters --profile matrix

# Live boundary (credentials from .env.stack.local via --env-file; never commit)
CE_PROVIDER_STAGING_SMOKE=1 python scripts/provider_staging_smoke.py \
  --env-file .env.stack.local --mode live --profile openai-embedding

# Live Reducto (REDUCTO_API_KEY in the same env file)
CE_PROVIDER_STAGING_SMOKE=1 python scripts/provider_staging_smoke.py \
  --env-file .env.stack.local --mode live --profile reducto
```

Missing `CE_PROVIDER_STAGING_SMOKE=1` refuses before network. Live OpenAI needs
`OPENAI_API_KEY` (or `CE_OPENAI_API_KEY` if already set). Live Reducto needs
`REDUCTO_API_KEY` (or `CE_REDUCTO_API_KEY`). Missing `--env-file` soft-skips
when the default `.env.stack.local` is absent.

## Support upgrade rules

1. Parser smoke does not imply embedding or synthesis support.
2. Embedding smoke does not imply parser support.
3. Unsmoked Bedrock/Ollama remain fail-closed even if present in the model catalog.
4. Root `scripts/verify.sh` never requires network providers or live credentials.

## Related

- Inventory: `docs/_scratch/p10-05-provider-packaging-inventory.md`
- Compose runbook: `docs/operations/compose-stack-runbook.md`
- Tech stack closed list: `docs/tech-stack.md`
