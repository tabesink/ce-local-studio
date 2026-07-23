"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, FileText, Upload, X } from "lucide-react";
import {
  cx,
  EmptySafeNotice,
  PageHeader,
  RefreshIconButton,
  SearchInput,
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
  cancelSourceIndex,
  cancelSourcePreparation,
  deleteSource,
  listAdminSources,
  retrySourceIndex,
  retrySourcePreparation,
  uploadSource,
  type SourceDocument,
} from "@/features/documents/api";
import {
  buildChatReturnHref,
  hasChatReturn,
  parseLibraryDeepLink,
} from "@/features/documents/libraryDeepLink";

type DomainOption = Pick<AdminDomain, "id" | "displayName">;

type PreviewState =
  | { kind: "idle" }
  | { kind: "unavailable"; message: string };

function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "Request failed.";
}

function stateTone(state: string): UiTone {
  if (state === "ready") return "good";
  if (state === "failed" || state === "error") return "danger";
  if (state === "cancelled") return "default";
  return "warning";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* Phase 1 administrator source operations. Member library/content and
   evidence deep-links stay explicitly unavailable until the governed opaque
   document/evidence routes are implemented by P4/P6/P9. */
export function DocumentsPage() {
  return (
    <Suspense fallback={<PageState title="Library" message="Loading Source Documents…" />}>
      <DocumentsPageInner />
    </Suspense>
  );
}

function DocumentsPageInner() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === "administrator";
  const router = useRouter();
  const searchParams = useSearchParams();
  const deepLink = useMemo(() => parseLibraryDeepLink(searchParams), [searchParams]);
  const showBackToChat = hasChatReturn(deepLink);

  const [domains, setDomains] = useState<DomainOption[]>([]);
  const [domainId, setDomainId] = useState("");
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [selected, setSelected] = useState<SourceDocument | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ kind: "idle" });
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadGenerationRef = useRef(0);

  const setPreviewState = useCallback((next: PreviewState) => {
    setPreview(next);
  }, []);

  useEffect(() => {
    if (!user || !isAdmin) return;
    let cancelled = false;
    const loadDomains = listAdminDomains();
    loadDomains
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
  }, [user, isAdmin]);

  const reload = useCallback(async () => {
    if (!domainId || !user || !isAdmin) return;
    const generation = ++loadGenerationRef.current;
    const requestDomainId = domainId;
    setLoading(true);
    setError(null);
    try {
      const rows = await listAdminSources(requestDomainId);
      if (loadGenerationRef.current !== generation) return;
      setSources(rows);
      setSelected((current) => rows.find((row) => row.id === current?.id) ?? null);
    } catch (err) {
      if (loadGenerationRef.current !== generation) return;
      setSources([]);
      setSelected(null);
      setError(errorMessage(err));
    } finally {
      if (loadGenerationRef.current === generation) {
        setLoading(false);
      }
    }
  }, [domainId, user, isAdmin]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    setSources([]);
    setSelected(null);
    setPreviewState({ kind: "idle" });
  }, [domainId, setPreviewState]);

  useEffect(() => {
    if (!selected || !domainId || selected.domainId !== domainId) {
      setPreviewState({ kind: "idle" });
      return;
    }
    setPreviewState({
      kind: "unavailable",
      message: "Governed document preview is not available until the opaque document content contract is implemented.",
    });
  }, [selected, domainId, setPreviewState]);

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return sources;
    return sources.filter((row) => row.originalFilename.toLowerCase().includes(needle));
  }, [filter, sources]);

  if (!user) {
    return <PageState title="Library" message="Sign in to browse Source Documents." />;
  }

  if (!isAdmin) {
    return (
      <PageState
        title="Library"
        message="The governed member document library is not available until opaque document metadata and content routes are implemented."
      />
    );
  }

  const onUpload = async (file: File) => {
    if (!domainId || !isAdmin) return;
    setUploading(true);
    setError(null);
    try {
      await uploadSource(domainId, file);
      await reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const runSourceAction = async (source: SourceDocument, action: () => Promise<void>): Promise<boolean> => {
    if (!isAdmin) return false;
    setBusySourceId(source.id);
    setError(null);
    try {
      await action();
      await reload();
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusySourceId(null);
    }
  };

  const closePreview = () => {
    setSelected(null);
    setPreviewState({ kind: "idle" });
  };

  const selectSource = (source: SourceDocument) => {
    setSelected(source);
  };

  const onBackToChat = () => {
    if (!deepLink.conversationId || !deepLink.turnId) return;
    router.push(buildChatReturnHref(deepLink.conversationId, deepLink.turnId));
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {showBackToChat ? (
        <div
          className="flex h-10 shrink-0 items-center gap-2 border-b border-[var(--ui-border)] bg-[var(--ui-bg)] px-4 sm:px-6"
          data-testid="documents-back-to-chat-chrome"
        >
          <span data-testid="documents-back-to-chat">
            <SettingsButton tone="primary" onClick={onBackToChat} aria-label="Back to chat">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to chat
            </SettingsButton>
          </span>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1">
        <div className={cx("min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6", selected ? "hidden lg:block" : "")}>
          <PageHeader
            eyebrow="Library"
            title="Source Documents"
            actions={
              <>
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
                {isAdmin ? (
                  <>
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      data-testid="documents-upload-input"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void onUpload(file);
                      }}
                    />
                    <span data-testid="documents-upload-button">
                      <SettingsButton
                        tone="primary"
                        disabled={!domainId || uploading}
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Upload className="h-3.5 w-3.5" />
                        {uploading ? "Uploading" : "Upload"}
                      </SettingsButton>
                    </span>
                  </>
                ) : null}
                <RefreshIconButton onClick={() => void reload()} loading={loading} label="Refresh sources" />
              </>
            }
          />
          {error ? <SettingsNotice tone="danger" className="mb-3">{error}</SettingsNotice> : null}
          <SearchInput value={filter} onChange={setFilter} placeholder="Filter by filename..." className="mb-3 max-w-sm" />
          {filtered.length === 0 && !loading ? (
            <EmptySafeNotice>No Source Documents loaded for this Knowledge Domain.</EmptySafeNotice>
          ) : (
            <Table>
              <THead>
                <tr>
                  <TH>Filename</TH>
                  <TH>Preparation</TH>
                  <TH>Index</TH>
                  <TH align="right">Size</TH>
                  <TH align="right">Blocks</TH>
                  <TH align="right">Updated</TH>
                </tr>
              </THead>
              <TBody>
                {filtered.map((source) => (
                  <TRow
                    key={source.id}
                    interactive
                    onClick={() => selectSource(source)}
                  >
                    <TCell className="max-w-64">
                      <span
                        className="flex items-center gap-2"
                        data-testid={`documents-row-${source.id}`}
                        data-filename={source.originalFilename}
                      >
                        <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--dim)]" />
                        <span className="truncate text-[length:var(--fs-sm)] text-[var(--fg)]">
                          {source.originalFilename}
                        </span>
                      </span>
                    </TCell>
                    <TCell>
                      <StatusPill tone={stateTone(source.state)}>{source.state}</StatusPill>
                    </TCell>
                    <TCell>
                      <StatusPill tone={stateTone(source.indexState)}>{source.indexState}</StatusPill>
                    </TCell>
                    <TCell align="right" className="whitespace-nowrap font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                      {formatBytes(source.originalSizeBytes)}
                    </TCell>
                    <TCell align="right" className="font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                      {source.blockCount}
                    </TCell>
                    <TCell align="right" className="whitespace-nowrap font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                      {new Date(source.updatedAt).toLocaleString()}
                    </TCell>
                  </TRow>
                ))}
              </TBody>
            </Table>
          )}
        </div>

        {selected ? (
          <aside
            className="flex w-full min-w-0 flex-col border-l border-[var(--ui-border)] bg-[var(--ui-bg)] lg:w-1/2"
            data-testid="documents-preview-panel"
          >
            <header className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-[var(--ui-border)] px-3">
              <span className="truncate text-[length:var(--fs-sm)] font-medium text-[var(--fg)]">
                {selected.originalFilename}
              </span>
              <button
                type="button"
                onClick={closePreview}
                aria-label="Close preview"
                className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </header>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <PreviewBody preview={preview} />
                <dl className="mt-4 space-y-2 text-[length:var(--fs-sm)]">
                  <PreviewFact label="Content type" value={selected.contentType} mono />
                  <PreviewFact label="Size" value={formatBytes(selected.originalSizeBytes)} mono />
                  <PreviewFact label="Parser" value={selected.parserKind} mono />
                  <PreviewFact label="Preparation state" value={selected.state} />
                  <PreviewFact label="Index state" value={selected.indexState} />
                  {selected.indexErrorMessage ? (
                    <PreviewFact label="Index error" value={selected.indexErrorMessage} />
                  ) : null}
                  <PreviewFact label="Blocks" value={String(selected.blockCount)} mono />
                  <PreviewFact label="Images" value={String(selected.imageCount)} mono />
                  <PreviewFact label="Created" value={new Date(selected.createdAt).toLocaleString()} />
                </dl>
                {isAdmin ? (
                  <div className="mt-5 flex flex-wrap gap-1.5" data-testid="documents-admin-actions">
                    <SettingsButton
                      disabled={busySourceId === selected.id}
                      onClick={() => void runSourceAction(selected, () => retrySourcePreparation(domainId, selected.id))}
                    >
                      Retry preparation
                    </SettingsButton>
                    <SettingsButton
                      disabled={busySourceId === selected.id}
                      onClick={() => void runSourceAction(selected, () => cancelSourcePreparation(domainId, selected.id))}
                    >
                      Cancel preparation
                    </SettingsButton>
                    <SettingsButton
                      disabled={busySourceId === selected.id}
                      onClick={() => void runSourceAction(selected, () => retrySourceIndex(domainId, selected.id))}
                    >
                      Retry index
                    </SettingsButton>
                    <SettingsButton
                      disabled={busySourceId === selected.id}
                      onClick={() => void runSourceAction(selected, () => cancelSourceIndex(domainId, selected.id))}
                    >
                      Cancel index
                    </SettingsButton>
                    <SettingsButton
                      tone="danger"
                      disabled={busySourceId === selected.id}
                      onClick={() => {
                        if (window.confirm(`Delete "${selected.originalFilename}"? This cannot be undone.`)) {
                          const sourceId = selected.id;
                          void runSourceAction(selected, async () => {
                            await deleteSource(domainId, sourceId);
                          }).then((ok) => {
                            if (!ok) return;
                            setSelected(null);
                            setPreviewState({ kind: "idle" });
                          });
                        }
                      }}
                    >
                      Delete
                    </SettingsButton>
                  </div>
                ) : (
                  <div data-testid="documents-member-readonly" className="sr-only">
                    Member read-only library
                  </div>
                )}
              </div>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function PreviewBody({ preview }: { preview: PreviewState }) {
  const message =
    preview.kind === "unavailable"
      ? preview.message
      : "Select a Source Document to inspect its safe administrative metadata.";
  return (
    <div data-testid="documents-preview-unavailable">
      <SettingsNotice tone="warning" className="mb-4">
        {message}
      </SettingsNotice>
    </div>
  );
}

function PreviewFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--ui-separator)]/60 pb-1.5">
      <dt className="shrink-0 text-[var(--dim)]">{label}</dt>
      <dd className={cx("min-w-0 truncate text-right text-[var(--fg)]/85", mono ? "font-mono text-[length:var(--fs-xs)]" : "")}>
        {value}
      </dd>
    </div>
  );
}
