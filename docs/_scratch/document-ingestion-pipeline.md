# Document ingestion pipeline (Context Engine)

This is the **admin-side path** from “upload a PDF” to “members can retrieve grounded answers from it.” It spans build phases **P4 (prepare)** and **P5 (index)** in `docs/master-build-plan.md`. Retrieval/chat (P6+) consumes the output but is not part of ingestion itself.

**Status note:** Plans are authoritative; code is still largely scaffold. `docs/architecture/as-built-gaps-and-decisions.md` says Docling is a text fallback and Reducto is unimplemented until P4-03 lands.

---

## Mental model (junior-friendly)

| Term | What it means |
|------|----------------|
| **Knowledge Domain** | Isolated corpus + private LightRAG runtime. One domain ≠ one tenant. |
| **Source Document** | One uploaded file in exactly one domain. |
| **Parser** | Converts raw bytes → **Canonical Source** (product-owned shape). |
| **Source Block** | Ordered, citable unit (`text` / `table` / `figure`). Stored in Postgres. |
| **Prepare** | Async job: parse file → replace all blocks atomically. |
| **Index** | Async job: send blocks to LightRAG so retrieval works. |

**Critical rule:** Users never see Docling JSON or Reducto API responses. Parsers are **adapters behind a port**; only Canonical Source Blocks cross the product boundary (`app/CONTEXT.md`).

---

## End-to-end flow (two async stages)

```text
                    INGESTION (P4 + P5)
┌──────────┐     ┌─────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────┐
│ Admin UI │────▶│ FastAPI │────▶│ Postgres │     │ Object store│     │  Worker  │
└──────────┘     └─────────┘     └──────────┘     └─────────────┘     └────┬─────┘
     │                │               │                    │                  │
     │  multipart     │ validate+     │ pending source +   │ raw bytes        │
     │  upload        │ dedupe+hash   │ prepare operation  │ (random key)     │
     │                │               │                    │                  │
     │                │               │◀───────────────────┼──────────────────┤
     │                │               │                    │   claim lease    │
     │                │               │                    │                  ▼
     │                │               │                    │            ┌───────────┐
     │                │               │                    │            │  Parser   │
     │                │               │                    │            │ adapter   │
     │                │               │                    │            │ Docling / │
     │                │               │                    │            │ Reducto   │
     │                │               │                    │            └─────┬─────┘
     │                │               │◀───────────────────┼──────────────────┘
     │                │               │ replace source_blocks + source_images
     │                │               │ state = prepared
     │                │               │                  │
     │  index retry   │               │                  ▼
     │───────────────▶│               │         ┌────────────────┐
     │                │               │         │ LightRAG       │
     │                │               │         │ (per domain)   │
     │                │               │         └────────────────┘
     │                │               │ index_state = ready → query-eligible
```

**Lifecycle states** (`docs/architecture/data-and-lifecycle.md`):

```text
upload ──▶ pending ──▶ [prepare op] ──▶ prepared
                                          │
                    domain running + index op
                                          ▼
                              queued → processing → ready
                                    ↘ failed / cancelled
```

A source is **not searchable** until `prepared` **and** `index_state = ready` **and** its domain is **running + runtime-ready** (A-08).

---

## Stage 1: Upload (synchronous API, async work)

**Who:** Admin via `POST /admin/domains/{domainId}/sources`  
**What happens** (`docs/prd.md` FR-04, case A-06):

1. Browser sends **only** the file — no parser choice, no storage path, no hash from client.
2. API **streams** bytes with size limits, sniffs MIME, rejects bombs, computes **SHA-256 server-side**.
3. **Dedup** within domain: `(domain_id, sha256)` is unique — same bytes → one source even if filenames differ.
4. Server picks **current active parser** from runtime settings and **freezes** it on the row as `parserKind: "docling" | "reducto"`.
5. Raw file goes to **governed object storage** (randomized key; filename is display metadata only).
6. Postgres gets `state=pending` + a **preparation operation** row; worker picks it up.

```text
Admin POST upload
       │
       ├─ sniff / size / bomb checks
       ├─ sha256(H) ── duplicate? ──▶ 409 duplicate_source or same source
       ├─ parser_kind = runtime_settings.active_parser_kind  (FROZEN)
       ├─ store bytes ──▶ object storage
       └─ DB: source pending + prepare operation queued
```

---

## Stage 2: Prepare (worker + parser adapter)

**Who:** Background worker with DB lease + generation fence  
**Contract** (`docs/architecture/api-and-integration-flows.md`):

```text
Worker → parser: parse with frozen parser kind + private live credential
Worker → Postgres: replace canonical blocks/images atomically, mark prepared
```

### What gets written

From `docs/database-schema.txt`:

- **`source_blocks`**: ordered rows with `kind`, `canonical_markdown`, page range, heading/section metadata.
- **`source_images`**: figure assets linked to blocks (hash, mime, alt, page).
- **`source_documents.state`**: `pending` → `prepared`.

Replace is **atomic** — never half-updated blocks (A-07). Retry bumps **preparation_generation** but keeps the **same frozen parser kind**.

### Admin controls (P4-04)

| Action | Endpoint | Effect |
|--------|----------|--------|
| Retry prepare | `POST .../retry` | New generation, same parser |
| Cancel prepare | `POST .../cancel` | Stale completion cannot publish blocks |
| Outline (structure only) | `GET .../outline` | Headings/tables/figures — **no canonical text** |
| Delete | `DELETE .../source` | Fence retrieval, redact chat, cleanup |

---

## Docling vs Reducto — how each is used

Both implement the **same parser adapter port**: input = stored file bytes + frozen kind; output = **one canonical, parser-independent representation** (`docs/architecture/api-and-integration-flows.md`).

```text
                    ┌─────────────────────────────────────┐
                    │         Parser adapter port          │
                    │  in: bytes, content_type, parser_kind│
                    │ out: ordered blocks + image metadata │
                    └─────────────────────────────────────┘
                           ▲                    ▲
                           │                    │
              ┌────────────┴───┐    ┌───────────┴──────────┐
              │ Docling adapter │    │ Reducto adapter       │
              │ (local process) │    │ (external HTTP/API)   │
              └────────────────┘    └───────────────────────┘
```

| | **Docling** | **Reducto** |
|---|-------------|-------------|
| **Where it runs** | Locally in worker/backend (`docs/tech-stack.md`: “local Docling”) | External service (`parser-provider reducto` in PRD) |
| **Credentials** | None — bundled/local library | Encrypted in `provider_configs` (kind `reducto`), resolved at execution |
| **When chosen** | `runtime_settings.active_parser_kind = docling` at upload time | Same, but `reducto` |
| **Frozen on source** | `source_documents.parser_kind` never changes for that document | Same |
| **If admin changes default later** | In-flight prepare still uses frozen kind (A-13) | Same |

**Selection flow:**

```text
At upload:
  active_parser_kind ← runtime_settings (singleton default, P2)

At worker execute:
  if source.parser_kind == "docling":
      DoclingAdapter.parse(file from object storage)
  elif source.parser_kind == "reducto":
      ReductoAdapter.parse(file, credentials from provider_configs)
  
  map vendor output → Canonical Source Blocks (NOT stored raw)
```

**Why two parsers?** Docling = no external dependency, good for dev/on-prem. Reducto = higher-quality/cloud parsing when admins configure API credentials. Product behavior is identical after prepare; citations always point at **Source Blocks**, not parser chunks.

---

## Stage 3: Index (still “ingestion,” but separate worker)

After **prepared**, admin triggers indexing (`POST .../index/retry`, A-08):

1. **Renderer** converts canonical blocks → versioned **LightRAG handoff** with **local provenance markers** (P5-02).
2. Index worker submits to the domain’s **private LightRAG runtime** (idempotent key from content hash + generation).
3. Worker polls until **ready** or safe retryable failure.
4. `index_state = ready` → source becomes **query-eligible** (with running domain).

```text
prepared blocks
      │
      ▼
[canonical-block renderer] ──▶ LightRAG handoff + provenance markers
      │
      ▼
LightRAG index (private, per domain)
      │
      ▼
index_state = ready  ──▶  retrieval can map hits → Source Blocks → Evidence
```

---

## What the browser sees (and doesn’t)

**Admin:** source metadata, `parserKind`, `state`, `indexState`, operations — via `/admin/domains/.../sources*`.

**Members:** only safe **`documentRef`**, labels, PDF preview — via `/documents/{documentRef}`. No parser errors, hashes, or storage keys (`docs/contracts/document-and-evidence-contract.md`).

All traffic: **Browser → Next.js BFF → FastAPI**. Parsers and object storage are **private** (`docs/architecture/frontend-security-boundary.md`).

---

## Safety / concurrency rules (don’t skip these)

1. **Parser kind frozen at upload** — retry doesn’t switch Docling ↔ Reducto.
2. **Generation + lease** — stale workers can’t overwrite newer cancel/retry/delete.
3. **Dedup by hash** inside a domain (A-06).
4. **Delete fences first** — block retrieval, redact citing chat turns, then cleanup storage/LightRAG (A-09).
5. **No raw parser output in API, logs, or Evidence** — only mapped blocks and safe excerpts (≤500 chars).

---

## Build-plan task map

| Phase | Task | Delivers |
|-------|------|----------|
| P2 | Runtime config | `activeParserKind`, Reducto credentials |
| P4-01 | Schema + storage | `source_documents`, object store adapter |
| P4-02 | Upload validation | Stream limits, sniff, dedup, parser freeze |
| P4-03 | **Docling/Reducto adapters** | Real parse → canonical blocks transaction |
| P4-04 | Admin APIs | outline, retry, cancel, delete |
| P5 | Indexing | LightRAG handoff, readiness, provenance |

---

## One-line summary

**Upload validates and stores bytes → worker parses with frozen Docling or Reducto → product writes ordered Source Blocks → second worker indexes blocks into per-domain LightRAG → only then can chat retrieve mapped Evidence.**

If you want, I can walk through the same flow mapped to specific service filenames once P4 code exists, or contrast this with how vendored LightRAG uses Docling internally (that’s reference code, not the CE adapter contract).