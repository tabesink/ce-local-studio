"use client";

import { useEffect, useState } from "react";
import { EmptySafeNotice, SettingsNotice, StatusPill } from "@/_shared/ui";
import type { components } from "@/lib/api/generated/openapi";

export type OperationRow = components["schemas"]["OperationDto"];

type LoadState = "loading" | "ready" | "empty" | "error";

function statusTone(status: OperationRow["status"]): "default" | "good" | "warning" | "danger" | "info" {
  switch (status) {
    case "succeeded":
      return "good";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    case "running":
    case "queued":
      return "info";
    default:
      return "default";
  }
}

/**
 * Read-only operation history. Does not render retry/cancel — those bind only to
 * separately contracted current-operation endpoints elsewhere.
 */
export function OperationHistoryList({
  testId,
  title = "Operation history",
  load,
}: {
  testId: string;
  title?: string;
  load: () => Promise<{ operations: OperationRow[] }>;
}) {
  const [state, setState] = useState<LoadState>("loading");
  const [operations, setOperations] = useState<OperationRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setError(null);
    void load()
      .then((result) => {
        if (cancelled) return;
        setOperations(result.operations);
        setState(result.operations.length === 0 ? "empty" : "ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Operation history is unavailable.");
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  return (
    <div data-testid={testId} className="space-y-2">
      <p className="font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
        {title}
      </p>
      {state === "loading" ? <SettingsNotice tone="default">Loading operation history…</SettingsNotice> : null}
      {state === "error" ? (
        <SettingsNotice tone="danger">{error ?? "Operation history is unavailable."}</SettingsNotice>
      ) : null}
      {state === "empty" ? <EmptySafeNotice>No operations recorded yet.</EmptySafeNotice> : null}
      {state === "ready" ? (
        <ul className="space-y-1.5">
          {operations.map((op) => (
            <li
              key={op.id}
              className="rounded-md border border-[var(--ui-border)]/50 px-2.5 py-1.5 text-[length:var(--fs-sm)]"
              data-testid={`${testId}-row`}
              data-operation-status={op.status}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                  {op.operationType}
                </span>
                <StatusPill tone={statusTone(op.status)}>{op.status}</StatusPill>
              </div>
              {op.message ? <p className="mt-0.5 truncate text-[var(--fg)]">{op.message}</p> : null}
              {op.error ? (
                <p className="mt-0.5 truncate text-[length:var(--fs-xs)] text-[var(--danger)]">
                  {op.error.code}: {op.error.message}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
