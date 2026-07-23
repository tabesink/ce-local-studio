/* CE adapter for the currently contracted P4/P5 administrator source operations:

   GET    /api/v1/admin/domains/{domainId}/sources            (admin list/mutations)
   POST   /api/v1/admin/domains/{domainId}/sources           (multipart file)
   POST   .../sources/{sourceId}/retry | /cancel             (preparation)
   POST   .../sources/{sourceId}/index/retry | /index/cancel (indexing)
   DELETE .../sources/{sourceId}
*/

import { ceFetch } from "@/lib/api/client";

export type SourceDocument = {
  id: string;
  domainId: string;
  originalFilename: string;
  contentType: string;
  originalSizeBytes: number;
  originalSha256: string;
  state: string;
  parserKind: string;
  blockCount: number;
  imageCount: number;
  indexState: string;
  indexErrorCode: string | null;
  indexErrorMessage: string | null;
  indexAcceptedAt: string | null;
  indexReadyAt: string | null;
  indexUpdatedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type SourceOperation = {
  id: string;
  operationType: string;
  status: string;
  message: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
};

export async function listAdminSources(domainId: string): Promise<SourceDocument[]> {
  const body = await ceFetch<{ sources: SourceDocument[] }>(`/admin/domains/${domainId}/sources`);
  return body.sources;
}

export async function uploadSource(
  domainId: string,
  file: File,
): Promise<{ source: SourceDocument; operation: SourceOperation }> {
  const form = new FormData();
  form.append("file", file);
  return ceFetch<{ source: SourceDocument; operation: SourceOperation }>(`/admin/domains/${domainId}/sources`, {
    method: "POST",
    body: form,
  });
}

export async function retrySourcePreparation(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(`/admin/domains/${domainId}/sources/${sourceId}/retry`, { method: "POST" });
}

export async function cancelSourcePreparation(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(`/admin/domains/${domainId}/sources/${sourceId}/cancel`, { method: "POST" });
}

export async function retrySourceIndex(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(`/admin/domains/${domainId}/sources/${sourceId}/index/retry`, { method: "POST" });
}

export async function cancelSourceIndex(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<unknown>(`/admin/domains/${domainId}/sources/${sourceId}/index/cancel`, { method: "POST" });
}

export async function deleteSource(domainId: string, sourceId: string): Promise<void> {
  await ceFetch<void>(`/admin/domains/${domainId}/sources/${sourceId}`, { method: "DELETE" });
}
