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
} from "@/_shared/ui";
import { isApiError } from "@/lib/api/errors";
import { useAuthStore } from "@/features/auth/auth-store";
import { PageState } from "@/components/ui/PageState";
import { listMemberDomains, type MemberDomain } from "@/features/domains/api";
import {
  cancelSourceIndex,
  cancelSourcePreparation,
  deleteSource,
  fetchDocumentContent,
  getDocument,
  getEvidenceLocation,
  getSourceOutline,
  isAdminActionEnabled,
  listAdminSources,
  listDocuments,
  listSourceOperations,
  retrySourceIndex,
  retrySourcePreparation,
  uploadSource,
  type AdminSource,
  type DocumentSummary,
  type OutlineItem,
} from "@/features/documents/api";
import { OperationHistoryList } from "@/features/operations/OperationHistoryList";
import { PdfPreview, type PdfPreviewAnchor } from "@/features/documents/PdfPreview";
import {
  buildChatReturnHref,
  hasChatReturn,
  parseLibraryDeepLink,
} from "@/features/documents/libraryDeepLink";

type PreviewState =
  | { kind: "idle" }
  | { kind: "loading"; locatingEvidence?: boolean }
  | {
      kind: "pdf";
      objectUrl: string;
      page: number;
      exactLocationUnavailable?: boolean;
      anchor?: PdfPreviewAnchor | null;
      anchorGeneration?: number;
    }
  | { kind: "unavailable"; message: string; requestId?: string | null }
  | { kind: "failed"; message: string; requestId?: string | null };

function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  return "Request failed.";
}

function errorRequestId(error: unknown): string | null {
  if (isApiError(error)) return error.requestId;
  return null;
}

function mapDocumentPreviewError(error: unknown): Extract<PreviewState, { kind: "unavailable" | "failed" }> {
  if (isApiError(error) && (error.code === "document_preview_unavailable" || error.status === 409)) {
    return {
      kind: "unavailable",
      message: "Governed preview is not available for this document.",
      requestId: error.requestId,
    };
  }
  if (isApiError(error) && (error.status === 404 || error.code === "document_not_found")) {
    return {
      kind: "unavailable",
      message: "Document is not available.",
      requestId: error.requestId,
    };
  }
  if (isApiError(error) && (error.status === 410 || error.code === "evidence_unavailable")) {
    return {
      kind: "unavailable",
      message: "Evidence no longer available.",
      requestId: error.requestId,
    };
  }
  return {
    kind: "failed",
    message: errorMessage(error),
    requestId: errorRequestId(error),
  };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function revokeObjectUrl(url: string | null | undefined) {
  if (!url) return;
  try {
    URL.revokeObjectURL(url);
  } catch {
    /* ignore */
  }
}

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
  const urlDomain = searchParams.get("domain")?.trim() || "";

  const [domains, setDomains] = useState<MemberDomain[]>([]);
  const [domainId, setDomainId] = useState(urlDomain);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentSummary | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ kind: "idle" });
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [busySourceId, setBusySourceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adminSources, setAdminSources] = useState<AdminSource[]>([]);
  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [outlineStatus, setOutlineStatus] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [anchorNotice, setAnchorNotice] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const listGenerationRef = useRef(0);
  const adminGenerationRef = useRef(0);
  const selectionGenerationRef = useRef(0);
  const locationGenerationRef = useRef(0);
  const contentAbortRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const adminSourcesRef = useRef<AdminSource[]>([]);
  const selectedRefRef = useRef<string | null>(null);
  const handledDeepLinkRef = useRef<string | null>(null);
  const identityKey = user ? `${user.id}:${user.role}` : null;

  const clearObjectUrl = useCallback(() => {
    revokeObjectUrl(objectUrlRef.current);
    objectUrlRef.current = null;
  }, []);

  const setPreviewSafe = useCallback(
    (next: PreviewState) => {
      setPreview((current) => {
        if (current.kind === "pdf" && (next.kind !== "pdf" || next.objectUrl !== current.objectUrl)) {
          if (objectUrlRef.current === current.objectUrl) {
            clearObjectUrl();
          } else {
            revokeObjectUrl(current.objectUrl);
          }
        }
        if (next.kind === "pdf") {
          objectUrlRef.current = next.objectUrl;
        }
        return next;
      });
    },
    [clearObjectUrl],
  );

  const closeViewer = useCallback(() => {
    contentAbortRef.current?.abort();
    contentAbortRef.current = null;
    selectionGenerationRef.current += 1;
    locationGenerationRef.current += 1;
    selectedRefRef.current = null;
    setSelectedRef(null);
    setDetail(null);
    setOutline([]);
    setOutlineStatus("idle");
    setAnchorNotice(null);
    setPreviewSafe({ kind: "idle" });
  }, [setPreviewSafe]);

  useEffect(() => {
    return () => {
      contentAbortRef.current?.abort();
      clearObjectUrl();
    };
  }, [clearObjectUrl]);

  useEffect(() => {
    listGenerationRef.current += 1;
    adminGenerationRef.current += 1;
    handledDeepLinkRef.current = null;
    adminSourcesRef.current = [];
    setLoadingMore(false);
    closeViewer();
    setDocuments([]);
    setNextCursor(null);
    setAdminSources([]);
    setError(null);
  }, [identityKey, closeViewer]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    listMemberDomains()
      .then((rows) => {
        if (cancelled) return;
        setDomains(rows);
        setDomainId((current) => {
          if (current && rows.some((row) => row.id === current)) return current;
          if (urlDomain && rows.some((row) => row.id === urlDomain)) return urlDomain;
          return rows[0]?.id ?? "";
        });
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [user, urlDomain]);

  const reloadLibrary = useCallback(async () => {
    if (!user || !domainId) return;
    const generation = ++listGenerationRef.current;
    setLoading(true);
    setLoadingMore(false);
    setError(null);
    try {
      const { documents: rows, nextCursor: cursor } = await listDocuments({
        domainId,
      });
      if (listGenerationRef.current !== generation) return;
      setDocuments(rows);
      setNextCursor(cursor);
      const currentSelected = selectedRefRef.current;
      if (
        currentSelected &&
        !rows.some((row) => row.ref === currentSelected) &&
        !adminSourcesRef.current.some((source) => source.documentRef === currentSelected)
      ) {
        closeViewer();
      }
    } catch (err) {
      if (listGenerationRef.current !== generation) return;
      setDocuments([]);
      setNextCursor(null);
      setError(errorMessage(err));
    } finally {
      if (listGenerationRef.current === generation) setLoading(false);
    }
  }, [user, domainId, closeViewer]);

  const loadMoreDocuments = useCallback(async () => {
    if (!user || !domainId || !nextCursor || loadingMore) return;
    const generation = listGenerationRef.current;
    setLoadingMore(true);
    setError(null);
    try {
      const { documents: rows, nextCursor: cursor } = await listDocuments({
        domainId,
        cursor: nextCursor,
      });
      if (listGenerationRef.current !== generation) return;
      setDocuments((current) => {
        const seen = new Set(current.map((row) => row.ref));
        return [...current, ...rows.filter((row) => !seen.has(row.ref))];
      });
      setNextCursor(cursor);
    } catch (err) {
      if (listGenerationRef.current !== generation) return;
      setError(errorMessage(err));
    } finally {
      if (listGenerationRef.current === generation) setLoadingMore(false);
    }
  }, [user, domainId, nextCursor, loadingMore]);

  useEffect(() => {
    void reloadLibrary();
  }, [reloadLibrary]);

  const reloadAdminSources = useCallback(async () => {
    if (!user || !isAdmin || !domainId) {
      adminGenerationRef.current += 1;
      adminSourcesRef.current = [];
      setAdminSources([]);
      return;
    }
    const requestDomainId = domainId;
    const generation = ++adminGenerationRef.current;
    adminSourcesRef.current = [];
    setAdminSources([]);
    try {
      const rows = await listAdminSources(requestDomainId);
      if (adminGenerationRef.current !== generation) return;
      adminSourcesRef.current = rows;
      setAdminSources(rows);
    } catch (err) {
      if (adminGenerationRef.current !== generation) return;
      setError(errorMessage(err));
      adminSourcesRef.current = [];
      setAdminSources([]);
    }
  }, [user, isAdmin, domainId]);

  useEffect(() => {
    void reloadAdminSources();
  }, [reloadAdminSources]);

  const selectedAdminSource = useMemo(() => {
    if (!selectedRef) return null;
    return adminSources.find((source) => source.documentRef === selectedRef) ?? null;
  }, [adminSources, selectedRef]);

  const loadPdfContent = useCallback(
    async (
      documentRef: string,
      page: number,
      generation: number,
      exactLocationUnavailable = false,
      anchor: PdfPreviewAnchor | null = null,
      anchorGeneration = 0,
    ) => {
      contentAbortRef.current?.abort();
      const controller = new AbortController();
      contentAbortRef.current = controller;
      setPreviewSafe({ kind: "loading", locatingEvidence: Boolean(anchor) });
      try {
        const { blob } = await fetchDocumentContent(documentRef, { signal: controller.signal });
        if (selectionGenerationRef.current !== generation || controller.signal.aborted) return;
        const objectUrl = URL.createObjectURL(blob);
        if (selectionGenerationRef.current !== generation || controller.signal.aborted) {
          revokeObjectUrl(objectUrl);
          return;
        }
        setPreviewSafe({
          kind: "pdf",
          objectUrl,
          page,
          exactLocationUnavailable,
          anchor,
          anchorGeneration,
        });
      } catch (err) {
        if (controller.signal.aborted || selectionGenerationRef.current !== generation) return;
        setPreviewSafe(mapDocumentPreviewError(err));
      }
    },
    [setPreviewSafe],
  );

  const openDocument = useCallback(
    async (
      documentRef: string,
      options?: {
        page?: number | null;
        exactLocationUnavailable?: boolean;
        anchor?: PdfPreviewAnchor | null;
        anchorGeneration?: number;
        preserveAnchorNotice?: boolean;
      },
    ) => {
      locationGenerationRef.current += 1;
      const generation = ++selectionGenerationRef.current;
      selectedRefRef.current = documentRef;
      setSelectedRef(documentRef);
      setDetail(null);
      if (!options?.preserveAnchorNotice) {
        setAnchorNotice(null);
      }
      setPreviewSafe({ kind: "loading", locatingEvidence: Boolean(options?.anchor) });
      try {
        const doc = await getDocument(documentRef);
        if (selectionGenerationRef.current !== generation) return;
        setDetail(doc);
        const page = options?.page && options.page > 0 ? options.page : 1;
        if (doc.previewKind === "pdf") {
          await loadPdfContent(
            documentRef,
            page,
            generation,
            options?.exactLocationUnavailable ?? false,
            options?.anchor ?? null,
            options?.anchorGeneration ?? 0,
          );
        } else {
          setPreviewSafe({
            kind: "unavailable",
            message: "Governed preview is not available for this document type.",
          });
        }
      } catch (err) {
        if (selectionGenerationRef.current !== generation) return;
        setPreviewSafe(mapDocumentPreviewError(err));
      }
    },
    [loadPdfContent, setPreviewSafe],
  );

  const openAdminOnlySource = useCallback(
    (source: AdminSource) => {
      locationGenerationRef.current += 1;
      selectionGenerationRef.current += 1;
      contentAbortRef.current?.abort();
      contentAbortRef.current = null;
      selectedRefRef.current = source.documentRef;
      setSelectedRef(source.documentRef);
      setDetail(null);
      setAnchorNotice(null);
      setPreviewSafe({
        kind: "unavailable",
        message: "This source is not yet available in the member library.",
      });
    },
    [setPreviewSafe],
  );

  // Inbound deep link: evidence location (server anchor wins over URL page hint).
  const deepLinkKey = `${deepLink.document ?? ""}|${deepLink.evidence ?? ""}|${deepLink.page ?? ""}`;
  useEffect(() => {
    if (!user) return;
    const evidenceRef = deepLink.evidence;
    const documentHint = deepLink.document;
    const pageHint = deepLink.page;

    if (!evidenceRef && !documentHint) return;
    if (handledDeepLinkRef.current === deepLinkKey) return;
    handledDeepLinkRef.current = deepLinkKey;

    const generation = ++locationGenerationRef.current;

    if (evidenceRef) {
      setAnchorNotice("Locating evidence…");
      setPreviewSafe({ kind: "loading", locatingEvidence: true });
      void getEvidenceLocation(evidenceRef)
        .then((location) => {
          if (locationGenerationRef.current !== generation) return;
          // Server page/region win over URL page hints (including page=99).
          const page = location.anchor.pageNumber > 0 ? location.anchor.pageNumber : null;
          const exactUnavailable =
            location.anchor.fallback === "page" && location.anchor.region == null;
          if (exactUnavailable) {
            setAnchorNotice("Exact location unavailable — opened the nearest authorized page.");
          } else if (location.anchor.fallback === "section" && location.anchor.sectionLabel) {
            setAnchorNotice(`Opened section ${location.anchor.sectionLabel}.`);
          } else {
            setAnchorNotice(null);
          }
          void openDocument(location.document.ref, {
            page,
            exactLocationUnavailable: exactUnavailable,
            preserveAnchorNotice: true,
            anchorGeneration: generation,
            anchor: {
              pageNumber: location.anchor.pageNumber,
              region: location.anchor.region,
              sectionLabel: location.anchor.sectionLabel,
              fallback: location.anchor.fallback,
              evidenceKind: location.evidence.kind,
            },
          });
        })
        .catch((err) => {
          if (locationGenerationRef.current !== generation) return;
          setDetail(null);
          setOutline([]);
          setOutlineStatus("idle");
          setAnchorNotice(null);
          setPreviewSafe({
            kind: "unavailable",
            message:
              isApiError(err) && (err.status === 404 || err.status === 410)
                ? "Evidence no longer available."
                : errorMessage(err),
            requestId: errorRequestId(err),
          });
          // Do not open document content from URL hints after location denial.
          if (documentHint) {
            selectedRefRef.current = documentHint;
            setSelectedRef(documentHint);
          }
        });
      return;
    }

    void openDocument(documentHint!, { page: pageHint });
  }, [user, deepLinkKey, deepLink.evidence, deepLink.document, deepLink.page, openDocument, setPreviewSafe]);

  useEffect(() => {
    if (!isAdmin || !selectedAdminSource) {
      setOutline([]);
      setOutlineStatus("idle");
      return;
    }
    let cancelled = false;
    setOutlineStatus("loading");
    getSourceOutline(selectedAdminSource.domainId, selectedAdminSource.id)
      .then((items) => {
        if (cancelled) return;
        setOutline(items);
        setOutlineStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setOutline([]);
        setOutlineStatus("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, selectedAdminSource]);

  type LibraryRow =
    | { kind: "library"; doc: DocumentSummary }
    | { kind: "adminOnly"; source: AdminSource };

  const libraryRows = useMemo((): LibraryRow[] => {
    const rows: LibraryRow[] = documents.map((doc) => ({ kind: "library", doc }));
    if (!isAdmin) return rows;
    const seen = new Set(documents.map((doc) => doc.ref));
    for (const source of adminSources) {
      if (seen.has(source.documentRef) || source.state === "deleting") continue;
      rows.push({ kind: "adminOnly", source });
    }
    return rows;
  }, [documents, adminSources, isAdmin]);

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return libraryRows;
    return libraryRows.filter((row) => {
      const label = row.kind === "library" ? row.doc.label : row.source.displayName;
      return label.toLowerCase().includes(needle);
    });
  }, [filter, libraryRows]);

  if (!user) {
    return <PageState title="Library" message="Sign in to browse Source Documents." />;
  }

  const onUpload = async (file: File) => {
    if (!domainId || !isAdmin) return;
    setUploading(true);
    setError(null);
    try {
      await uploadSource(domainId, file);
      await Promise.all([reloadLibrary(), reloadAdminSources()]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const runSourceAction = async (source: AdminSource, action: () => Promise<void>): Promise<boolean> => {
    if (!isAdmin) return false;
    setBusySourceId(source.id);
    setError(null);
    try {
      await action();
      await Promise.all([reloadLibrary(), reloadAdminSources()]);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusySourceId(null);
    }
  };

  const onBackToChat = () => {
    if (!deepLink.conversation || !deepLink.turn) return;
    router.push(buildChatReturnHref(deepLink.conversation, deepLink.turn, deepLink.evidence));
  };

  const viewerOpen = Boolean(selectedRef) || preview.kind !== "idle";

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
        <div className={cx("min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6", viewerOpen ? "hidden lg:block" : "")}>
          <PageHeader
            eyebrow="Library"
            title="Source Documents"
            actions={
              <>
                <select
                  value={domainId}
                  onChange={(event) => {
                    setDomainId(event.target.value);
                    closeViewer();
                  }}
                  aria-label="Knowledge Domain"
                  className="h-8 rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2.5 text-[length:var(--fs-sm)] text-[var(--fg)] outline-none"
                >
                  {domains.length === 0 ? <option value="">No domains</option> : null}
                  {domains.map((domain) => (
                    <option key={domain.id} value={domain.id} disabled={!domain.queryEligible}>
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
                <RefreshIconButton
                  onClick={() => {
                    void reloadLibrary();
                    void reloadAdminSources();
                  }}
                  loading={loading}
                  label="Refresh documents"
                />
              </>
            }
          />
          {error ? <SettingsNotice tone="danger" className="mb-3">{error}</SettingsNotice> : null}
          <SearchInput value={filter} onChange={setFilter} placeholder="Filter by filename..." className="mb-3 max-w-sm" />
          {filtered.length === 0 && !loading ? (
            <EmptySafeNotice>No Source Documents available for this Knowledge Domain.</EmptySafeNotice>
          ) : (
            <>
              <Table>
                <THead>
                  <tr>
                    <TH>Filename</TH>
                    <TH>Preview</TH>
                    <TH>Domain</TH>
                    <TH align="right">Pages</TH>
                    <TH align="right">Updated</TH>
                  </tr>
                </THead>
                <TBody>
                  {filtered.map((row) => {
                    if (row.kind === "adminOnly") {
                      const source = row.source;
                      return (
                        <TRow
                          key={`admin-${source.id}`}
                          interactive
                          onClick={() => openAdminOnlySource(source)}
                          data-selected={selectedRef === source.documentRef ? "true" : undefined}
                        >
                          <TCell className="max-w-64">
                            <span
                              className="flex items-center gap-2"
                              data-testid={`documents-row-${source.documentRef}`}
                              data-filename={source.displayName}
                              data-document-ref={source.documentRef}
                              data-admin-only="true"
                            >
                              <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--dim)]" />
                              <span className="truncate text-[length:var(--fs-sm)] text-[var(--fg)]">
                                {source.displayName}
                              </span>
                            </span>
                          </TCell>
                          <TCell>
                            <StatusPill tone="warning">ops</StatusPill>
                          </TCell>
                          <TCell className="max-w-40 truncate text-[length:var(--fs-sm)] text-[var(--dim)]">
                            {domains.find((domain) => domain.id === source.domainId)?.displayName ?? "—"}
                          </TCell>
                          <TCell align="right" className="font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                            —
                          </TCell>
                          <TCell align="right" className="whitespace-nowrap font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                            {new Date(source.updatedAt).toLocaleString()}
                          </TCell>
                        </TRow>
                      );
                    }
                    const doc = row.doc;
                    return (
                      <TRow
                        key={doc.ref}
                        interactive
                        onClick={() => void openDocument(doc.ref)}
                        data-selected={selectedRef === doc.ref ? "true" : undefined}
                      >
                        <TCell className="max-w-64">
                          <span
                            className="flex items-center gap-2"
                            data-testid={`documents-row-${doc.ref}`}
                            data-filename={doc.label}
                            data-document-ref={doc.ref}
                          >
                            <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--dim)]" />
                            <span className="truncate text-[length:var(--fs-sm)] text-[var(--fg)]">{doc.label}</span>
                          </span>
                        </TCell>
                        <TCell>
                          <StatusPill tone={doc.previewKind === "pdf" ? "good" : "warning"}>
                            {doc.previewKind}
                          </StatusPill>
                        </TCell>
                        <TCell className="max-w-40 truncate text-[length:var(--fs-sm)] text-[var(--dim)]">
                          {doc.domain.displayName}
                        </TCell>
                        <TCell align="right" className="font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                          {doc.pageCount ?? "—"}
                        </TCell>
                        <TCell align="right" className="whitespace-nowrap font-mono text-[length:var(--fs-xs)] text-[var(--dim)]">
                          {new Date(doc.updatedAt).toLocaleString()}
                        </TCell>
                      </TRow>
                    );
                  })}
                </TBody>
              </Table>
              {nextCursor ? (
                <div className="mt-3" data-testid="documents-load-more">
                  <SettingsButton disabled={loadingMore} onClick={() => void loadMoreDocuments()}>
                    {loadingMore ? "Loading…" : "Load more"}
                  </SettingsButton>
                </div>
              ) : null}
            </>
          )}
          {!isAdmin ? (
            <div data-testid="documents-member-readonly" className="sr-only">
              Member read-only library
            </div>
          ) : null}
        </div>

        {viewerOpen ? (
          <aside
            className="flex w-full min-w-0 flex-col border-l border-[var(--ui-border)] bg-[var(--ui-bg)] lg:w-1/2"
            data-testid="documents-preview-panel"
          >
            <header className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-[var(--ui-border)] px-3">
              <span className="truncate text-[length:var(--fs-sm)] font-medium text-[var(--fg)]">
                {detail?.label ?? "Document"}
              </span>
              <button
                type="button"
                onClick={closeViewer}
                aria-label="Close preview"
                className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </header>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {anchorNotice ? (
                  <SettingsNotice tone="warning" className="mb-3">
                    {anchorNotice}
                  </SettingsNotice>
                ) : null}
                <PreviewBody preview={preview} filename={detail?.label ?? "Document"} />
                {detail ? (
                  <dl className="mt-4 space-y-2 text-[length:var(--fs-sm)]">
                    <PreviewFact label="Content type" value={detail.contentType} mono />
                    <PreviewFact label="Preview" value={detail.previewKind} />
                    <PreviewFact label="Domain" value={detail.domain.displayName} />
                    <PreviewFact
                      label="Pages"
                      value={detail.pageCount != null ? String(detail.pageCount) : "—"}
                      mono
                    />
                    <PreviewFact label="Updated" value={new Date(detail.updatedAt).toLocaleString()} />
                  </dl>
                ) : null}

                {isAdmin && selectedAdminSource ? (
                  <AdminOpsPanel
                    source={selectedAdminSource}
                    busy={busySourceId === selectedAdminSource.id}
                    outline={outline}
                    outlineStatus={outlineStatus}
                    onRetryPreparation={() =>
                      void runSourceAction(selectedAdminSource, () =>
                        retrySourcePreparation(selectedAdminSource.domainId, selectedAdminSource.id),
                      )
                    }
                    onCancelPreparation={() =>
                      void runSourceAction(selectedAdminSource, () =>
                        cancelSourcePreparation(
                          selectedAdminSource.domainId,
                          selectedAdminSource.id,
                          selectedAdminSource.version,
                        ),
                      )
                    }
                    onRetryIndex={() =>
                      void runSourceAction(selectedAdminSource, () =>
                        retrySourceIndex(selectedAdminSource.domainId, selectedAdminSource.id),
                      )
                    }
                    onCancelIndex={() =>
                      void runSourceAction(selectedAdminSource, () =>
                        cancelSourceIndex(selectedAdminSource.domainId, selectedAdminSource.id),
                      )
                    }
                    onDelete={() => {
                      if (
                        !window.confirm(
                          `Delete "${selectedAdminSource.displayName}"? This cannot be undone.`,
                        )
                      ) {
                        return;
                      }
                      void runSourceAction(selectedAdminSource, async () => {
                        await deleteSource(
                          selectedAdminSource.domainId,
                          selectedAdminSource.id,
                          selectedAdminSource.version,
                        );
                      }).then((ok) => {
                        if (ok) closeViewer();
                      });
                    }}
                  />
                ) : null}
              </div>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function PreviewBody({ preview, filename }: { preview: PreviewState; filename: string }) {
  if (preview.kind === "loading") {
    return (
      <div data-testid="documents-preview-loading">
        <SettingsNotice tone="default" className="mb-4">
          {preview.locatingEvidence ? "Locating evidence…" : "Loading document preview…"}
        </SettingsNotice>
      </div>
    );
  }
  if (preview.kind === "pdf") {
    return (
      <>
        {preview.exactLocationUnavailable ? (
          <SettingsNotice tone="warning" className="mb-3">
            Exact location unavailable.
          </SettingsNotice>
        ) : null}
        <PdfPreview
          objectUrl={preview.objectUrl}
          filename={filename}
          initialPage={preview.page}
          anchor={preview.anchor}
          anchorGeneration={preview.anchorGeneration ?? 0}
        />
      </>
    );
  }
  if (preview.kind === "unavailable" || preview.kind === "failed") {
    return (
      <div data-testid="documents-preview-unavailable">
        <SettingsNotice tone="warning" className="mb-4">
          {preview.message}
          {preview.requestId ? (
            <span className="mt-1 block font-mono text-[length:var(--fs-xs)]">
              Request ID: {preview.requestId}
            </span>
          ) : null}
        </SettingsNotice>
      </div>
    );
  }
  return (
    <div data-testid="documents-preview-idle">
      <SettingsNotice tone="default" className="mb-4">
        Select a Source Document to open its governed preview.
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

function AdminOpsPanel({
  source,
  busy,
  outline,
  outlineStatus,
  onRetryPreparation,
  onCancelPreparation,
  onRetryIndex,
  onCancelIndex,
  onDelete,
}: {
  source: AdminSource;
  busy: boolean;
  outline: OutlineItem[];
  outlineStatus: "idle" | "loading" | "ready" | "unavailable";
  onRetryPreparation: () => void;
  onCancelPreparation: () => void;
  onRetryIndex: () => void;
  onCancelIndex: () => void;
  onDelete: () => void;
}) {
  const loadHistory = useCallback(
    () => listSourceOperations(source.domainId, source.id).then((result) => ({ operations: result.operations })),
    [source.domainId, source.id],
  );

  return (
    <div className="mt-5 space-y-4" data-testid="documents-admin-ops">
      <div>
        <p className="mb-2 font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
          Administrator operations
        </p>
        <dl className="mb-3 space-y-2 text-[length:var(--fs-sm)]">
          <PreviewFact label="Preparation" value={source.state} />
          <PreviewFact label="Index" value={source.indexState} />
          <PreviewFact label="Size" value={formatBytes(source.sizeBytes)} mono />
          <PreviewFact label="Parser" value={source.parserKind} mono />
        </dl>
        <div className="flex flex-wrap gap-1.5" data-testid="documents-admin-actions">
          <SettingsButton
            disabled={busy || !isAdminActionEnabled(source, "retry")}
            onClick={onRetryPreparation}
          >
            Retry preparation
          </SettingsButton>
          <SettingsButton
            disabled={busy || !isAdminActionEnabled(source, "cancel")}
            onClick={onCancelPreparation}
          >
            Cancel preparation
          </SettingsButton>
          <SettingsButton
            disabled={busy || !isAdminActionEnabled(source, "indexRetry")}
            onClick={onRetryIndex}
          >
            Retry index
          </SettingsButton>
          <SettingsButton
            disabled={busy || !isAdminActionEnabled(source, "indexCancel")}
            onClick={onCancelIndex}
          >
            Cancel index
          </SettingsButton>
          <SettingsButton
            tone="danger"
            disabled={busy || !isAdminActionEnabled(source, "delete")}
            onClick={onDelete}
          >
            Delete
          </SettingsButton>
        </div>
      </div>

      <OperationHistoryList testId="source-operation-history" load={loadHistory} />

      <div data-testid="documents-admin-outline">
        <p className="mb-2 font-mono text-[length:var(--fs-xs)] uppercase tracking-[0.12em] text-[var(--dim)]/70">
          Outline
        </p>
        {outlineStatus === "loading" ? (
          <SettingsNotice tone="default">Loading outline…</SettingsNotice>
        ) : null}
        {outlineStatus === "unavailable" ? (
          <SettingsNotice tone="warning">Outline is not available for this source.</SettingsNotice>
        ) : null}
        {outlineStatus === "ready" && outline.length === 0 ? (
          <EmptySafeNotice>No outline items for this source.</EmptySafeNotice>
        ) : null}
        {outline.length > 0 ? (
          <ul className="space-y-1">
            {outline.map((item, index) => (
              <li
                key={`${item.kind}-${item.label}-${item.pageNumber ?? "x"}-${index}`}
                className="rounded-md border border-[var(--ui-border)]/50 px-2.5 py-1.5 text-[length:var(--fs-sm)]"
                data-testid="documents-outline-item"
                data-outline-kind={item.kind}
              >
                <span className="font-mono text-[length:var(--fs-xs)] uppercase text-[var(--dim)]">
                  {item.kind}
                  {item.level != null ? ` L${item.level}` : ""}
                  {item.pageNumber != null ? ` · p.${item.pageNumber}` : ""}
                </span>
                <span className="mt-0.5 block truncate text-[var(--fg)]">{item.label}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
