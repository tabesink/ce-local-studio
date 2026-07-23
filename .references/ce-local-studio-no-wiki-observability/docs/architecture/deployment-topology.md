# Deployment Topology

This is the production runtime contract for P12. Compose may emulate it, but a single-process development success is not release evidence.

## Runtime units

```text
Internet/LAN
  -> TLS ingress/WAF
      -> Next.js web+BFF replicas
          -> FastAPI replicas (private)
              -> PostgreSQL 16 primary
              -> governed object storage
              -> per-domain LightRAG query endpoints (private)
              -> model provider adapters
          -> database-leased worker replicas
              -> object storage, parser/model adapters, LightRAG/runtime controller
```

| Unit | Scale/ownership | Public exposure | Durable state |
| --- | --- | --- | --- |
| Ingress | >=2 or managed HA | HTTPS only | certificates/config outside app images |
| Next web/BFF | stateless horizontal replicas | through ingress | none; no authenticated cache |
| FastAPI | stateless horizontal replicas | private service only | PostgreSQL/object store through ports |
| Worker | horizontal by queue class; DB leases | none | operation/outbox rows, not local disk |
| PostgreSQL 16 | managed/HA per environment | none | all product authority |
| Object store | versioned, encrypted, lifecycle governed | none | source binaries and durable derived previews |
| LightRAG runtime | isolated per domain; rebuildable | none | ephemeral index/runtime state; not backup authority |

Workers may be one image with queue flags or separate preparation/index/domain-cleanup deployments. Every class has its own concurrency and connection budget. Web, API, and worker artifacts share one release manifest and compatible contract/schema range.

## Environment matrix

| Environment | Data/integrations | Required proof |
| --- | --- | --- |
| Development | Compose PostgreSQL, filesystem object adapter, fake/pinned adapters | fast unit/contract loop; never production evidence |
| Test | disposable PostgreSQL 16 and S3-compatible store; deterministic adapters | migrations, transactions, concurrency, SSE, browser cases |
| Staging | production ingress/network/object-store shape; sandbox providers | upgrade/rollback, load, failure, backup/restore rehearsal |
| Production | HA database/store, KMS/secret manager, monitored private services | signed approval and release evidence manifest |

Production never uses SQLite, browser filesystem access, a filesystem source adapter, shared domain runtime directories, or an unauthenticated sidecar.

## Network and ingress rules

- Ingress replaces trusted forwarding headers and enforces TLS, host allowlist, header/body/time limits, and connection limits.
- Only ingress reaches Next; only Next and approved internal probes reach FastAPI; only API/workers/migration jobs reach PostgreSQL and object storage.
- Provider, parser, LightRAG, and controller egress is allowlisted. They cannot call browser-controlled destinations.
- SSE paths use HTTP/1.1 or HTTP/2 streaming with proxy buffering, response compression, caching, and body transformation disabled. Idle timeout exceeds heartbeat interval plus reconnect margin.
- Document content preserves byte ranges. Upload requests preserve backpressure and have longer explicit request timeouts than ordinary JSON.

Deployed tests measure arrival of at least two answer deltas before terminal completion; receiving one buffered response fails P12-05.

## Boot, health, and shutdown

| Probe | Meaning | Must not do |
| --- | --- | --- |
| `/health/live` | process event loop is serving | query providers, object store, or domain runtimes |
| `/health/ready` | config valid; database reachable; schema within supported range; bootstrap complete; indispensable object-store capability available | fail globally for one provider/domain outage |
| internal worker readiness | migrations compatible; database/store reachable; queue class configured | claim work before ready |

Startup fails closed on invalid encryption/cookie/trusted-host settings or incompatible schema. During shutdown, ingress stops new traffic, API stops new turns, workers stop claims, streams/work drain within the configured bound, and unresolved external work remains recoverable by lease expiry/reconciliation. A closed socket is not completion.

## Database work and asynchronous ownership

- A one-shot migration job runs before new API/workers. Application replicas never run migrations on boot.
- Operation plus outbox/audit intent commits in one transaction. Workers claim rows with `FOR UPDATE SKIP LOCKED`, lease owner/expiry, and generation.
- Workers heartbeat at less than one third of lease duration. A completion commits only when lease and generation match.
- External calls occur outside database transactions and carry stable idempotency keys. Timeout with unknown remote outcome enters reconciliation before retry.
- Object and remote cleanup is repeatable. Product rows are not reported deleted until required cleanup and reconciliation reach the contracted terminal state.

## Release and compatibility sequence

1. Produce immutable web/API/worker images, SBOM, lockfile digests, source revision, OpenAPI/SSE versions, and migration head.
2. Back up PostgreSQL and record the matching object-store consistency/version marker.
3. Apply expand-only migration; verify migration job and readiness.
4. Deploy API/workers that read old+new shapes, then web; run ingress smoke and canary cases.
5. Run data backfill as resumable leased work where needed.
6. Contract old schema only in a later release after all readers are proven migrated.

Rollback reverts images only while their declared schema/contract ranges include the current versions. Destructive rollback uses restore, not an improvised down migration. SSE changes are additive within a major version; unsupported major versions fail explicitly.

## Capacity and load shedding

Each environment records tested values for: API replicas/connections, worker concurrency by class, database pool/reserve, concurrent streams per user/instance, stream duration, upload bytes, request bytes, document ranges, operation queue depth/age, provider quotas, parser timeouts, and object-store throughput.

Reject before unbounded allocation:

- `413` for body/upload limits;
- `429` for per-principal/request rate or concurrent-stream limits with `Retry-After`;
- `503 capacity_unavailable` for global/provider/queue saturation;
- `409` for legal-state and per-conversation operation conflicts.

Minimum service metrics use bounded labels such as route template, operation type, outcome, and safe error code. User/domain/source/turn IDs may appear only in allowlisted internal logs, never metric labels.

## Backup, restore, and disaster recovery

The backup unit is PostgreSQL, matching governed object versions, encryption-key references, and deployment configuration metadata. LightRAG indexes and runtime directories are reconstructed from canonical blocks and recorded handoff versions.

Initial targets are RPO <=15 minutes and RTO <=4 hours. At least quarterly, restore into an isolated environment, run object/database reconciliation, rebuild one domain, and verify authentication, citations/anchors, redactions, governed-ref invalidations, audit continuity, and deletion tombstones. Missing keys or mismatched object versions fail the drill.

## Production release gate

Release evidence must include migration fresh/upgrade proof, image rollback compatibility, deployed login/CSRF/logout, incremental SSE/resume/redaction, byte-range PDF access, worker death and lease recovery, provider/parser/LightRAG timeout, database failover behavior, capacity/load shedding, vulnerability/secret scans, backup restore, minimum health/service-metric checks, and operator runbooks. Evidence points to artifact digests and cannot be copied from a development run. This gate does not authorize a product-facing observability dashboard.
