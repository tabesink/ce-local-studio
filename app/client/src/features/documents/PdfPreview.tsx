"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { SettingsNotice } from "@/_shared/ui";

type PdfPreviewProps = {
  objectUrl: string;
  filename: string;
  /** 1-based page to open; defaults to 1 (document start). */
  initialPage?: number;
};

/**
 * Shared Library PDF viewer (pdf.js). Used for ordinary row select and citation deep-links.
 * Parent owns blob object URL create/revoke lifecycle.
 */
export function PdfPreview({ objectUrl, filename, initialPage = 1 }: PdfPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(() => Math.max(1, initialPage));
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    setPage(Math.max(1, initialPage));
  }, [objectUrl, initialPage]);

  useEffect(() => {
    let cancelled = false;
    let destroyDoc: (() => void) | undefined;

    const run = async () => {
      setStatus("loading");
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

        const viewport = pdfPage.getViewport({ scale: 1.25 });
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
        if (!cancelled) setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    };

    void run();

    return () => {
      cancelled = true;
      destroyDoc?.();
    };
  }, [objectUrl, page]);

  return (
    <div
      className="mb-4 overflow-hidden rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)]"
      data-testid="documents-pdf-preview"
      data-pdfjs="true"
      data-page={page}
      data-page-count={pageCount || undefined}
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
      <div className="flex h-[min(60vh,28rem)] items-start justify-center overflow-auto bg-[var(--ui-bg)] p-2">
        {status === "error" ? (
          <SettingsNotice tone="warning">PDF preview could not be displayed in this browser.</SettingsNotice>
        ) : (
          <canvas
            ref={canvasRef}
            className="max-w-full"
            aria-label={`${filename} PDF preview, page ${page}`}
          />
        )}
      </div>
    </div>
  );
}
