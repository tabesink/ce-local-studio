"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Network, RefreshCw, X } from "lucide-react";
import { PageHeader, Select, SettingsButton, SettingsNotice, StatusPill } from "@/_shared/ui";
import { PageState } from "@/components/ui/PageState";
import { Button } from "@/ui/Button";
import { isApiError } from "@/lib/api/errors";
import { useAuthStore } from "@/features/auth/auth-store";
import { listMemberDomains } from "@/features/domains/api";
import { fetchDomainGraph, searchDomainGraphLabels, type GraphLabel } from "@/features/graph/api";
import { GraphNodeBrowser } from "@/features/graph/GraphNodeBrowser";
import { GraphNodeDetail } from "@/features/graph/GraphNodeDetail";

const GraphCanvas = dynamic(
  () => import("@/features/graph/GraphCanvas").then((mod) => mod.GraphCanvas),
  {
    ssr: false,
    loading: () => (
      <div
        className="flex h-full min-h-[240px] items-center justify-center rounded-lg border border-[var(--ui-border)] text-[length:var(--fs-sm)] text-[var(--dim)]"
        data-testid="graph-canvas-loading"
      >
        Loading canvas…
      </div>
    ),
  },
);
import {
  connectedEdges,
  filterLocalNodes,
  graphReducer,
  initialGraphState,
  selectedNode,
  shouldClearGraphOnError,
} from "@/features/graph/graphState";
import { buildGraphHref, parseGraphUrlState } from "@/features/graph/graphUrlState";

function toSafeError(error: unknown) {
  if (isApiError(error)) {
    return { code: error.code, message: error.message, requestId: error.requestId };
  }
  return { code: "http_error", message: "Request failed.", requestId: null };
}

function GraphPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const auth = useAuthStore();
  const urlState = useMemo(() => parseGraphUrlState(searchParams), [searchParams]);
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const snapshotAbort = useRef<AbortController | null>(null);
  const searchAbort = useRef<AbortController | null>(null);
  const preferredNodeRef = useRef<string | null>(urlState.node);
  const focusLabelRef = useRef<string | null>(null);

  const node = selectedNode(state);
  const edges = node ? connectedEdges(state, node.ref) : [];
  const localNodes = useMemo(
    () => filterLocalNodes(state.snapshot?.nodes ?? [], state.filterQuery),
    [state.filterQuery, state.snapshot],
  );
  const isAdmin = auth.user?.role === "administrator";
  const busy = state.phase === "loading" || state.phase === "refreshing";

  const syncUrl = useCallback(
    (domainId: string | null, nodeRef: string | null) => {
      const next = buildGraphHref({ domain: domainId, node: nodeRef });
      const current = buildGraphHref(urlState);
      if (next !== current) router.replace(next, { scroll: false });
    },
    [router, urlState],
  );

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      dispatch({ type: "identity_cleared" });
    }
  }, [auth.status]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const domains = await listMemberDomains();
        if (cancelled) return;
        dispatch({
          type: "domains_loaded",
          domains,
          preferredDomainId: urlState.domain,
        });
      } catch (error) {
        if (cancelled) return;
        dispatch({ type: "domains_failed", error: toSafeError(error) });
      }
    })();
    return () => {
      cancelled = true;
    };
    // Boot once per auth identity; URL domain preference is captured at load time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  useEffect(() => {
    if (!state.domainId) return;
    const generation = state.requestGeneration;
    if (generation < 1) return;
    snapshotAbort.current?.abort();
    const controller = new AbortController();
    snapshotAbort.current = controller;
    const focusLabel = focusLabelRef.current;
    focusLabelRef.current = null;
    dispatch({ type: "snapshot_loading", generation });
    (async () => {
      try {
        const snapshot = await fetchDomainGraph(state.domainId!, {
          label: focusLabel,
          signal: controller.signal,
        });
        dispatch({
          type: "snapshot_ready",
          generation,
          snapshot,
          preferredNodeRef: preferredNodeRef.current,
        });
        preferredNodeRef.current = null;
        headingRef.current?.focus();
      } catch (error) {
        if (controller.signal.aborted) return;
        const safe = toSafeError(error);
        dispatch({
          type: "snapshot_failed",
          generation,
          error: safe,
          clearGraph: shouldClearGraphOnError(safe.code),
        });
      }
    })();
    return () => controller.abort();
  }, [state.domainId, state.requestGeneration]);

  useEffect(() => {
    syncUrl(state.domainId, state.selectedNodeRef);
  }, [state.domainId, state.selectedNodeRef, syncUrl]);

  useEffect(() => {
    const query = state.filterQuery.trim();
    searchAbort.current?.abort();
    if (!state.domainId || query.length < 2) {
      dispatch({ type: "remote_search_cleared" });
      return;
    }
    const controller = new AbortController();
    searchAbort.current = controller;
    const timer = window.setTimeout(async () => {
      dispatch({ type: "remote_search_pending" });
      try {
        const result = await searchDomainGraphLabels(state.domainId!, {
          q: query,
          limit: 50,
          signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          dispatch({ type: "remote_search_ready", items: result.items });
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        dispatch({ type: "remote_search_cleared" });
        dispatch({ type: "announce", message: toSafeError(error).message });
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [state.domainId, state.filterQuery]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (detailOpen) {
          setDetailOpen(false);
          dispatch({ type: "select_node", nodeRef: null });
          return;
        }
        if (browserOpen) setBrowserOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [browserOpen, detailOpen]);

  const onSelectDomain = (domainId: string) => {
    preferredNodeRef.current = null;
    focusLabelRef.current = null;
    dispatch({ type: "select_domain", domainId });
  };

  const onRefresh = () => {
    if (!state.domainId) return;
    preferredNodeRef.current = state.selectedNodeRef;
    focusLabelRef.current = null;
    dispatch({ type: "reload_snapshot" });
  };

  const onSelectNode = (nodeRef: string | null) => {
    dispatch({ type: "select_node", nodeRef });
    setDetailOpen(Boolean(nodeRef));
  };

  const onSelectRemoteLabel = (label: GraphLabel) => {
    if (!state.domainId) return;
    preferredNodeRef.current = label.nodeRef;
    focusLabelRef.current = label.label;
    setDetailOpen(true);
    dispatch({ type: "reload_snapshot" });
  };

  if (state.phase === "boot") {
    return <PageState title="Graph" message="Loading knowledge domains…" />;
  }

  if (state.phase === "empty_domains") {
    return (
      <div className="flex h-full min-h-0 flex-col px-4 py-5 sm:px-6" data-testid="graph-workbench">
        <PageHeader eyebrow="Knowledge graph" title="Graph" />
        <div className="mt-6 max-w-lg rounded-lg border border-[var(--ui-border)] bg-[var(--ui-surface)]/40 p-6">
          <Network className="mb-3 h-7 w-7 text-[var(--dim)]" strokeWidth={1.5} />
          <h2 className="text-[length:var(--fs-lg)] font-medium text-[var(--fg)]">No eligible domain</h2>
          <p className="mt-2 text-[length:var(--fs-sm)] text-[var(--dim)]">
            Graph viewing needs a running, query-eligible knowledge domain.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href="/documents" className="text-[length:var(--fs-sm)] text-[var(--accent)] underline">
              Open Documents
            </Link>
            <Link href="/chat" className="text-[length:var(--fs-sm)] text-[var(--accent)] underline">
              Open Chat
            </Link>
            {isAdmin ? (
              <Link
                href="/settings?section=domains"
                className="text-[length:var(--fs-sm)] text-[var(--accent)] underline"
              >
                Open Settings
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const summary = state.snapshot
    ? `${state.snapshot.domain.name}: ${state.snapshot.nodes.length} nodes, ${state.snapshot.edges.length} relations${
        state.snapshot.truncated ? ", truncated neighborhood" : ""
      }.${node ? ` Selected ${node.label}.` : ""}`
    : "Knowledge graph canvas.";

  return (
    <div className="flex h-full min-h-0 flex-col px-4 py-5 sm:px-6" data-testid="graph-workbench">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <PageHeader eyebrow="Knowledge graph" title="Graph" />
          <h2 ref={headingRef} tabIndex={-1} className="sr-only">
            Knowledge domain graph
          </h2>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[220px]">
            <Select
              label="Knowledge Domain"
              value={state.domainId ?? ""}
              onChange={(event) => onSelectDomain(event.target.value)}
              options={state.domains
                .filter((domain) => domain.queryEligible && domain.state === "running")
                .map((domain) => ({ value: domain.id, label: domain.displayName }))}
            />
          </div>
          <SettingsButton
            type="button"
            aria-label="Refresh graph"
            onClick={onRefresh}
            disabled={!state.domainId || busy}
          >
            <RefreshCw className="h-4 w-4" />
          </SettingsButton>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="lg:hidden"
            onClick={() => setBrowserOpen(true)}
          >
            Nodes
          </Button>
          {node ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="xl:hidden"
              onClick={() => setDetailOpen(true)}
            >
              Detail
            </Button>
          ) : null}
        </div>
      </div>

      <div className="sr-only" role="status" aria-live="polite">
        {state.announcement}
      </div>
      <p className="mb-3 text-[length:var(--fs-sm)] text-[var(--dim)]" data-testid="graph-accessible-summary">
        {summary}
      </p>

      {state.error ? (
        <div className="mb-3">
          <SettingsNotice tone="danger">
            {state.error.message}
            {state.error.requestId ? ` Request ID: ${state.error.requestId}` : ""}
          </SettingsNotice>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
              Retry
            </Button>
            {isAdmin ? (
              <Link href="/settings?section=domains" className="text-[length:var(--fs-sm)] text-[var(--accent)] underline">
                Settings
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      {state.snapshot?.truncated ? (
        <div className="mb-3">
          <StatusPill tone="warning">Bounded neighborhood shown — search still covers authorized labels.</StatusPill>
        </div>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_minmax(240px,360px)]">
        <div className="hidden min-h-0 lg:block">
          <GraphNodeBrowser
            nodes={localNodes}
            remoteLabels={state.remoteLabels}
            selectedNodeRef={state.selectedNodeRef}
            filterQuery={state.filterQuery}
            remoteSearchPending={state.remoteSearchPending}
            onFilterChange={(query) => dispatch({ type: "set_filter", query })}
            onSelectNode={onSelectNode}
            onSelectRemoteLabel={onSelectRemoteLabel}
          />
        </div>
        <div className="min-h-0 min-w-0">
          {state.snapshot ? (
            <GraphCanvas
              nodes={state.snapshot.nodes}
              edges={state.snapshot.edges}
              selectedNodeRef={state.selectedNodeRef}
              busy={busy}
              onSelectNode={onSelectNode}
            />
          ) : (
            <div
              className="flex h-full min-h-[240px] items-center justify-center rounded-lg border border-[var(--ui-border)] text-[length:var(--fs-sm)] text-[var(--dim)]"
              data-testid="graph-canvas-empty"
            >
              {busy ? "Loading graph…" : "No graph loaded."}
            </div>
          )}
        </div>
        <div className="hidden min-h-0 xl:block">
          {node && state.snapshot ? (
            <GraphNodeDetail
              snapshot={state.snapshot}
              node={node}
              edges={edges}
              onSelectNeighbor={onSelectNode}
              onClose={() => onSelectNode(null)}
            />
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--ui-border)] p-4 text-[length:var(--fs-sm)] text-[var(--dim)]">
              Select a node to inspect label, kind, degree, and relations.
            </div>
          )}
        </div>
      </div>

      {browserOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Graph nodes">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close nodes drawer"
            onClick={() => setBrowserOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-[min(100%,320px)] flex-col bg-[var(--ui-bg)] p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[length:var(--fs-md)] font-medium">Nodes</h2>
              <Button type="button" variant="ghost" size="sm" aria-label="Close" onClick={() => setBrowserOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <GraphNodeBrowser
              nodes={localNodes}
              remoteLabels={state.remoteLabels}
              selectedNodeRef={state.selectedNodeRef}
              filterQuery={state.filterQuery}
              remoteSearchPending={state.remoteSearchPending}
              onFilterChange={(query) => dispatch({ type: "set_filter", query })}
              onSelectNode={(ref) => {
                onSelectNode(ref);
                setBrowserOpen(false);
              }}
              onSelectRemoteLabel={(label) => {
                onSelectRemoteLabel(label);
                setBrowserOpen(false);
              }}
            />
          </div>
        </div>
      ) : null}

      {detailOpen && node && state.snapshot ? (
        <div className="fixed inset-0 z-50 xl:hidden" role="dialog" aria-modal="true" aria-label="Node detail">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close detail drawer"
            onClick={() => setDetailOpen(false)}
          />
          <div className="absolute inset-y-0 right-0 flex w-[min(100%,360px)] flex-col bg-[var(--ui-bg)] p-4 shadow-xl">
            <GraphNodeDetail
              snapshot={state.snapshot}
              node={node}
              edges={edges}
              onSelectNeighbor={onSelectNode}
              onClose={() => {
                setDetailOpen(false);
                onSelectNode(null);
              }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function GraphPage() {
  return (
    <Suspense fallback={<PageState title="Graph" message="Loading graph workbench…" />}>
      <GraphPageInner />
    </Suspense>
  );
}
