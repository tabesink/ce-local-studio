"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppPage,
  EmptySafeNotice,
  PageHeader,
  RefreshIconButton,
  SegmentedControl,
  SettingsButton,
  SettingsNotice,
  StatusPill,
  Table,
  TBody,
  TCell,
  TH,
  THead,
  TRow,
  type UiTone,
} from "@/_shared/ui";
import { isApiError } from "@/lib/api/errors";
import { useAuthStore } from "@/state/auth-store";
import { PageState } from "@/components/ui/PageState";
import { listAdminDomains, type AdminDomain } from "@/features/domains/api";
import {
  getLightragDiagnostics,
  listAuditEvents,
  type AuditEvent,
  type LightragDiagnostics,
} from "@/features/logs-observability/api";

type LogsTab = "audit" | "diagnostics";

function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "Request failed.";
}

function outcomeTone(outcome: string): UiTone {
  if (outcome === "succeeded") return "good";
  if (outcome === "failed") return "danger";
  return "default";
}

/* LS logs-observability surface over CE P8 audit + diagnostics.
   Live SSE log tails stay absent until an F-010 scoped-logs contract. */
export function LogsPage() {
  const user = useAuthStore((state) => state.user);
  const [tab, setTab] = useState<LogsTab>("audit");

  if (user && user.role !== "administrator") {
    return <PageState title="Forbidden" message="Logs are available to administrators only." tone="danger" />;
  }

  return (
    <AppPage>
      <div className="mx-auto w-full max-w-5xl px-4 py-5 sm:px-6 lg:py-8">
        <PageHeader
          eyebrow="Observability"
          title="Logs"
          actions={
            <SegmentedControl<LogsTab>
              items={[
                { id: "audit", label: "Audit events" },
                { id: "diagnostics", label: "LightRAG diagnostics" },
              ]}
              value={tab}
              onChange={setTab}
            />
          }
        />
        {tab === "audit" ? <AuditEventsPanel /> : <DiagnosticsPanel />}
      </div>
    </AppPage>
  );
}

function AuditEventsPanel() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (cursor?: string) => {
    setLoading(true);
    setError(null);
    try {
      const page = await listAuditEvents({ limit: 50, cursor });
      setEvents((current) => (cursor ? [...current, ...page.auditEvents] : page.auditEvents));
      setNextCursor(page.nextCursor);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-[length:var(--fs-sm)] text-[var(--dim)]">{events.length} events loaded</span>
        <RefreshIconButton onClick={() => void load()} loading={loading} label="Refresh audit events" />
      </div>
      {error ? <SettingsNotice tone="danger" className="mb-3">{error}</SettingsNotice> : null}
      {events.length === 0 && !loading ? (
        <EmptySafeNotice>No audit events recorded.</EmptySafeNotice>
      ) : (
        <Table>
          <THead>
            <tr>
              <TH>Event</TH>
              <TH>Actor</TH>
              <TH>Target</TH>
              <TH>Outcome</TH>
              <TH>Request</TH>
              <TH align="right">Created</TH>
            </tr>
          </THead>
          <TBody>
            {events.map((event) => (
              <TRow key={event.id}>
                <TCell className="font-mono text-[length:var(--fs-sm)]">{event.eventName}</TCell>
                <TCell className="text-[length:var(--fs-sm)] text-[var(--dim)]">{event.actorKind}</TCell>
                <TCell className="max-w-48 truncate font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                  {event.targetKind ? `${event.targetKind}:${event.targetId ?? ""}` : "-"}
                </TCell>
                <TCell>
                  <StatusPill tone={outcomeTone(event.outcome)}>
                    {event.outcome}
                    {event.safeErrorCode ? ` (${event.safeErrorCode})` : ""}
                  </StatusPill>
                </TCell>
                <TCell className="max-w-36 truncate font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                  {event.requestId ?? "-"}
                </TCell>
                <TCell align="right" className="whitespace-nowrap font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                  {new Date(event.createdAt).toLocaleString()}
                </TCell>
              </TRow>
            ))}
          </TBody>
        </Table>
      )}
      {nextCursor ? (
        <div className="mt-3 flex justify-center">
          <SettingsButton disabled={loading} onClick={() => void load(nextCursor)}>
            Load more
          </SettingsButton>
        </div>
      ) : null}
    </section>
  );
}

function DiagnosticsPanel() {
  const [domains, setDomains] = useState<AdminDomain[]>([]);
  const [domainId, setDomainId] = useState("");
  const [diagnostics, setDiagnostics] = useState<LightragDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAdminDomains()
      .then((rows) => {
        if (cancelled) return;
        setDomains(rows);
        setDomainId((current) => current || (rows[0]?.id ?? ""));
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    if (!domainId) return;
    setLoading(true);
    setError(null);
    try {
      setDiagnostics(await getLightragDiagnostics(domainId, 200));
    } catch (err) {
      setDiagnostics(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [domainId]);

  useEffect(() => {
    void load();
  }, [load]);

  const status = useMemo(() => {
    if (!diagnostics) return "";
    const captured = new Date(diagnostics.capturedAt).toLocaleString();
    return `${diagnostics.lineCount} lines captured ${captured}${diagnostics.truncated ? " (truncated)" : ""}`;
  }, [diagnostics]);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <select
          value={domainId}
          onChange={(event) => setDomainId(event.target.value)}
          aria-label="Knowledge Domain"
          className="h-8 rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2.5 text-[length:var(--fs-sm)] text-[var(--fg)] outline-none"
        >
          {domains.length === 0 ? <option value="">No domains</option> : null}
          {domains.map((domain) => (
            <option key={domain.id} value={domain.id}>
              {domain.displayName}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <span className="text-[length:var(--fs-sm)] text-[var(--dim)]">{status}</span>
          <RefreshIconButton onClick={() => void load()} loading={loading} label="Refresh diagnostics" />
        </div>
      </div>
      {error ? <SettingsNotice tone="danger" className="mb-3">{error}</SettingsNotice> : null}
      {!diagnostics && !error ? (
        <EmptySafeNotice>{loading ? "Loading diagnostics." : "Select a Knowledge Domain."}</EmptySafeNotice>
      ) : null}
      {diagnostics ? (
        <pre className="max-h-[60vh] overflow-auto rounded-md border border-[var(--ui-border)] bg-[var(--ui-surface)] p-3 font-mono text-[length:var(--fs-xs)] leading-relaxed text-[var(--fg)]/85">
          {diagnostics.lines.map((line) => line.message).join("\n") || "No log lines captured."}
        </pre>
      ) : null}
    </section>
  );
}
