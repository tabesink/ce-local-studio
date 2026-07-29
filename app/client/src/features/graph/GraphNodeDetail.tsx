"use client";

import { Button } from "@/ui/Button";
import type { GraphEdge, GraphNode, GraphSnapshot } from "@/features/graph/api";

function neighborLabel(snapshot: GraphSnapshot, edge: GraphEdge, nodeRef: string): string {
  const otherRef = edge.sourceRef === nodeRef ? edge.targetRef : edge.sourceRef;
  return snapshot.nodes.find((node) => node.ref === otherRef)?.label ?? "Related node";
}

export function GraphNodeDetail({
  snapshot,
  node,
  edges,
  onSelectNeighbor,
  onClose,
}: {
  snapshot: GraphSnapshot;
  node: GraphNode;
  edges: GraphEdge[];
  onSelectNeighbor: (nodeRef: string) => void;
  onClose: () => void;
}) {
  return (
    <aside
      className="flex h-full min-h-0 w-full flex-col gap-3"
      data-testid="graph-node-detail"
      aria-label="Node detail"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-[length:var(--fs-md)] font-medium text-[var(--fg)]">{node.label}</h2>
          <p className="mt-1 text-[length:var(--fs-xs)] text-[var(--dim)]">
            {node.kind ?? "entity"} · degree {node.degree}
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose} aria-label="Close node detail">
          Close
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <h3 className="mb-2 text-[length:var(--fs-xs)] font-medium uppercase tracking-wide text-[var(--dim)]">
          Connected relations
        </h3>
        {edges.length === 0 ? (
          <p className="text-[length:var(--fs-sm)] text-[var(--dim)]">No connected relations in this snapshot.</p>
        ) : (
          <ul className="space-y-1">
            {edges.map((edge) => {
              const neighborRef = edge.sourceRef === node.ref ? edge.targetRef : edge.sourceRef;
              return (
                <li key={edge.ref}>
                  <button
                    type="button"
                    className="w-full rounded-md border border-[var(--ui-border)] px-3 py-2 text-left text-[length:var(--fs-sm)] hover:bg-[var(--ui-fg)]/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
                    onClick={() => onSelectNeighbor(neighborRef)}
                  >
                    <span className="text-[var(--fg)]">{neighborLabel(snapshot, edge, node.ref)}</span>
                    {edge.label ? (
                      <span className="mt-0.5 block text-[length:var(--fs-xs)] text-[var(--dim)]">{edge.label}</span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
