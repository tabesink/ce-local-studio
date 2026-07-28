"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, RotateCw } from "lucide-react";
import { SettingsNotice } from "@/_shared/ui";
import {
  focusAnnouncement,
  prefersReducedMotion,
  resolveHighlightRect,
  type AnchorFallback,
  type NormalizedRegion,
} from "@/features/documents/pdfAnchorFocus";

export type PdfPreviewAnchor = {
  pageNumber: number;
  region?: NormalizedRegion | null;
  sectionLabel?: string | null;
  fallback: AnchorFallback;
  evidenceKind?: string | null;
};

type PdfPreviewProps = {
  objectUrl: string;
  filename: string;
  /** 1-based page to open; defaults to 1 (document start). */
  initialPage?: number;
  /** Authorized location anchor; ignored when null/undefined. */
  anchor?: PdfPreviewAnchor | null;
  /** Bumps when a newer location supersedes a prior highlight. */
  anchorGeneration?: number;
};

/**
 * Shared Library PDF viewer (pdf.js). Used for ordinary row select and citation deep-links.
 * Parent owns blob object URL create/revoke lifecycle.
 */
export function PdfPreview({
  objectUrl,
  filename,
  initialPage = 1,
  anchor = null,
  anchorGeneration = 0,
}: PdfPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(() => Math.max(1, initialPage));
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [rotation, setRotation] = useState(0);
  const [scale, setScale] = useState(1.25);
  const [highlight, setHighlight] = useState<{
    left: number;
    top: number;
    width: number;
    height: number;
    mode: "region" | "containing-block";
  } | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);

  useEffect(() => {
    setPage(Math.max(1, initialPage));
  }, [objectUrl, initialPage]);

  useEffect(() => {
    setRotation(0);
    setScale(1.25);
    setHighlight(null);
    setStatusText(null);
  }, [objectUrl, anchorGeneration]);

  useEffect(() => {
    let cancelled = false;
    let destroyDoc: (() => void) | undefined;

    const run = async () => {
      setStatus("loading");
      setHighlight(null);
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();

        const loadingTask = pdfjs.getDocument(objectUrl);
        const pdf = await loadingTask.promise;
        destroyDoc = () => {
          void pdf.destroy();
        };
        if (cancelled) {
          destroyDoc();
          return;
        }

        const total = pdf.numPages;
        setPageCount(total);
        const pageNumber = Math.min(Math.max(1, page), total);
        if (pageNumber !== page) {
          setPage(pageNumber);
          return;
        }

        const pdfPage = await pdf.getPage(pageNumber);
        if (cancelled) return;

        const viewport = pdfPage.getViewport({ scale, rotation });
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext("2d");
        if (!context) {
          setStatus("error");
          return;
        }

        canvas.height = viewport.height;
        canvas.width = viewport.width;
        await pdfPage.render({ canvasContext: context, viewport }).promise;
        if (cancelled) return;

        const activeAnchor =
          anchor && anchor.pageNumber === pageNumber
            ? anchor
            : null;
        const resolved = activeAnchor
          ? resolveHighlightRect({
              region: activeAnchor.region,
              fallback: activeAnchor.fallback,
              evidenceKind: activeAnchor.evidenceKind,
              canvasWidth: viewport.width,
              canvasHeight: viewport.height,
              rotation,
            })
          : null;

        if (resolved) {
          setHighlight({ ...resolved.rect, mode: resolved.mode });
          setStatusText(
            focusAnnouncement({
              evidenceKind: activeAnchor?.evidenceKind,
              pageNumber,
              sectionLabel: activeAnchor?.sectionLabel,
              mode: resolved.mode,
            }),
          );
        } else if (activeAnchor?.fallback === "section" && activeAnchor.sectionLabel) {
          setHighlight(null);
          setStatusText(
            focusAnnouncement({
              evidenceKind: activeAnchor.evidenceKind,
              pageNumber,
              sectionLabel: activeAnchor.sectionLabel,
              mode: "section",
            }),
          );
        } else {
          setHighlight(null);
          setStatusText(null);
        }

        setStatus("ready");
      } catch {
        if (!cancelled) {
          setStatus("error");
          setHighlight(null);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      destroyDoc?.();
    };
  }, [objectUrl, page, rotation, scale, anchor, anchorGeneration]);

  useEffect(() => {
    if (status !== "ready" || !highlightRef.current) return;
    const node = highlightRef.current;
    if (typeof node.focus === "function") {
      node.focus({ preventScroll: true });
    }
    if (typeof node.scrollIntoView === "function") {
      node.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: prefersReducedMotion() ? "auto" : "smooth",
      });
    }
  }, [status, highlight, page, rotation, scale, anchorGeneration]);

  return (
    <div
      className="mb-4 overflow-hidden rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)]"
      data-testid="documents-pdf-preview"
      data-pdfjs="true"
      data-page={page}
      data-page-count={pageCount || undefined}
      data-rotation={rotation}
      data-scale={scale}
      data-anchor-state={highlight ? "anchor-focused" : status === "ready" ? "ready" : status}
    >
      <div className="flex h-8 items-center justify-between gap-2 border-b border-[var(--ui-border)] px-2">
        <button
          type="button"
          aria-label="Previous page"
          disabled={page <= 1 || status === "loading"}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
          className="flex h-6 w-6 items-center justify-center rounded text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:pointer-events-none disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <span className="font-mono text-[length:var(--fs-xs)] text-[var(--dim)]" data-testid="documents-pdf-page-label">
          {pageCount > 0 ? `Page ${page} of ${pageCount}` : "Loading…"}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Rotate page"
            disabled={status === "loading"}
            onClick={() => setRotation((current) => (current + 90) % 360)}
            className="flex h-6 w-6 items-center justify-center rounded text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:pointer-events-none disabled:opacity-40"
          >
            <RotateCw className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            aria-label="Zoom in"
            disabled={status === "loading" || scale >= 2}
            onClick={() => setScale((current) => Math.min(2, Number((current + 0.25).toFixed(2))))}
            className="flex h-6 w-6 items-center justify-center rounded text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:pointer-events-none disabled:opacity-40"
          >
            +
          </button>
          <button
            type="button"
            aria-label="Next page"
            disabled={pageCount === 0 || page >= pageCount || status === "loading"}
            onClick={() => setPage((current) => (pageCount ? Math.min(pageCount, current + 1) : current))}
            className="flex h-6 w-6 items-center justify-center rounded text-[var(--dim)] hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="flex h-[min(60vh,28rem)] items-start justify-center overflow-auto bg-[var(--ui-bg)] p-2">
        {status === "error" ? (
          <SettingsNotice tone="warning">PDF preview could not be displayed in this browser.</SettingsNotice>
        ) : (
          <div className="relative inline-block max-w-full">
            <canvas
              ref={canvasRef}
              className="max-w-full"
              aria-label={`${filename} PDF preview, page ${page}`}
            />
            {highlight ? (
              <div
                ref={highlightRef}
                data-testid="evidence-highlight"
                data-highlight-mode={highlight.mode}
                tabIndex={-1}
                className="pointer-events-none absolute box-border border-2 border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_22%,transparent)] outline-none"
                style={{
                  left: highlight.left,
                  top: highlight.top,
                  width: highlight.width,
                  height: highlight.height,
                }}
                aria-label={statusText ?? "Evidence highlight"}
              />
            ) : null}
          </div>
        )}
      </div>
      <div className="sr-only" aria-live="polite" data-testid="documents-pdf-anchor-status">
        {statusText}
      </div>
    </div>
  );
}
