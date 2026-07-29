import Graph from "graphology";
import type { GraphEdge, GraphNode } from "@/features/graph/api";

export type GraphologyAttributes = {
  label: string;
  kind: string | null;
  degree: number;
  size: number;
  color: string;
  x: number;
  y: number;
};

function kindColor(kind: string | null): string {
  const key = (kind ?? "entity").toLowerCase();
  if (key.includes("equipment") || key.includes("asset")) return "var(--accent)";
  if (key.includes("person") || key.includes("org")) return "var(--ui-info, var(--accent))";
  if (key.includes("location") || key.includes("site")) return "var(--ui-success, var(--accent))";
  return "var(--fg)";
}

/** Deterministic circular layout — presentation only; never persisted. */
export function buildGraphologyGraph(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  const graph = new Graph({ multi: false, allowSelfLoops: false, type: "undirected" });
  const count = Math.max(nodes.length, 1);
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / count;
    const radius = 40 + Math.min(node.degree, 12) * 2;
    graph.addNode(node.ref, {
      label: node.label,
      kind: node.kind,
      degree: node.degree,
      size: 4 + Math.min(node.degree, 10),
      color: kindColor(node.kind),
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    } satisfies GraphologyAttributes);
  });
  for (const edge of edges) {
    if (!graph.hasNode(edge.sourceRef) || !graph.hasNode(edge.targetRef)) continue;
    if (graph.hasEdge(edge.sourceRef, edge.targetRef)) continue;
    graph.addEdgeWithKey(edge.ref, edge.sourceRef, edge.targetRef, {
      label: edge.label ?? undefined,
      size: 1,
      color: "var(--ui-border)",
    });
  }
  return graph;
}
