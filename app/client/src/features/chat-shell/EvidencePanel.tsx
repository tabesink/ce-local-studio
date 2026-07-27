"use client";

import { useCallback, useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useRouter } from "next/navigation";
import { PanelRightClose } from "lucide-react";
import { cx } from "@/lib/cx";
import { Button } from "@/ui";
import type { AcceptedRef } from "@/features/chat-shell/api";
import type { EvidenceRow } from "@/features/chat-shell/types";
import {
  buildDocumentsDeepLinkHref,
  isOpenInLibraryEnabled,
  LIBRARY_SURFACE_AVAILABLE,
} from "@/features/chat-shell/documentsDeepLink";

/* Turn-scoped inspector (Evidence | Refs | Source).
   Data comes from the chat turn SSE/history; this component performs no
   fetch and never sees private source identifiers. */

const DEFAULT_WIDTH = 440;
const DRAWER_MQ = "(max-width: 1023px)";

type InspectorTab = "evidence" | "refs" | "source";

type EvidencePanelProps = {
  open: boolean;
  rows: EvidenceRow[];
  acceptedRefs: AcceptedRef[];
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  onClose: () => void;
};

export function EvidencePanel({
  open,
  rows,
  acceptedRefs,
  selectedEvidenceId,
  onSelectEvidence,
  onClose,
}: EvidencePanelProps) {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [tab, setTab] = useState<InspectorTab>("evidence");
  const [isDrawer, setIsDrawer] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
    return window.matchMedia(DRAWER_MQ).matches;
  });
  const panelRef = useRef<HTMLElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const setPanelNode = useCallback((node: HTMLElement | null) => {
    panelRef.current = node;
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(DRAWER_MQ);
    const sync = () => setIsDrawer(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const node = panelRef.current;
    const focusable = node?.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
    return () => {
      returnFocusRef.current?.focus();
      returnFocusRef.current = null;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !isDrawer) return;
    const node = panelRef.current;
    if (!node) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        node.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey) {
        if (active === first || !node.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isDrawer, onClose, open]);

  /* LS ComputerPanel left-edge resize: min max(280px, 25vw), max 65vw. */
  const startResize = useCallback(
    (event: ReactPointerEvent) => {
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
  const panelProps = {
    tab,
    onTabChange: setTab,
    rows,
    acceptedRefs,
    selectedId: selected?.id ?? null,
    onSelectEvidence,
    onClose,
    titleId,
  };

  if (isDrawer) {
    return (
      <div className="fixed inset-0 z-50 flex justify-end">
        <button
          type="button"
          className="absolute inset-0 h-full w-full bg-black/20"
          aria-label="Close evidence panel"
          onClick={onClose}
        />
        <div
          ref={setPanelNode}
          role="dialog"
          aria-modal="true"
          aria-label="Evidence"
          aria-labelledby={titleId}
          className="relative flex h-full w-[min(100vw,400px)] flex-col border-l border-[var(--border)] bg-[var(--color-panel)]"
        >
          <PanelContent {...panelProps} />
        </div>
      </div>
    );
  }

  return (
    <aside
      ref={setPanelNode}
      role="complementary"
      className="relative flex h-full shrink-0 flex-col border-l border-[var(--border)]/85 bg-[var(--color-panel)]"
      style={{ width: `${width}px` }}
      aria-label="Evidence"
    >
      <div
        role="separator"
        aria-orientation="vertical"
        onPointerDown={startResize}
        className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-[var(--link)]/50"
      />
      <PanelContent {...panelProps} />
    </aside>
  );
}

function PanelContent({
  tab,
  onTabChange,
  rows,
  acceptedRefs,
  selectedId,
  onSelectEvidence,
  onClose,
  titleId,
}: {
  tab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
  rows: EvidenceRow[];
  acceptedRefs: AcceptedRef[];
  selectedId: string | null;
  onSelectEvidence: (id: string) => void;
  onClose: () => void;
  titleId: string;
}) {
  const selected = rows.find((row) => row.id === selectedId) ?? null;
  const libraryHref = selected
    ? buildDocumentsDeepLinkHref({
        documentRef: selected.documentRef,
        evidenceRef: selected.id,
        page: selected.anchor?.pageNumber,
      })
    : null;
  const libraryEnabled = isOpenInLibraryEnabled(libraryHref, LIBRARY_SURFACE_AVAILABLE);

  return (
    <>
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-[var(--border)]/85 bg-[var(--color-header)] px-3">
        <span id={titleId} className="text-[length:var(--fs-sm)] font-medium text-[var(--fg)]">
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

      <div role="tablist" aria-label="Inspector tabs" className="flex shrink-0 gap-1 border-b border-[var(--border)]/60 px-2 py-1.5">
        <button
          type="button"
          role="tab"
          id="inspector-tab-evidence"
          data-testid="inspector-tab-evidence"
          aria-selected={tab === "evidence"}
          tabIndex={tab === "evidence" ? 0 : -1}
          onClick={() => onTabChange("evidence")}
          className={cx(
            "rounded-md px-2.5 py-1 text-[length:var(--fs-sm)] transition-colors",
            tab === "evidence"
              ? "bg-[var(--surface)]/70 text-[var(--fg)]"
              : "text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]",
          )}
        >
          Evidence
        </button>
        <button
          type="button"
          role="tab"
          id="inspector-tab-refs"
          data-testid="inspector-tab-refs"
          aria-selected={tab === "refs"}
          tabIndex={tab === "refs" ? 0 : -1}
          onClick={() => onTabChange("refs")}
          className={cx(
            "rounded-md px-2.5 py-1 text-[length:var(--fs-sm)] transition-colors",
            tab === "refs"
              ? "bg-[var(--surface)]/70 text-[var(--fg)]"
              : "text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]",
          )}
        >
          Refs
        </button>
        <button
          type="button"
          role="tab"
          id="inspector-tab-source"
          data-testid="inspector-tab-source"
          aria-selected={tab === "source"}
          tabIndex={tab === "source" ? 0 : -1}
          onClick={() => onTabChange("source")}
          className={cx(
            "rounded-md px-2.5 py-1 text-[length:var(--fs-sm)] transition-colors",
            tab === "source"
              ? "bg-[var(--surface)]/70 text-[var(--fg)]"
              : "text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]",
          )}
        >
          Source
        </button>
      </div>

      <div
        className="min-h-0 flex-1 overflow-y-auto p-3"
        role="tabpanel"
        aria-labelledby={
          tab === "evidence"
            ? "inspector-tab-evidence"
            : tab === "refs"
              ? "inspector-tab-refs"
              : "inspector-tab-source"
        }
      >
        {tab === "evidence" ? (
          <EvidenceTab
            rows={rows}
            selectedId={selectedId}
            onSelectEvidence={onSelectEvidence}
            selected={selected}
          />
        ) : null}
        {tab === "refs" ? <RefsTab acceptedRefs={acceptedRefs} /> : null}
        {tab === "source" ? (
          <SourceTab
            selected={selected}
            libraryHref={libraryHref}
            libraryEnabled={libraryEnabled}
          />
        ) : null}
      </div>
    </>
  );
}

function EvidenceTab({
  rows,
  selectedId,
  onSelectEvidence,
  selected,
}: {
  rows: EvidenceRow[];
  selectedId: string | null;
  onSelectEvidence: (id: string) => void;
  selected: EvidenceRow | null;
}) {
  if (rows.length === 0) {
    return (
      <p className="px-1 text-[length:var(--fs-sm)] leading-6 text-[var(--dim)]">
        Retrieved evidence for this answer appears here after a domain query.
      </p>
    );
  }

  return (
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
                  data-testid={`evidence-card-${row.id}`}
                  onClick={() => onSelectEvidence(row.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectEvidence(row.id);
                    }
                  }}
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
        </section>
      ) : null}
    </div>
  );
}

function RefsTab({ acceptedRefs }: { acceptedRefs: AcceptedRef[] }) {
  if (acceptedRefs.length === 0) {
    return (
      <p className="px-1 text-[length:var(--fs-sm)] leading-6 text-[var(--dim)]">
        Accepted references for this turn appear here when the answer used governed context.
      </p>
    );
  }

  return (
    <ul className="space-y-1.5">
      {acceptedRefs.map((ref) => (
        <li
          key={ref.id}
          className="rounded-md border border-[var(--border)]/50 bg-[var(--surface)]/30 px-3 py-2"
        >
          <div className="flex items-center gap-2 font-mono text-[length:var(--fs-xs)] uppercase text-[var(--dim)]">
            <span>{ref.kind}</span>
            <span className="text-[var(--dim)]/50">#{ref.order}</span>
          </div>
          <p className="mt-1 truncate text-[length:var(--fs-sm)] text-[var(--fg)]">{ref.label}</p>
          {ref.description ? (
            <p className="mt-0.5 text-[length:var(--fs-xs)] leading-5 text-[var(--dim)]">{ref.description}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function SourceTab({
  selected,
  libraryHref,
  libraryEnabled,
}: {
  selected: EvidenceRow | null;
  libraryHref: string | null;
  libraryEnabled: boolean;
}) {
  const router = useRouter();

  if (!selected) {
    return (
      <p className="px-1 text-[length:var(--fs-sm)] leading-6 text-[var(--dim)]">
        Select evidence to view its source document metadata.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <section className="rounded-md border border-[var(--border)]/50 bg-[var(--surface)]/30 px-3 py-2.5">
        <p className="font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
          Document
        </p>
        <p className="mt-1.5 text-[length:var(--fs-sm)] text-[var(--fg)]">
          {selected.documentLabel || selected.sourceLabel || "Untitled document"}
        </p>
        <dl className="mt-2 space-y-1 font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
          <div className="flex gap-2">
            <dt className="shrink-0">Kind</dt>
            <dd>{selected.kind}</dd>
          </div>
          {typeof selected.anchor?.pageNumber === "number" ? (
            <div className="flex gap-2">
              <dt className="shrink-0">Page</dt>
              <dd>{selected.anchor.pageNumber}</dd>
            </div>
          ) : null}
          {selected.anchor?.sectionLabel ? (
            <div className="flex gap-2">
              <dt className="shrink-0">Section</dt>
              <dd className="truncate">{selected.anchor.sectionLabel}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          data-testid="open-in-library"
          disabled={!libraryEnabled}
          title={
            libraryEnabled
              ? "Open in Library"
              : !libraryHref
                ? "Open in Library unavailable — missing document or evidence reference"
                : "Open in Library is unavailable until the documents library is ready"
          }
          aria-disabled={!libraryEnabled}
          onClick={(event) => {
            event.preventDefault();
            if (libraryEnabled && libraryHref) {
              router.push(libraryHref);
            }
          }}
        >
          Open in Library
        </Button>
        {!libraryEnabled ? (
          <p
            role="status"
            data-testid="document-navigation-unavailable"
            className="mt-2 px-1 text-[length:var(--fs-sm)] leading-5 text-[var(--dim)]"
          >
            {!libraryHref
              ? "Open in Library is disabled because required opaque document or evidence references are missing."
              : "Document navigation is unavailable until the Library preview surface is ready."}
          </p>
        ) : (
          <p role="status" className="mt-2 px-1 text-[length:var(--fs-sm)] leading-5 text-[var(--dim)]">
            Opens the authorized Library preview for this evidence.
          </p>
        )}
      </div>
    </div>
  );
}
