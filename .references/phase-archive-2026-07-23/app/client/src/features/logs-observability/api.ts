/* CE adapter for the LS logs-observability slice (admin-only, P8):

   GET /api/v1/admin/audit-events?limit=&cursor=&eventName=...
   GET /api/v1/admin/domains/{domainId}/diagnostics/lightrag?tail=

   Scoped log sessions and SSE log tails are F-010 gated. */

import { ceFetch } from "@/lib/api/client";

export type AuditEvent = {
  id: string;
  eventName: string;
  actorKind: string;
  actorUserId: string | null;
  targetKind: string | null;
  targetId: string | null;
  requestId: string | null;
  traceId: string | null;
  outcome: string;
  safeErrorCode: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
};

export type AuditEventsPage = {
  auditEvents: AuditEvent[];
  nextCursor: string | null;
};

export type LightragDiagnostics = {
  domainId: string;
  kind: string;
  capturedAt: string;
  lineCount: number;
  truncated: boolean;
  lines: Array<{ message: string }>;
};

export async function listAuditEvents(input: {
  limit?: number;
  cursor?: string;
  eventName?: string;
  outcomeFilterUnsupported?: never;
} = {}): Promise<AuditEventsPage> {
  const params = new URLSearchParams();
  params.set("limit", String(input.limit ?? 50));
  if (input.cursor) params.set("cursor", input.cursor);
  if (input.eventName) params.set("eventName", input.eventName);
  return ceFetch<AuditEventsPage>(`/admin/audit-events?${params.toString()}`);
}

export async function getLightragDiagnostics(domainId: string, tail = 100): Promise<LightragDiagnostics> {
  const body = await ceFetch<{ diagnostics: LightragDiagnostics }>(
    `/admin/domains/${domainId}/diagnostics/lightrag?tail=${tail}`,
  );
  return body.diagnostics;
}
