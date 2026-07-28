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

## Object-store altitude (orthogonal)

| Profile | Store | When to claim |
| --- | --- | --- |
| Filesystem | `CE_SOURCE_STORAGE_ROOT` | default CI / default Compose |
| MinIO/S3 | `compose.stack.minio.yml` + `CE_OBJECT_STORE_KIND=s3` | production object-store staging claims only |

Filesystem-only success must not be labeled production object-store proof.

## Support upgrade rules

1. Parser smoke does not imply embedding or synthesis support.
2. Embedding smoke does not imply parser support.
3. Unsmoked Bedrock/Ollama remain fail-closed even if present in the model catalog.
4. Root `scripts/verify.sh` never requires network providers or live credentials.

## Related

- Inventory: `docs/_scratch/p10-05-provider-packaging-inventory.md`
- Compose runbook: `docs/operations/compose-stack-runbook.md`
- Tech stack closed list: `docs/tech-stack.md`
