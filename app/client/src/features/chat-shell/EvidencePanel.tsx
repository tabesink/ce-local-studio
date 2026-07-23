"use client";

import { useCallback, useState } from "react";
import { PanelRightClose } from "lucide-react";
import { cx } from "@/_shared/ui";
import type { EvidenceRow } from "@/features/chat-shell/types";

/* Turn-scoped Evidence Panel (F-009 context-panel-tabs v1).
   Single-column LS ComputerPanel-style aside: header + evidence rows +
   selected excerpt and an explicit unavailable document-navigation state.
   Data comes from the chat turn SSE/history; this component performs no
   fetch and never sees private source identifiers. Session ledger,
   figure/table asset cards, citation
   chips, and Source tab are deferred. */

const DEFAULT_WIDTH = 440;

type EvidencePanelProps = {
  open: boolean;
  rows: EvidenceRow[];
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  onClose: () => void;
};

export function EvidencePanel({
  open,
  rows,
  selectedEvidenceId,
  onSelectEvidence,
  onClose,
}: EvidencePanelProps) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);

  /* LS ComputerPanel left-edge resize: min max(280px, 25vw), max 65vw. */
  const startResize = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = width;
      const onMove = (move: PointerEvent) => {
        const next = startWidth + (startX - move.clientX);
        const min = Math.max(280, window.innerWidth * 0.25);
        const max = window.innerWidth * 0.65;
        setWidth(Math.round(Math.min(max, Math.max(min, next))));
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [width],
  );

  if (!open) return null;

  const selected = rows.find((row) => row.id === selectedEvidenceId) ?? rows[0] ?? null;
  const content = (
    <PanelContent
      rows={rows}
      selectedId={selected?.id ?? null}
      onSelectEvidence={onSelectEvidence}
      onClose={onClose}
    />
  );

  return (
    <>
      {/* Desktop aside */}
      <aside
        className="relative hidden h-full shrink-0 flex-col border-l border-[var(--border)]/85 bg-[var(--color-panel)] lg:flex"
        style={{ width: `${width}px` }}
        aria-label="Evidence"
      >
        <div
          role="separator"
          aria-orientation="vertical"
          onPointerDown={startResize}
          className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-[var(--link)]/50"
        />
        {content}
      </aside>

      {/* Mobile slide-over */}
      <div className="fixed inset-0 z-50 bg-black/20 lg:hidden" onClick={onClose} aria-hidden>
        <div
          className="ml-auto flex h-full w-[min(100vw,400px)] flex-col border-l border-[var(--border)] bg-[var(--color-panel)]"
          onClick={(event) => event.stopPropagation()}
        >
          {content}
        </div>
      </div>
    </>
  );
}

function PanelContent({
  rows,
  selectedId,
  onSelectEvidence,
  onClose,
}: {
  rows: EvidenceRow[];
  selectedId: string | null;
  onSelectEvidence: (id: string) => void;
  onClose: () => void;
}) {
  const selected = rows.find((row) => row.id === selectedId) ?? null;
  return (
    <>
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-[var(--border)]/85 bg-[var(--color-header)] px-3">
        <span className="text-[length:var(--fs-sm)] font-medium text-[var(--fg)]">
          Evidence
          {rows.length > 0 ? <span className="ml-1.5 text-[var(--dim)]">({rows.length})</span> : null}
        </span>
        <button
          type="button"
          onClick={onClose}
          title="Close evidence panel"
          aria-label="Close evidence panel"
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {rows.length === 0 ? (
          <p className="px-1 text-[length:var(--fs-sm)] leading-6 text-[var(--dim)]">
            Retrieved evidence for this answer appears here after a domain query.
          </p>
        ) : (
          <div className="space-y-4">
            <section>
              <p className="px-1 font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
                Sources
              </p>
              <ul className="mt-1.5 space-y-1">
                {rows.map((row) => {
                  const active = row.id === selectedId;
                  return (
                    <li key={row.id}>
                      <button
                        type="button"
                        onClick={() => onSelectEvidence(row.id)}
                        aria-pressed={active}
                        className={cx(
                          "flex w-full items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                          active
                            ? "border-[var(--border)]/70 bg-[var(--surface)]/60 text-[var(--fg)]"
                            : "border-transparent text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]",
                        )}
                      >
                        {row.citationLabel ? (
                          <span className="shrink-0 font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                            [{row.citationLabel}]
                          </span>
                        ) : null}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[length:var(--fs-sm)]">
                            {row.sourceLabel ?? "Untitled source"}
                          </span>
                          {row.excerpt ? (
                            <span className="mt-0.5 line-clamp-2 block text-[length:var(--fs-xs)] leading-5 text-[var(--dim)]/80">
                              {row.excerpt}
                            </span>
                          ) : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>

            {selected ? (
              <section data-testid="evidence-selected-detail">
                <p className="px-1 font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
                  Excerpt
                </p>
                <div className="mt-1.5 rounded-md border border-[var(--border)]/50 bg-[var(--surface)]/30 px-3 py-2.5">
                  <div className="flex items-center gap-2 font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                    {selected.citationLabel ? <span>[{selected.citationLabel}]</span> : null}
                    {selected.sourceLabel ? <span className="truncate">{selected.sourceLabel}</span> : null}
                  </div>
                  <p className="mt-1.5 whitespace-pre-wrap text-[length:var(--fs-sm)] leading-6 text-[var(--fg)]/90">
                    {selected.excerpt ?? "No excerpt is available for this evidence."}
                  </p>
                </div>
                <p
                  role="status"
                  data-testid="document-navigation-unavailable"
                  className="mt-2 px-1 text-[length:var(--fs-sm)] leading-5 text-[var(--dim)]"
                >
                  Document navigation is unavailable until governed evidence-location and
                  document-content routes are implemented.
                </p>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </>
  );
}
