# P3-03 Domain Lease / Generation / Delete Worker Inventory

Date: 2026-07-25

Owner: P3-03

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-03; A-03; A-04 fence; A-05; A-10; DRIFT-12 race
half; DRIFT-32 domain half; architecture lease/generation rules.

## Scope

- Generation-fenced start/stop completion via conditional domain state update.
- Short-lived lease fields on start/stop ops for owner-checked finish.
- A-05 delete supersede: cancel active start/stop, bump generation, queue delete.
- DomainDeleteWorker heartbeat (&lt; ⅓ lease), owner+generation checks on complete,
  expired lease reclaim, uncertain leave-non-terminal with reclaim path.
- Immediate query fence proofs for stop/delete intent (`domain_available`).
- PostgreSQL 16 race evidence with latches where needed.

## Out of scope

- Full async start/stop worker class (retain sync pilot with fences).
- Mid-turn chat A-04 `domain_became_unavailable` policy (P7).
- Index/controller DRIFT-32 half beyond domain ops (P5-03).
- Live Docker daemon suite; Settings UI.

## Disposition register

| Surface | Disposition | P3-03 action |
| --- | --- | --- |
| Sync start/stop in-request | retain-and-reverify | Keep pilot; fence completion |
| `update_domain_state_if_current` | modify | Wire into start/stop; bump version |
| Delete vs active start/stop | modify | Supersede/cancel active op |
| DomainDeleteWorker | modify | Heartbeat, owner check, reconcile reclaim |
| `domain_available` fence | retain-and-reverify | PG proofs for stop/delete |
| Mid-turn chat A-04 | defer to P7 | Residual only |
