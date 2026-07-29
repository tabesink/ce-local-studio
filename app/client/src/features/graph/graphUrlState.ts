/** Approved `/database-visualize` URL keys: opaque `domain` + `node` refs only. */

export type GraphUrlState = {
  domain: string | null;
  node: string | null;
};

export function parseGraphUrlState(params: URLSearchParams): GraphUrlState {
  const domain = params.get("domain")?.trim() || null;
  const node = params.get("node")?.trim() || null;
  return { domain, node };
}

export function buildGraphHref(state: GraphUrlState): string {
  const params = new URLSearchParams();
  if (state.domain) params.set("domain", state.domain);
  if (state.node) params.set("node", state.node);
  const query = params.toString();
  return query ? `/database-visualize?${query}` : "/database-visualize";
}

export function graphUrlEquals(a: GraphUrlState, b: GraphUrlState): boolean {
  return a.domain === b.domain && a.node === b.node;
}
