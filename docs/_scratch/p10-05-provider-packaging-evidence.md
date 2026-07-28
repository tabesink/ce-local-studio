# P10-05 Production Parser and Provider Pipeline Evidence

Date: 2026-07-28

Owner: P10-05

Status: DONE at packaging / fixture / gated-staging altitude

Plan: `docs/plans/2026-07-28-012-feat-p10-05-provider-packaging-plan.md`

Inventory: `docs/_scratch/p10-05-provider-packaging-inventory.md`

Matrix: `docs/operations/provider-deployment-profiles.md`

## Delivered

1. **Packaging gates** — `embeddings` extra; Dockerfile additive args
   `CE_STACK_LIVE_IMAGE` / `CE_STACK_PARSERS_IMAGE` / `CE_STACK_OBJECT_STORE_IMAGE`;
   live overlay installs parsers+synthesis+embeddings; default CI stays bare.
2. **Docling killable timeout** — `adapters/parser_runtime.py` spawn+terminate
   wall-clock deadline; wired through `DoclingDocumentParser` default path.
3. **Reducto URL/asset resolve** — private transport resolves `type=url` and
   materializes figure bytes; URLs/job IDs stripped before `PreparedSource`.
4. **Embedding bindings** — closed OpenAI adapter in LightRAG shim from sealed
   `CE_EMBEDDING_*`; Bedrock/Ollama fail-closed; synthetic only with explicit
   `CE_EMBEDDING_ALLOW_SYNTHETIC=1` (written when credential absent).
5. **Staging smoke** — `scripts/provider_staging_smoke.py` refuses without
   `CE_PROVIDER_STAGING_SMOKE=1`; adapters mode network-free; live mode
   credential-gated.
6. **Pipeline proofs** — fixture PDF; multi-block/oversized marker survival;
   marker-free hits discarded; P5-04 remains topology credit.

## Commands / results

```bash
cd app
uv run --extra test pytest \
  tests/test_provider_packaging.py \
  tests/test_parser_runtime.py \
  tests/test_embedding_adapters.py \
  tests/test_lightrag_shim_embeddings.py \
  tests/test_provider_staging_smoke.py \
  tests/test_provider_pipeline_staging.py \
  tests/test_parser_adapters.py \
  -q
```

Focused result: green (2026-07-28). Shim embedding tests also require
`--extra lightrag-runtime --extra embeddings` when run in isolation.

## Kind status (honest)

| Kind | Packaged | Fixture | Live smoke | Full pipeline | Status |
| --- | --- | --- | --- | --- | --- |
| Docling | yes | yes | import/killable; PDF live optional | CI handoff/map yes; Compose live opt-in | packaged / fixture-proven |
| Reducto | yes | URL/asset yes | credential-gated script | same | packaged / fixture-proven |
| OpenAI embedding | yes | yes | credential-gated script | opt-in | packaged / fixture-proven |
| OpenAI synthesis | yes | yes | credential-gated script | n/a (API worker) | packaged / fixture-proven |
| Bedrock embedding/synthesis | no | fail-closed | no | no | fail-closed |
| Ollama embedding/synthesis | no | fail-closed | no | no | fail-closed |

No kind is labeled **production-supported** until an operator records live
smoke revision + artifact digest under the matrix. Catalog presence alone is
not support.

## Non-claims / residuals

| Item | Owner |
| --- | --- |
| Operator-recorded live smoke digests elevating a kind to production-supported | operator / matrix update |
| Combined `live.yml` + `minio.yml` three-file matrix | P12-04 |
| Immutable SBOM/digest pins for parser/provider/runtime images | P12-06 |
| Browser/capacity/failure on real pipeline | P12-07 |
| Bedrock/Ollama production packaging | fail-closed until approved profile + smoke |
| Real Docling PDF corpus characterization beyond fixture altitude | optional live U4/U8 when Docling installed |

## Tracker

- P10-05 → DONE
- P10 phase remains open until P10-06 (governed preview) closes
