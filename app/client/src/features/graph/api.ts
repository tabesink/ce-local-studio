/* Generated OpenAPI graph reads through the same-origin BFF (P12-07 U9/U10). */

import { ceFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/openapi";

export type GraphSnapshot = components["schemas"]["GraphSnapshotDto"];
export type GraphNode = components["schemas"]["GraphNodeDto"];
export type GraphEdge = components["schemas"]["GraphEdgeDto"];
export type GraphLabel = components["schemas"]["GraphLabelDto"];
export type GraphLabelSearch = components["schemas"]["GraphLabelSearchDto"];

export async function fetchDomainGraph(
  domainId: string,
  options: { label?: string | null; signal?: AbortSignal } = {},
): Promise<GraphSnapshot> {
  const search = new URLSearchParams();
  const label = options.label?.trim();
  if (label) search.set("label", label);
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return ceFetch<GraphSnapshot>(`/domains/${encodeURIComponent(domainId)}/graph${suffix}`, {
    signal: options.signal,
  });
}

export async function searchDomainGraphLabels(
  domainId: string,
  options: { q: string; limit?: number; signal?: AbortSignal },
): Promise<GraphLabelSearch> {
  const search = new URLSearchParams();
  search.set("q", options.q.trim());
  if (typeof options.limit === "number") search.set("limit", String(options.limit));
  return ceFetch<GraphLabelSearch>(
    `/domains/${encodeURIComponent(domainId)}/graph/labels?${search.toString()}`,
    { signal: options.signal },
  );
}
