# P11-03 Private Assembly / Fingerprint / Replay / Redaction Evidence

Date: 2026-07-27  
Status: DONE (with explicit residuals)  
Plan: `docs/plans/2026-07-27-018-feat-p11-03-assembly-fingerprint-replay-plan.md`  
Branch: `feat/p11-03-assembly-fingerprint-replay`

## What landed

| Item | Result |
| --- | --- |
| Seed fingerprint honesty | Dedicated consumed `token_mina_figure_bound_*` tokens; `turn_mina_figure` fingerprint via production `composer_ref_fingerprint`; `token_mina_*_valid` stay unconsumed; `turn_mina_redacted` empty fingerprint (projection-only) |
| Private assembly proof | `tests/test_prompt_assembly.py` — template/source/evidence kinds, redacted evidence skip, source/total caps, non-persist of assembly markers on turn columns |
| Replay-without-reconsume (DRIFT-26) | HTTP `turns:stream` identical POST after consume attaches; `consumed_at` stable; `CountingSynthesis.direct_calls == 1` |
| Refs-changed conflict | Same `clientRequestId` with changed / reordered / omitted tokens → `409 idempotency_conflict`; no consume on conflict path |
| Privacy on conflict/attach | Response bodies omit raw tokens and token hashes |
| Accepted-ref redaction | Delete path with real `ConversationTurnComposerRef` clears public labels; expires source composer tokens; validate fails closed |
| Seeded-demo recipe | M-10 conflict includes ordered refs; figure-bound tokens documented |

## Commands and results

```text
cd app
python -m pytest tests/test_composer_seed_refs.py -q
# PASS

python -m pytest tests/test_prompt_assembly.py -q
# PASS

python -m pytest tests/test_composer_refs_replay_fingerprint.py -q
# PASS (DRIFT-26 HTTP attach + refs conflict matrix + empty-ref attach)

python -m pytest tests/test_delete_redaction.py::test_m11_source_delete_clears_accepted_refs_and_expires_composer_tokens -q
# PASS
```

## Privacy guarantees evidenced

- Assembled template/source/evidence bodies are worker-time only; turn columns and durable event payloads do not store assembly markers / “Approved context” strings (assemble path + empty-event check; HTTP attach suites also omit raw tokens).
- Attach/conflict HTTP envelopes do not echo raw composer tokens or token hashes.
- Delete redaction clears accepted-ref public labels; expired-token validate errors omit target IDs and raw tokens.
- Seed modules persist hashes / fixture keys only; figure-bound tokens are consumed provenance, not denial-matrix valid tokens.

## Residuals (honest non-claims)

| Residual | Owner |
| --- | --- |
| Browser References discover UI unlock / E2E | later gates |
| P11-04 Evidence attach UX (suggest / attach chips) | DEFERRED — `docs/_scratch/p11-04-evidence-reattachment-evidence.md` |
| P12 adversarial privacy breadth / deployed-ingress SSE | P12 |
| Opt-in PostgreSQL race suites for fingerprint concurrency | operator matrix (existing M-10 / consume race patterns) |

## Tracker updates

- `docs/master-build-plan.md` P11-03 → DONE; P11 phase → DONE (P11-04 Evidence attach UX DEFERRED).
- `docs/brownfield-refactor-register.md` DRIFT-26 → DONE; hashed-token foundation row notes consume + replay-without-reconsume closed; P11-04 deferred residual named.
