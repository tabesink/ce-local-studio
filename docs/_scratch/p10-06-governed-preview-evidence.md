# P10-06 Governed Preview Generation — Evidence

Date: 2026-07-28

Branch: `feat/p10-06-governed-preview`

Plan: `docs/plans/2026-07-28-017-feat-p10-06-governed-preview-generation-plan.md`

Inventory: `docs/_scratch/p10-06-governed-preview-inventory.md`

## Verdict

**DONE** for Phase-1 governed PDF preview generation of approved formats
(PDF pass-through, Markdown, plain text, DOCX via `preview-renderer` extra),
with generation-fenced publication, authorized delivery, anchor remapping, and
idempotent derivative cleanup. Browser still consumes only the closed PDF
content contract. PPT and production LibreOffice-class packaging remain deferred
(P12-06/P12-07).

## Units

| Unit | Status | Proof |
| --- | --- | --- |
| U1 Inventory | DONE | `docs/_scratch/p10-06-governed-preview-inventory.md` |
| U2 Renderer port | DONE | `adapters/preview_renderer.py`; `tests/test_preview_renderer.py` |
| U3 Schema + worker | DONE | migration `d4e7a1b92c80`; `services/preview.py`; `tests/test_preview_service.py` |
| U4 Delivery + anchors | DONE | `documents.py` / `evidence.py` remap; document + remap tests |
| U5 Delete + tracker | DONE | preview keys in `delete_source_files`; this evidence; tracker |

## Supported formats (honest)

| Kind | Fixture altitude | Production-supported label |
| --- | --- | --- |
| `application/pdf` | Pass-through + identity page map | Yes (validated original as preview) |
| `text/markdown` | Deterministic `ce-preview-text-v1` | Yes at fixture/CI altitude |
| `text/plain` | Deterministic `ce-preview-text-v1` | Yes at fixture/CI altitude |
| DOCX | Requires `--extra preview-renderer` (`python-docx`) | Packaged; elevate only after operator live digest (P12-06) |
| PPT / other | Out of scope | No |

## Packaging

- Extra: `preview-renderer` in `app/pyproject.toml`
- Image gate: `CE_STACK_PREVIEW_IMAGE` (default off)
- Alembic head: `d4e7a1b92c80` + schema snapshot

## Verification commands (local)

```bash
cd app
uv run --extra preview-renderer --extra test pytest \
  tests/test_preview_renderer.py \
  tests/test_preview_service.py \
  tests/test_preview_anchor_remap.py \
  tests/test_preview_delete_cleanup.py \
  tests/test_documents_service.py \
  tests/test_documents_http_contract.py \
  tests/test_turn_execution_leases.py -q
```

## Residuals → follow-on

| Residual | Owner |
| --- | --- |
| Renderer/image SBOM pin | P12-06 |
| Backup/restore of preview derivatives | P12-04 |
| Browser E2E governed preview navigation | P12-07 |
| Operator live DOCX digest → production-supported | P12-06 / ops |
| Combined live+minio+preview overlay matrix | P12-04 |

## Privacy

Public DTOs remain closed (`previewKind`, `pageCount`, opaque ETag). Object keys,
renderer versions, page maps, and original non-PDF bytes do not cross the member
content/location boundary.
