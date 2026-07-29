"use client";

import { SearchInput } from "@/_shared/ui";
import type { GraphLabel, GraphNode } from "@/features/graph/api";

export function GraphNodeBrowser({
  nodes,
  remoteLabels,
  selectedNodeRef,
  filterQuery,
  remoteSearchPending,
  onFilterChange,
  onSelectNode,
  onSelectRemoteLabel,
}: {
  nodes: GraphNode[];
  remoteLabels: GraphLabel[] | null;
  selectedNodeRef: string | null;
  filterQuery: string;
  remoteSearchPending: boolean;
  onFilterChange: (query: string) => void;
  onSelectNode: (nodeRef: string) => void;
  onSelectRemoteLabel: (label: GraphLabel) => void;
}) {
  const showRemote = remoteLabels !== null && filterQuery.trim().length >= 2;

  return (
    <section
      className="flex h-full min-h-0 w-full flex-col gap-3"
      data-testid="graph-node-browser"
      aria-label="Graph nodes"
    >
      <label className="flex flex-col gap-1.5 text-[length:var(--fs-xs)] text-[var(--dim)]">
        <span>Search nodes</span>
        <SearchInput
          value={filterQuery}
          onChange={onFilterChange}
          placeholder="Filter or search labels"
        />
      </label>
      {remoteSearchPending ? (
        <p className="text-[length:var(--fs-xs)] text-[var(--dim)]" role="status">
          Searching authorized labels…
        </p>
      ) : null}
      <ul
        className="min-h-0 flex-1 overflow-y-auto rounded-md border border-[var(--ui-border)]"
        data-testid="graph-node-list"
      >
        {showRemote
          ? remoteLabels.map((item) => (
              <li key={item.nodeRef}>
                <button
                  type="button"
                  className="flex w-full flex-col items-start gap-0.5 border-b border-[var(--ui-border)] px-3 py-2 text-left text-[length:var(--fs-sm)] hover:bg-[var(--ui-fg)]/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
                  aria-current={selectedNodeRef === item.nodeRef ? "true" : undefined}
                  onClick={() => onSelectRemoteLabel(item)}
                >
                  <span className="font-medium text-[var(--fg)]">{item.label}</span>
                  <span className="text-[length:var(--fs-xs)] text-[var(--dim)]">
                    {item.kind ?? "entity"} · server match
                  </span>
                </button>
              </li>
            ))
          : nodes.map((node) => (
              <li key={node.ref}>
                <button
                  type="button"
                  className="flex w-full flex-col items-start gap-0.5 border-b border-[var(--ui-border)] px-3 py-2 text-left text-[length:var(--fs-sm)] hover:bg-[var(--ui-fg)]/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
                  aria-current={selectedNodeRef === node.ref ? "true" : undefined}
                  onClick={() => onSelectNode(node.ref)}
                >
                  <span className="font-medium text-[var(--fg)]">{node.label}</span>
                  <span className="text-[length:var(--fs-xs)] text-[var(--dim)]">
                    {node.kind ?? "entity"} · degree {node.degree}
                  </span>
                </button>
              </li>
            ))}
        {showRemote && remoteLabels.length === 0 ? (
          <li className="px-3 py-4 text-[length:var(--fs-sm)] text-[var(--dim)]">
            No matching node was found in the authorized domain.
          </li>
        ) : null}
        {!showRemote && nodes.length === 0 ? (
          <li className="px-3 py-4 text-[length:var(--fs-sm)] text-[var(--dim)]">
            No nodes in the current bounded snapshot.
          </li>
        ) : null}
      </ul>
    </section>
  );
}
