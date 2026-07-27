"use client";

import { Network } from "lucide-react";
import { PageHeader } from "@/_shared/ui";

/**
 * Reserved `/database-visualize` shell (P9-03 / DRIFT-04).
 * Deliberate unavailable surface with zero product-data requests —
 * no domains list, graph API, or runtime fetches.
 */
export function GraphPage() {
  return (
    <div className="flex h-full min-h-0 flex-col px-4 py-5 sm:px-6" data-testid="graph-unavailable">
      <PageHeader eyebrow="Knowledge graph" title="Graph" />
      <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-[var(--ui-border)] bg-[var(--ui-surface)]/40">
        <div className="max-w-md p-6 text-center">
          <Network className="mx-auto mb-3 h-8 w-8 text-[var(--dim)]" strokeWidth={1.5} />
          <h2 className="text-[length:var(--fs-lg)] font-medium text-[var(--fg)]">
            Graph visualization is not available
          </h2>
          <p className="mt-2 text-[length:var(--fs-sm)] leading-relaxed text-[var(--dim)]">
            The knowledge graph route stays deliberately unavailable until a versioned graph API and data
            contracts are approved. This page makes no product-data requests.
          </p>
        </div>
      </div>
    </div>
  );
}
