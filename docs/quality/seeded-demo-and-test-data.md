# Seeded Demo and Test Data

This fixture contract gives developers, screenshots, browser tests, and concurrency tests the same deterministic world. It specifies required implementation artifacts; the reconstruction package does not claim that the fixture bytes already exist. The first fixture slice must generate and commit them before visual/E2E acceptance. It contains synthetic content only and must never run automatically in production.

## Seed rules

- Seed command requires `CE_ENVIRONMENT=development|test` and `CE_ALLOW_TEST_SEED=true`; otherwise fail before writes.
- IDs, timestamps, file bytes, hashes, event sequences, and expected answers are committed constants. Do not use current time, random UUIDs, live providers, or network parsers.
- Seed is idempotent: rerun converges by fixture key; `--reset` is test-database-only and refuses non-allowlisted database names.
- Passwords below are public test values, never defaults. Production bootstrap rejects them.
- Private object keys, source/block IDs, session hashes, and trace IDs may exist in fixture internals but never expected browser snapshots.
- Clock default: `2026-07-17T12:00:00Z`; tests advance an injected clock.

Target artifact layout and commands:

```text
app/tests/fixtures/manifest.json
app/tests/fixtures/documents/<fixture>.pdf
app/tests/fixtures/previews/<fixture>.pdf
app/tests/fixtures/sse/<scenario>.ndjson
app/tests/fixtures/expected/<capability>.json
app/client/tests/parity/manifests/<target-id>.json
app/client/tests/parity/baselines/<browser>/<viewport>/<case>.png
```

```text
(cd app/client && npm run fixtures:build)   # planned deterministic generator; no network
(cd app/client && npm run fixtures:verify)  # planned hash/count/projection check; no writes
(cd app && python -m context_engine.dev.seed --manifest tests/fixtures/manifest.json)
```

These are P0/P9 target paths and commands, not claims that the lifted tree implements them today. P0 must establish the canonical Python package root before the seed command can pass.

`fixtures:build` writes a canonical JSON manifest with `schemaVersion`, generator source revision, injected clock, ordered artifacts, SHA-256, byte size, media type, semantic fixture key, expected page count, and dependent case IDs. It must refuse to overwrite a changed artifact unless `--update` is explicitly supplied. A blank, wildcard, or `TBD` hash fails verification.

## Actors

| Fixture | Login | Role/state | Purpose |
| --- | --- | --- | --- |
| `user_admin_ava` | `admin.ava` / `CE-Test-Admin-2026!` | administrator/enabled | lifecycle, settings, operations |
| `user_member_mina` | `member.mina` / `CE-Test-Member-2026!` | member/enabled | primary conversation/evidence owner |
| `user_member_noah` | `member.noah` / `CE-Test-Member-2026!` | member/enabled | isolation/concurrency actor |
| `user_admin_ren` | `admin.ren` / `CE-Test-Admin-2026!` | administrator/enabled | conflicting admin operations |
| `user_disabled_dia` | `disabled.dia` / `CE-Test-Member-2026!` | member/disabled | generic login denial |

Browser projects create separate cookie jars for every actor. Multi-tab tests may share Mina's session but use distinct tab-local request/selection state.

## Runtime profiles and domains

All provider adapters are deterministic fakes. Provider status exposes only configured/readiness metadata.

| Fixture | State | Corpus/result | Cases |
| --- | --- | --- | --- |
| `domain_manuals` / Equipment Manuals | running, ready | three eligible documents; non-empty bounded graph | M-02–M-06, M-14–M-21, C-01/C-03 |
| `domain_policies` / Workplace Policies | running, ready | eligible document, query fixture returns no hit for `NO_HIT_QUERY` | no-grounded behavior |
| `domain_research` / Research Drafts | stopped | prepared source, no query access | M-02 failure, A-03, M-17 |
| `domain_deleting` / Legacy Procedures | deleting | fenced source + failed cleanup op | A-10 recovery, C-02, M-17/M-18 |

Use embedding fixture `embed_384_v1` with dimension 384 and synthesis fixture `synth_deterministic_v1`. Bind Equipment Manuals to extraction-capable synthesis fixture `synth_extract_deterministic_v1` in addition to the embedding profile. A second embedding profile `embed_768_unused` supports creation tests. Attempts to mutate `embed_384_v1` exercise A-02.

## Documents and canonical anchors

Fixture bytes live under `tests/fixtures/documents/`; a manifest records SHA-256, byte size, MIME, page count, preview checksum, parser version, and canonical-block version.

| Public ref | Domain/state | Required content |
| --- | --- | --- |
| `doc_pump_manual` | manuals/ready | 24-page synthetic PDF; figure on page 18, text on page 7, table on page 12 |
| `doc_safety_bulletin` | manuals/ready | 3-page PDF with overlapping terms to test deterministic ordering |
| `doc_service_notes` | manuals/prepared, not indexed | visible only to admin lifecycle APIs |
| `doc_leave_policy` | policies/ready | 5-page synthetic PDF for policy grounding |
| `doc_legacy_delete` | deleting/deleting | content/location reads fenced |

Canonical Pump Manual fixtures:

| Evidence fixture | Kind | Anchor | Safe excerpt |
| --- | --- | --- | --- |
| `ev_mina_figure_valve` | figure | page 18, region `(0.12,0.24,0.66,0.41)`, section `4.2 Relief valve` | `Figure 4 places the relief valve downstream of the pump.` |
| `ev_mina_text_lockout` | text | page 7, region absent, section `2.1 Lockout` | `Isolate electrical power before opening the service panel.` |
| `ev_mina_table_torque` | table | page 12, region `(0.10,0.30,0.80,0.34)` | `M12 fasteners use the listed 80 N·m service torque.` |
| `ev_mina_page_only` | figure | page 20, no region/section, fallback `page` | `The inspection diagram is shown on this page.` |

All excerpts are synthetic and <=500 characters. Tests assert normalized coordinates, one-based pages, safe labels, document refs, citation order, PDF ranges, and semantic fallback. A malicious upload fixture includes path-like filename/control characters, MIME mismatch, oversized metadata, and decompression-bomb signature; it must never become usable content.

## Domain graph fixtures

Deterministic graph projections for Equipment Manuals live under `tests/fixtures/expected/graph/` and are keyed by domain fixture plus optional label focus. Public refs are opaque fixture tokens, never vendor LightRAG IDs.

| Fixture key | Kind | Domain | Required projection |
| --- | --- | --- | --- |
| `graph_manuals_snapshot` | snapshot | `domain_manuals` | non-empty `GraphSnapshotDto` with pump and relief-valve nodes, at least one connecting edge, `truncated:false` |
| `graph_node_pump` | node | `domain_manuals` | safe label `Pump`; kind `Equipment` or null after sanitizer; non-negative degree |
| `graph_node_relief_valve` | node | `domain_manuals` | safe label `Relief valve`; selectable via label search `relief`; drives M-15/E2E-M15 |
| `graph_edge_pump_relief` | edge | `domain_manuals` | `sourceRef`/`targetRef` resolve only to the pump and relief-valve opaque node refs; safe relation label or null |
| `graph_label_relief_valve` | label-search hit | `domain_manuals` | `GraphLabelDto` for `q=relief` within limit 1..50 |
| `graph_manuals_empty` | snapshot | ready domain without indexed entities | empty nodes/edges, `truncated:false` |
| `graph_manuals_truncated` | snapshot | capacity/truncation tests | `truncated:true` at server caps without raw properties |

Expected browser assertions use only closed Graph DTO fields. Fixture internals may retain private runtime identities for mapper tests, but those values never appear in URL, DOM, network, or visual baselines.

## Conversations and turns

| Fixture | Owner | State | Expected projection |
| --- | --- | --- | --- |
| `conv_mina_manuals` | Mina | active | completed figure turn plus text/table turn |
| `turn_mina_figure` / `client_demo_figure_001` | Mina | completed grounded | answer cites `[1] = ev_mina_figure_valve`; deep-links page 18 |
| `turn_mina_mixed` / `client_demo_mixed_001` | Mina | completed grounded | ordered text `[1]`, table `[2]` |
| `turn_mina_direct` / `client_demo_direct_001` | Mina | completed direct | no domain/evidence/citations |
| `turn_mina_no_hit` / `client_demo_nohit_001` | Mina | completed | `no_grounded_context`, no answer |
| `turn_mina_redacted` / `client_demo_redacted_001` | Mina | redacted | question preserved; answer/evidence/refs absent |
| `conv_noah_private` | Noah | active | inaccessible to Mina/admin conversation APIs |

Provider output is keyed by normalized request fixture, not arbitrary prompt matching. For the figure question `Where is the relief valve?`, the exact deterministic answer is `The relief valve is downstream of the pump [1].` The expected safe terminal projection and raw SSE transcripts are committed for whole-frame, random-chunk, duplicate, gap, resume, replay, cancel, and redaction cases.

## Composer data

| Fixture | Private id | Owner/state | Purpose |
| --- | --- | --- |
| `template_safety_summary` | `c0ffee01-0001-4001-8001-000000000001` | approved | valid bounded template reference |
| `template_disabled` | `c0ffee01-0001-4001-8001-000000000002` | disabled | rejected target-state reference |

| Token fixture key | Kind | Purpose |
| --- | --- | --- |
| `token_mina_source_valid` | source | valid Mina source token |
| `token_mina_evidence_valid` | evidence | valid Mina evidence token |
| `token_mina_template_valid` | template | valid Mina template token |
| `token_mina_expired` | source | expired denial |
| `token_noah_wrong_owner` | source | wrong-owner denial |
| `token_mina_wrong_domain` | source | wrong-domain denial |
| `token_mina_deleted_target` | source | deleted-target denial |
| `token_mina_disabled_template` | template | disabled-template denial |
| `token_mina_consumed_source` | source | already-consumed denial (`consumed_at` set; still unexpired) |
| `token_mina_figure_bound_source` | source | consumed provenance for `turn_mina_figure` fingerprint (order 1) |
| `token_mina_figure_bound_evidence` | evidence | consumed provenance for `turn_mina_figure` fingerprint (order 2) |
| `token_mina_figure_bound_template` | template | consumed provenance for `turn_mina_figure` fingerprint (order 3) |

| Accepted-ref public ref | Kind | Turn | Purpose |
| --- | --- | --- | --- |
| `accepted_mina_source_01` | source | `turn_mina_figure` | durable accepted source projection |
| `accepted_mina_evidence_01` | evidence | `turn_mina_figure` | durable accepted evidence projection |
| `accepted_mina_template_01` | template | `turn_mina_figure` | durable accepted template projection |
| `accepted_mina_redacted_01` | source | `turn_mina_redacted` | redacted labels cleared |

`turn_mina_figure.composer_ref_fingerprint` equals the production `composer_ref_fingerprint` over the ordered `token_mina_figure_bound_*` raw preimages (`ce-p11-01:…`). Denial-matrix `token_mina_*_valid` tokens stay unconsumed. `turn_mina_redacted` keeps the empty fingerprint (projection/redaction-only; not a fingerprint/replay demo). Seeded figure parents are not an SSE event ledger — live turn-start owns replay proofs.

Composer discovery returns one source, evidence, and template ref with fixed safe labels. Durable seeds persist token hashes only (`safe_description` holds the fixture key). Raw token plaintext is generated deterministically only in ephemeral tests, never committed under `expected/` or seed modules. Include expired, wrong-owner, wrong-domain, deleted-target, disabled-template, already-consumed (`token_mina_consumed_source`), and figure-bound consumed tokens.

Demo prompt templates and composer-ref parents install only through the gated composer seed entry (`CE_ENVIRONMENT=development|test` and `CE_ALLOW_TEST_SEED=true`). API lifespan must not upsert demo templates.

## Operations and fault fixtures

Seed queued/running/failed/succeeded operations with fixed generations:

- domain start generation 4 with an expired lease for worker-recovery tests;
- stop generation 5 and stale start completion generation 4 for A-05;
- source preparation generation 2 running plus late generation 1 result for A-07;
- index generation 3 with provider timeout-after-accept for reconciliation;
- domain delete generation 8 with object cleanup failed/retryable;

Fault adapters accept closed scenarios: `timeout_before_accept`, `timeout_after_accept`, `auth_failed`, `malformed_payload`, `unmapped_hit`, `wrong_domain_hit`, `provider_mid_stream_failure`, `object_range_failure`, and `audit_write_failure`. Scenario selection is test dependency injection, never a browser field.

## Concurrency recipes

Use transaction barriers/latches, not timing sleeps:

| Case | Actors/action | Required result |
| --- | --- | --- |
| M-10 | Mina tabs submit same request ID/fingerprint | one turn/provider call; both attach/replay |
| M-10 conflict | second tab changes domain/message/ordered refs | one turn; second `idempotency_conflict` |
| A-05 | Ava stop vs Ren delete manuals clone | one legal generation; loser current-state conflict or delete supersedes |
| A-06 | Ava/Ren upload identical bytes/different names | one `(domain,sha256)` source/preparation |
| C-01 | Mina/Noah query manuals concurrently | isolated owner/trace/evidence/sequence |
| C-05 | revoke Ava admin role before protected commit | transaction denies and writes safe denial audit |

Each recipe asserts database rows, external fake call counts, audit rows, API responses, and both browser projections.

## Screenshot and browser baseline

The default demo entry state is Mina on `/chat`, `conv_mina_manuals`, `turn_mina_figure` selected, Evidence panel open. Admin baselines use Ava with `domain_manuals`. Freeze clock, locale `en-US`, timezone `UTC`, fonts, reduced-motion preference, scrollbar policy, and animation completion. Reference sizes are defined by the visual-regression plan; fixture content must not be edited merely to make a screenshot fit.

## Fixture validation gate

CI verifies manifest hashes, FK/uniqueness/check constraints, public-ref/private-ID separation, no secret-like production values, exact seeded counts, all expected API projections, SSE reducer snapshots, PDF page/range checks, and rerun idempotency. A fixture change updates its manifest, expected contract snapshots, affected case IDs, and visual baselines in one reviewed change.
