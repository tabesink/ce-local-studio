# DTO Schema Catalog

This catalog closes the public JSON vocabulary used by `http-api-catalog.md`. It is the authoring input for generated OpenAPI and the TypeScript client. Names are strict camelCase; unknown fields are rejected. A field absent here is not browser-visible.

## Common scalars and envelopes

```text
OpaqueRef       := string, 8..128, ^[A-Za-z0-9_-]+$
UtcTimestamp    := RFC 3339 UTC string using `Z`, whole-second precision
SafeLabel       := trimmed string, 1..255
SafeMessage     := trimmed string, 1..500
Version         := positive integer; serialized into a strong ETag
Cursor          := opaque string, 1..512
RequestId       := opaque server value, 1..80; caller values are never adopted
ErrorCode       := one member of the closed common/capability sets below
```

```ts
type ErrorEnvelope = {
  error: { code: ErrorCode; message: string; requestId: string; fields: Record<string, string> };
};
type Page<T> = { items: T[]; nextCursor: string | null };
type AllowedAction = { action: string; enabled: boolean; reasonCode?: string };
```

`allowedActions` is advisory presentation. The server reauthorizes every mutation.

## Closed enums

```text
Role = member | administrator
DomainState = stopped | running | deleting
OperationStatus = queued | running | succeeded | failed | cancelled
SourceState = pending | prepared | deleting
IndexState = not_requested | queued | processing | ready | failed | cancelled | deleting
TurnRoute = direct_llm | domain_rag
TurnStatus = running | completed | failed | cancelled | redacted
EvidenceKind = text | table | figure
```

## Identity and configuration

```ts
type CurrentUserDto = {
  id: OpaqueRef;
  displayName: SafeLabel;
  role: Role;
  disabled: false;
};

type ProviderSummaryDto = {
  kind: "openai" | "bedrock" | "ollama" | "reducto";
  displayName: SafeLabel;
  requiresCredentials: boolean;
  configured: boolean;
  credentialUpdatedAt: UtcTimestamp | null;
  version: Version;
};

type ModelProfileDto = {
  id: OpaqueRef;
  name: SafeLabel;
  profileKind: "synthesis" | "embedding";
  providerKind: "openai" | "bedrock" | "ollama";
  modelName: string;
  vectorDimensions: number | null;
  inUse: boolean;
  version: Version;
};

type RuntimeSettingsDto = {
  activeSynthesisProfileId: OpaqueRef | null;
  activeParserKind: "docling" | "reducto";
  version: Version;
};
```

Credentials are accepted only as write-only request fields and never occur in a response DTO.

## Domain and operation DTOs

```ts
type DomainSummaryDto = {
  id: OpaqueRef;
  displayName: SafeLabel;
  state: DomainState;
  queryEligible: boolean;
};

type AdminDomainDto = DomainSummaryDto & {
  embeddingProfile: { id: OpaqueRef; name: SafeLabel; vectorDimensions: number };
  runtimeReady: boolean;
  controlGeneration: number;
  activeOperationId: OpaqueRef | null;
  createdAt: UtcTimestamp;
  updatedAt: UtcTimestamp;
  version: Version;
  allowedActions: AllowedAction[];
};

type OperationDto = {
  id: OpaqueRef;
  targetKind: "domain" | "source" | "index";
  targetRef: OpaqueRef;
  operationType: string;
  status: OperationStatus;
  generation: number;
  message: SafeMessage | null;
  error: { code: string; message: SafeMessage } | null;
  requestedAt: UtcTimestamp;
  startedAt: UtcTimestamp | null;
  finishedAt: UtcTimestamp | null;
  version: Version;
  allowedActions: AllowedAction[];
};
```

Member `DomainSummaryDto` never contains runtime IDs, provider/model names, storage, worker, or diagnostic fields.

## Source and document DTOs

```ts
type AdminSourceDto = {
  id: OpaqueRef;
  documentRef: OpaqueRef;
  domainId: OpaqueRef;
  displayName: SafeLabel;
  contentType: string;
  sizeBytes: number;
  state: SourceState;
  parserKind: "docling" | "reducto";
  indexState: IndexState;
  activeOperationId: OpaqueRef | null;
  createdAt: UtcTimestamp;
  updatedAt: UtcTimestamp;
  version: Version;
  allowedActions: AllowedAction[];
};

type DocumentSummaryDto = {
  ref: OpaqueRef;
  label: SafeLabel;
  domain: DomainSummaryDto;
  contentType: "application/pdf";
  previewKind: "pdf" | "unavailable";
  pageCount: number | null;
  updatedAt: UtcTimestamp;
};
```

Outline items are `{kind:"heading"|"figure"|"table", label:SafeLabel, level:number|null, pageNumber:number|null}` and contain no canonical source text.

## Conversation, turn, and evidence DTOs

```ts
type ConversationSummaryDto = {
  id: OpaqueRef;
  title: string | null;
  createdAt: UtcTimestamp;
  updatedAt: UtcTimestamp;
  version: Version;
};

type AcceptedRefDto = {
  id: OpaqueRef;
  kind: "source" | "evidence" | "template";
  order: number;
  label: SafeLabel;
  description: SafeMessage | null;
};

type TurnDto = {
  id: OpaqueRef;
  clientRequestId: string;
  route: TurnRoute;
  status: TurnStatus;
  domain: DomainSummaryDto | null;
  userMessage: string;
  assistantAnswer: string | null;
  evidence: EvidenceItemDto[];
  acceptedRefs: AcceptedRefDto[];
  error: { code: string; message: SafeMessage; retryable: boolean } | null;
  createdAt: UtcTimestamp;
  completedAt: UtcTimestamp | null;
};

type ConversationDetailDto = ConversationSummaryDto & { turns: TurnDto[] };
```

`EvidenceItemDto`, document metadata, and location anchors are exactly those in `document-and-evidence-contract.md`. `AcceptedRefDto.id` is the persisted accepted-ref public ref, never its private row ID. A redacted turn has `assistantAnswer:null`, `evidence:[]`, and `acceptedRefs:[]`.

The standalone retrieval route uses a distinct stateless projection:

```ts
type RetrievalEvidenceRequestDto = {
  question: string; // trimmed, 1..2000
};

type RetrievalEvidenceItemDto = {
  citationLabel: string;
  sourceLabel: SafeLabel;
  excerpt: string; // canonical mapped text, 1..500
  kind: "text" | "table" | "figure";
  documentRef: OpaqueRef;
  documentLabel: SafeLabel;
  anchor: EvidenceAnchorDto | null;
};

type RetrievalEvidenceResponseDto = {
  result: "evidence_found" | "no_grounded_context";
  evidence: RetrievalEvidenceItemDto[];
};
```

`RetrievalEvidenceItemDto` has no evidence ID because the route is read-only and creates no owner-bound turn Evidence row. Citation labels are dense and response-scoped after final block deduplication. A nullable anchor means no page can be proved; persisted `EvidenceItemDto.anchor` remains required.

## Governed-context DTOs

```ts
type ComposerRefDto = {
  token: string; kind: "source"|"evidence"|"template";
  label: SafeLabel; description: SafeMessage | null; expiresAt: UtcTimestamp;
};
```

Composer tokens appear only in discovery responses and turn-start requests; they are never returned in histories.

## Internal operational records

Phase 1 audit rows, structured log records, service metrics, and dependency checks are internal operational data and have no public/browser DTO. Candidate Logs, Usage, Server, audit-review, and diagnostic-review DTOs belong to the Phase 2 contract described in `../future/observability-layer.md`.

## Request and query schemas

| Capability | Closed input |
| --- | --- |
| login | `username` 1..320, `password` 1..1024 |
| conversation create/rename | optional/title 1..120 |
| turn start | `clientRequestId` 1..80, `message` 1..4000, `domainId?`, ordered `composerRefTokens?` max 25 |
| stateless evidence retrieval | `question` trimmed 1..2000; no other fields |
| domain create | `displayName` 1..120, `embeddingProfileId` |
| upload | one multipart `file`; no browser-supplied domain/parser/storage fields |
| list | only filters listed in `http-api-catalog.md`; `limit` 1..100; one opaque cursor |

The server computes the normalized turn request fingerprint; it is not a public request field.

## Closed error-code sets

| Capability | Stable codes |
| --- | --- |
| common authorization/validation | `unauthenticated`, `forbidden`, `validation_error` |
| framework boundary | `not_found`, `http_error`, `internal_error`; these never replace a more specific capability code |
| auth | `invalid_credentials`, `session_expired`, `csrf_invalid`, `account_unavailable` |
| domain | `domain_not_query_eligible`, `domain_operation_in_progress`, `domain_state_conflict`, `operation_conflict`, `stale_revision` |
| source/index | `duplicate_source`, `source_not_ready`, `operation_conflict`, `content_rejected` |
| chat | `domain_required`, `idempotency_conflict`, `cursor_expired`, `turn_not_cancellable` |
| document/evidence | `evidence_not_found`, `document_not_found`, `evidence_unavailable`, `document_preview_unavailable`, `document_content_unavailable`, `range_not_satisfiable` |
| capacity/dependency | `rate_limited`, `capacity_unavailable`, `dependency_unavailable`, `audit_unavailable` |

The union of these rows is the Phase 1 HTTP `ErrorCode` vocabulary. Adding or renaming a code is a contract change. Operation-row failure codes and SSE terminal reason codes are separately closed by their owning DTO/event schemas and do not silently become HTTP error codes.

## Generation gate

P0 must turn these definitions into committed JSON Schema/OpenAPI components and generate the browser client. CI fails when registered routes, OpenAPI, this catalog, examples, or generated types diverge. Until that artifact exists, feature slices that depend on the affected DTO remain blocked; handwritten substitute interfaces are prohibited.
