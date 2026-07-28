/* Knowledge Domain wrappers over generated OpenAPI closed DTOs (P9-04 U2). */

import { ceFetch, ifMatchHeader } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";

type DomainCreateRequest = components["schemas"]["DomainCreateRequest"];

export type AdminDomain = components["schemas"]["AdminDomainDto"];
export type MemberDomain = components["schemas"]["DomainSummaryDto"];
export type DomainOperation = components["schemas"]["OperationDto"];
export type AllowedAction = components["schemas"]["AllowedAction"];

export { ifMatchHeader };

export function isDomainActionEnabled(
  domain: { allowedActions: AllowedAction[] },
  action: string,
): boolean {
  return domain.allowedActions.some((entry) => entry.action === action && entry.enabled);
}

export async function listMemberDomains(): Promise<MemberDomain[]> {
  const body = await ceFetch<components["schemas"]["MemberDomainListResponse"]>("/domains");
  return body.domains;
}

export async function listAdminDomains(): Promise<AdminDomain[]> {
  const body = await ceFetch<components["schemas"]["AdminDomainListResponse"]>("/admin/domains");
  return body.domains;
}

export async function createDomain(input: DomainCreateRequest): Promise<AdminDomain> {
  const body = await ceFetch<components["schemas"]["AdminDomainMutationResponse"]>("/admin/domains", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return body.domain;
}

export async function startDomain(domainId: string): Promise<DomainOperation> {
  const body = await ceFetch<components["schemas"]["DomainOperationMutationResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}/start`,
    { method: "POST" },
  );
  return body.operation;
}

export async function stopDomain(domainId: string): Promise<DomainOperation> {
  const body = await ceFetch<components["schemas"]["DomainOperationMutationResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}/stop`,
    { method: "POST" },
  );
  return body.operation;
}

export async function deleteDomain(
  domainId: string,
  version: number | string | null | undefined,
): Promise<DomainOperation> {
  const headers = ifMatchHeader(version);
  if (!headers) {
    throw new Error("Domain version is required for delete (If-Match).");
  }
  const body = await ceFetch<components["schemas"]["DomainOperationMutationResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}`,
    {
      method: "DELETE",
      headers,
    },
  );
  return body.operation;
}

export async function listDomainOperations(
  domainId: string,
  params: { cursor?: string | null; limit?: number } = {},
): Promise<{ operations: DomainOperation[]; nextCursor: string | null }> {
  const search = new URLSearchParams();
  if (params.cursor) search.set("cursor", params.cursor);
  if (typeof params.limit === "number") search.set("limit", String(params.limit));
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  const body = await ceFetch<components["schemas"]["AdminDomainOperationsResponse"]>(
    `/admin/domains/${encodeURIComponent(domainId)}/operations${suffix}`,
  );
  return { operations: body.operations, nextCursor: body.nextCursor };
}
