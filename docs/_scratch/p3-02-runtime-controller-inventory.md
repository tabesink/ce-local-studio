# P3-02 Runtime Controller Port Inventory

Date: 2026-07-25

Owner: P3-02

Status: DONE - implemented and proven 2026-07-25

Requirements and cases: FR-03; outbound domain runtime controller port in
`docs/architecture/data-and-lifecycle.md`; components target
`adapters/domain_runtime_controller.py`.

## Scope

- Extract `DomainRuntimeController` Protocol, Local/Docker adapters, and
  `controller_from_settings` into `app/context_engine/adapters/domain_runtime_controller.py`.
- Require stable `operation_key` + `control_generation` on mutating adapter
  calls; include them in Docker command payloads and local runtime records.
- Return typed `RuntimeControllerResult` outcomes
  (`succeeded` / `failed` / `uncertain`) with bounded Docker timeouts mapping
  to `uncertain` (not hard failure).
- Keep lifecycle service ownership in `services/domains.py`; map uncertain
  outcomes to non-terminal operation messages pending P3-03 reconciliation.

## Out of scope

- Lease owner/expiry/heartbeat and stale-worker no-ops (P3-03).
- Full DRIFT-32 reconciliation worker loops (P3-03).
- Moving start/stop off the sync-in-request pilot path (P3-03).
- Real Docker daemon integration suite (optional marker reserved; not a P3-02
  exit gate).
- Settings UI (P9).

## Disposition register

| Surface | Disposition | P3-02 action |
| --- | --- | --- |
| Controllers inlined in `services/domains.py` | replace | Move to `adapters/domain_runtime_controller.py` |
| Void/`DomainControllerError` results | modify | Typed `RuntimeControllerResult` / `RuntimeHealth` |
| Docker timeout → hard failure | modify | Timeout → `uncertain` |
| `tools/domain_runtime_controller.py` | retain-and-reverify | Accepts extended payload fields; private Docker CLI unchanged |
| DomainDeleteWorker controller call | modify | Pass operation key/generation; honor uncertain/failed |

## Retained invariants

- Adapters do not authorize or commit product state.
- Private runtime paths and controller payloads stay out of public DTOs.
- Services still commit operation intent before external controller calls.
