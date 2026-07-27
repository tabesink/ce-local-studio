/* Thin adapters over generated OpenAPI components for member documents
   and administrator source operations (P9-03).

   Member:
     GET /documents
     GET /documents/{documentRef}
     GET /documents/{documentRef}/content
     GET /evidence/{evidenceRef}/location

   Admin:
     GET/POST/DELETE /admin/domains/{domainId}/sources…
     GET …/sources/{sourceId}/outline
*/

import { ceFetch, ceFetchBlob } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";

export type DocumentSummary = components["schemas"]["DocumentSummaryDto"];
export type AdminSource = components["schemas"]["AdminSourceDto"];
export type OutlineItem = components["schemas"]["OutlineItemDto"];
export type EvidenceLocation = components["schemas"]["EvidenceLocationResponseDto"];
export type OperationDto = components["schemas"]["OperationDto"];
export type AllowedAction = components["schemas"]["AllowedAction"];

export type ListDocumentsParams = {
  domainId?: string | null;
  query?: string | null;
  cursor?: string | null;
  limit?: number;
};

export type FetchDocumentContentOptions = {
  range?: string | null;
  signal?: AbortSignal;
};

function ifMatchHeader(version: number | string | null | undefined): Record<string, string> | undefined {
  if (version == null || version === "") return undefined;
  return { "If-Match": `"${version}"` };
}

function actionEnabled(source: AdminSource, action: string): boolean {
  return source.allowedActions.some((entry) => entry.action === action && entry.enabled);
}

export function isAdminActionEnabled(source: AdminSource, action: string): boolean {
  return actionEnabled(source, action);
}

export async function listDocuments(
  params: ListDocumentsParams = {},
): Promise<{ documents: DocumentSummary[]; nextCursor: string | null }> {
  const search = new URLSearchParams();
  if (params.domainId) search.set("domainId", params.domainId);
  if (params.query) search.set("query", params.query);
  if (params.cursor) search.set("cursor", params.cursor);
  if (typeof params.limit === "number") search.set("limit", String(params.limit));
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  const body = await ceFetch<components["schemas"]["DocumentsListResponse"]>(`/documents${suffix}`);
  return { documents: body.documents, nextCursor: body.nextCursor };
}

export async function getDocument(documentRef: string): Promise<DocumentSummary> {
  const body = await ceFetch<components["schemas"]["DocumentDetailResponse"]>(
    `/documents/${encodeURIComponent(documentRef)}`,
  );
  return body.document;
}

export async function fetchDocumentContent(
  documentRef: string,
  options: FetchDocumentContentOptions = {},
): Promise<{ blob: Blob; contentType: string }> {
  const headers: Record<string, string> = {};
  if (options.range) headers.Range = options.range;
  return ceFetchBlob(`/documents/${encodeURIComponent(documentRef)}/content`, {
    headers,
    signal: options.signal,
  });
}

export async function getEvidenceLocation(evidenceRef: string): Promise<EvidenceLocation> {
  return ceFetch<EvidenceLocation>(`/evidence/${encodeURIComponent(evidenceRef)}/location`);
}

export async function listAdminSources(domainId: string): Promise<AdminSource[]> {
  const body = await ceFetch<components["schemas"]["AdminSourceListResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources`,
  );
  return body.sources;
}

export async function uploadSource(
  domainId: string,
  file: File,
): Promise<{ source?: AdminSource; operation?: OperationDto }> {
  const form = new FormData();
  form.append("file", file);
  return ceFetch<{ source?: AdminSource; operation?: OperationDto }>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources`,
    {
      method: "POST",
      body: form,
    },
  );
}

export async function retrySourcePreparation(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}/retry`,
    { method: "POST" },
  );
}

export async function cancelSourcePreparation(
  domainId: string,
  sourceId: string,
  version: number,
): Promise<void> {
  await ceFetch<unknown>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}/cancel`,
    {
      method: "POST",
      headers: ifMatchHeader(version),
    },
  );
}

export async function retrySourceIndex(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}/index/retry`,
    { method: "POST" },
  );
}

export async function cancelSourceIndex(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}/index/cancel`,
    { method: "POST" },
  );
}

export async function deleteSource(domainId: string, sourceId: string, version: number): Promise<void> {
  await ceFetch<void>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}`,
    {
      method: "DELETE",
      headers: ifMatchHeader(version),
    },
  );
}

export async function getSourceOutline(domainId: string, sourceId: string): Promise<OutlineItem[]> {
  const body = await ceFetch<components["schemas"]["AdminSourceOutlineResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}/sources/${encodeURIComponent(sourceId)}/outline`,
  );
  return body.items;
}
