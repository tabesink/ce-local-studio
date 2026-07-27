"use client";

import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cx, IconButton, StatusPill } from "@/components/ui";

export type DomainAccordionRowProps = {
  displayName: string;
  domainId: string;
  expanded: boolean;
  panelId: string;
  stateLabel: string;
  stateTone: "default" | "good" | "warning" | "danger" | "info";
  onToggleExpand: () => void;
  lifecycleControl: ReactNode;
  children?: ReactNode;
};

/**
 * Settings-owned Controllers-style accordion row chrome.
 * Cite: environment-controls Controllers template / LS Knowledge Graphs grammar.
 * Not a shared @/ui Accordion export.
 */
export function DomainAccordionRow({
  displayName,
  domainId,
  expanded,
  panelId,
  stateLabel,
  stateTone,
  onToggleExpand,
  lifecycleControl,
  children,
}: DomainAccordionRowProps) {
  return (
    <div>
      <div className="flex items-center gap-3 px-3.5 py-2.5 transition-colors hover:bg-(--ui-hover)/35">
        <IconButton
          aria-expanded={expanded}
          aria-controls={panelId}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${displayName}`}
          title={`${expanded ? "Collapse" : "Expand"} Knowledge Domain`}
          onClick={onToggleExpand}
          className="shrink-0 text-(--ui-muted) hover:bg-(--ui-hover) hover:text-(--ui-fg)"
        >
          <ChevronDown
            className={cx(
              "h-3.5 w-3.5 motion-reduce:transition-none transition-transform",
              expanded ? "" : "-rotate-90",
            )}
            aria-hidden
          />
        </IconButton>
        <div className="min-w-0 flex-1">
          <span className="truncate text-[length:var(--fs-base)] font-medium text-(--ui-fg)">
            {displayName}
          </span>
          <div className="truncate font-mono text-[length:var(--fs-xs)] text-(--ui-muted)">{domainId}</div>
        </div>
        <StatusPill tone={stateTone}>{stateLabel}</StatusPill>
        {lifecycleControl}
      </div>
      {expanded ? (
        <div
          id={panelId}
          role="region"
          aria-label={`${displayName} details`}
          className="bg-(--ui-bg)/35 px-3.5 py-3"
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
