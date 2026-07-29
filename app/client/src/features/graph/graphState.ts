import type { MemberDomain } from "@/features/domains/api";
import type { GraphLabel, GraphNode, GraphSnapshot } from "@/features/graph/api";

export type GraphSafeError = {
  code: string;
  message: string;
  requestId: string | null;
};

export type GraphPhase =
  | "boot"
  | "empty_domains"
  | "loading"
  | "ready"
  | "refreshing"
  | "error";

export type GraphWorkbenchState = {
  phase: GraphPhase;
  domains: MemberDomain[];
  domainId: string | null;
  snapshot: GraphSnapshot | null;
  selectedNodeRef: string | null;
  filterQuery: string;
  remoteLabels: GraphLabel[] | null;
  remoteSearchPending: boolean;
  announcement: string;
  error: GraphSafeError | null;
  requestGeneration: number;
};

export type GraphWorkbenchAction =
  | { type: "domains_loaded"; domains: MemberDomain[]; preferredDomainId: string | null }
  | { type: "domains_failed"; error: GraphSafeError }
  | { type: "select_domain"; domainId: string }
  | { type: "reload_snapshot" }
  | { type: "snapshot_loading"; generation: number }
  | { type: "snapshot_ready"; generation: number; snapshot: GraphSnapshot; preferredNodeRef: string | null }
  | { type: "snapshot_refreshing"; generation: number }
  | { type: "snapshot_failed"; generation: number; error: GraphSafeError; clearGraph: boolean }
  | { type: "select_node"; nodeRef: string | null }
  | { type: "set_filter"; query: string }
  | { type: "remote_search_pending" }
  | { type: "remote_search_ready"; items: GraphLabel[] }
  | { type: "remote_search_cleared" }
  | { type: "announce"; message: string }
  | { type: "identity_cleared" };

export const initialGraphState: GraphWorkbenchState = {
  phase: "boot",
  domains: [],
  domainId: null,
  snapshot: null,
  selectedNodeRef: null,
  filterQuery: "",
  remoteLabels: null,
  remoteSearchPending: false,
  announcement: "",
  error: null,
  requestGeneration: 0,
};

function eligibleDomains(domains: MemberDomain[]): MemberDomain[] {
  return domains.filter((domain) => domain.queryEligible && domain.state === "running");
}

export function pickInitialDomain(
  domains: MemberDomain[],
  preferredDomainId: string | null,
): string | null {
  const eligible = eligibleDomains(domains);
  if (preferredDomainId && eligible.some((domain) => domain.id === preferredDomainId)) {
    return preferredDomainId;
  }
  return eligible[0]?.id ?? null;
}

export function graphReducer(
  state: GraphWorkbenchState,
  action: GraphWorkbenchAction,
): GraphWorkbenchState {
  switch (action.type) {
    case "domains_loaded": {
      const domainId = pickInitialDomain(action.domains, action.preferredDomainId);
      if (!domainId) {
        return {
          ...initialGraphState,
          phase: "empty_domains",
          domains: action.domains,
          announcement: "No query-eligible knowledge domains are available for graph viewing.",
        };
      }
      return {
        ...state,
        phase: "loading",
        domains: action.domains,
        domainId,
        snapshot: null,
        selectedNodeRef: null,
        filterQuery: "",
        remoteLabels: null,
        remoteSearchPending: false,
        error: null,
        announcement: "Loading knowledge graph.",
        requestGeneration: state.requestGeneration + 1,
      };
    }
    case "domains_failed":
      return {
        ...initialGraphState,
        phase: "error",
        error: action.error,
        announcement: action.error.message,
      };
    case "select_domain": {
      if (action.domainId === state.domainId) return state;
      return {
        ...state,
        phase: "loading",
        domainId: action.domainId,
        snapshot: null,
        selectedNodeRef: null,
        filterQuery: "",
        remoteLabels: null,
        remoteSearchPending: false,
        error: null,
        announcement: "Loading knowledge graph for the selected domain.",
        requestGeneration: state.requestGeneration + 1,
      };
    }
    case "reload_snapshot": {
      if (!state.domainId) return state;
      return {
        ...state,
        phase: state.snapshot ? "refreshing" : "loading",
        error: null,
        announcement: "Refreshing knowledge graph.",
        requestGeneration: state.requestGeneration + 1,
      };
    }
    case "snapshot_loading":
      if (action.generation !== state.requestGeneration) return state;
      return {
        ...state,
        phase: state.snapshot ? "refreshing" : "loading",
        error: null,
      };
    case "snapshot_refreshing":
      if (action.generation !== state.requestGeneration) return state;
      return { ...state, phase: "refreshing", error: null };
    case "snapshot_ready": {
      if (action.generation !== state.requestGeneration) return state;
      const nodes = action.snapshot.nodes;
      const preferred =
        action.preferredNodeRef && nodes.some((node) => node.ref === action.preferredNodeRef)
          ? action.preferredNodeRef
          : state.selectedNodeRef && nodes.some((node) => node.ref === state.selectedNodeRef)
            ? state.selectedNodeRef
            : null;
      const count = nodes.length;
      const truncatedNote = action.snapshot.truncated
        ? " Showing a bounded neighborhood; search still covers authorized labels."
        : "";
      return {
        ...state,
        phase: "ready",
        snapshot: action.snapshot,
        selectedNodeRef: preferred,
        error: null,
        announcement: `Loaded ${count} node${count === 1 ? "" : "s"}.${truncatedNote}`,
      };
    }
    case "snapshot_failed": {
      if (action.generation !== state.requestGeneration) return state;
      return {
        ...state,
        phase: "error",
        snapshot: action.clearGraph ? null : state.snapshot,
        selectedNodeRef: action.clearGraph ? null : state.selectedNodeRef,
        error: action.error,
        announcement: action.error.message,
      };
    }
    case "select_node":
      return {
        ...state,
        selectedNodeRef: action.nodeRef,
        announcement: action.nodeRef
          ? `Selected ${nodeLabel(state.snapshot, action.nodeRef)}.`
          : "Cleared node selection.",
      };
    case "set_filter":
      return { ...state, filterQuery: action.query };
    case "remote_search_pending":
      return { ...state, remoteSearchPending: true };
    case "remote_search_ready":
      return {
        ...state,
        remoteSearchPending: false,
        remoteLabels: action.items,
        announcement:
          action.items.length === 0
            ? "No matching node was found in the authorized domain."
            : `Found ${action.items.length} matching label${action.items.length === 1 ? "" : "s"}.`,
      };
    case "remote_search_cleared":
      return { ...state, remoteSearchPending: false, remoteLabels: null };
    case "announce":
      return { ...state, announcement: action.message };
    case "identity_cleared":
      return { ...initialGraphState, announcement: "Signed out. Graph projection cleared." };
    default:
      return state;
  }
}

function nodeLabel(snapshot: GraphSnapshot | null, nodeRef: string): string {
  return snapshot?.nodes.find((node) => node.ref === nodeRef)?.label ?? "node";
}

export function selectedNode(state: GraphWorkbenchState): GraphNode | null {
  if (!state.snapshot || !state.selectedNodeRef) return null;
  return state.snapshot.nodes.find((node) => node.ref === state.selectedNodeRef) ?? null;
}

export function connectedEdges(state: GraphWorkbenchState, nodeRef: string) {
  if (!state.snapshot) return [];
  return state.snapshot.edges.filter(
    (edge) => edge.sourceRef === nodeRef || edge.targetRef === nodeRef,
  );
}

export function filterLocalNodes(nodes: GraphNode[], query: string): GraphNode[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return nodes;
  return nodes.filter(
    (node) =>
      node.label.toLowerCase().includes(needle) ||
      (node.kind?.toLowerCase().includes(needle) ?? false),
  );
}

export function shouldClearGraphOnError(code: string): boolean {
  return (
    code === "not_found" ||
    code === "domain_not_query_eligible" ||
    code === "graph_refreshing" ||
    code === "forbidden" ||
    code === "unauthenticated" ||
    code === "session_expired"
  );
}
