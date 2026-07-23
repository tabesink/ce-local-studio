"use client";

import { useEffect, useState } from "react";
import { Network } from "lucide-react";
import { PageHeader, SettingsNotice } from "@/_shared/ui";
import { isApiError } from "@/lib/api/errors";
import { listMemberDomains, type MemberDomain } from "@/features/domains/api";

/* Knowledge graph route shell at /database-visualize (do not rename without
   spec change). The sigma canvas stays a placeholder: graph API/data DTOs
   are not approved yet (F-009 T-070 gate). */
export function GraphPage() {
  const [domains, setDomains] = useState<MemberDomain[]>([]);
  const [domainId, setDomainId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMemberDomains()
      .then((rows) => {
        if (cancelled) return;
        setDomains(rows);
        setDomainId((current) => current || (rows[0]?.id ?? ""));
      })
      .catch((err) => {
        if (!cancelled) setError(isApiError(err) ? err.message : "Request failed.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow="Knowledge graph"
        title="Graph"
        actions={
          <select
            value={domainId}
            onChange={(event) => setDomainId(event.target.value)}
            aria-label="Knowledge Domain"
            className="h-8 rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2.5 text-[length:var(--fs-sm)] text-[var(--fg)] outline-none"
          >
            {domains.length === 0 ? <option value="">No domains</option> : null}
            {domains.map((domain) => (
              <option key={domain.id} value={domain.id} disabled={!domain.available}>
                {domain.displayName}
              </option>
            ))}
          </select>
        }
      />
      {error ? <SettingsNotice tone="danger" className="mb-3">{error}</SettingsNotice> : null}
      <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-[var(--ui-border)] bg-[var(--ui-surface)]/40">
        <div className="max-w-md p-6 text-center">
          <Network className="mx-auto mb-3 h-8 w-8 text-[var(--dim)]" strokeWidth={1.5} />
          <h2 className="text-[length:var(--fs-lg)] font-medium text-[var(--fg)]">Graph canvas unavailable</h2>
          <p className="mt-2 text-[length:var(--fs-sm)] leading-relaxed text-[var(--dim)]">
            The knowledge graph visualization is blocked until the graph API and data contracts are approved. The
            route shell and Knowledge Domain selector are in place for that wiring.
          </p>
        </div>
      </div>
    </div>
  );
}
