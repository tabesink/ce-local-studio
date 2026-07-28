import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PdfPreview } from "@/features/documents/PdfPreview";

vi.mock("pdfjs-dist", () => {
  const mockPage = {
    getViewport: () => ({ height: 200, width: 150 }),
    render: () => ({ promise: Promise.resolve() }),
  };
  const mockPdf = {
    numPages: 12,
    getPage: vi.fn().mockResolvedValue(mockPage),
    destroy: vi.fn(),
  };
  return {
    GlobalWorkerOptions: { workerSrc: "" },
    getDocument: vi.fn(() => ({
      promise: Promise.resolve(mockPdf),
    })),
  };
});

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Document viewer parity (R10)", () => {
  beforeEach(() => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      canvas: document.createElement("canvas"),
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  });

  it("renders pdf viewer chrome with page navigation", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="Synthetic Policy Guide.pdf"
          initialPage={2}
        />
      </ThemeWrap>,
    );
    const preview = screen.getByTestId("documents-pdf-preview");
    expect(preview).toHaveAttribute("data-pdfjs", "true");
    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("documents-pdf-page-label")).toHaveTextContent("Page 2 of 12");
    });
  });

  it("keeps page navigation keyboard-focusable", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-light">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="Synthetic Policy Guide.pdf"
          initialPage={1}
        />
      </ThemeWrap>,
    );
    const next = screen.getByRole("button", { name: "Next page" });
    await waitFor(() => {
      expect(next).not.toBeDisabled();
    });
    next.focus();
    expect(next).toHaveFocus();
    await user.click(next);
    await waitFor(() => {
      expect(screen.getByTestId("documents-pdf-page-label")).toHaveTextContent("Page 2 of 12");
    });
  });

  it("exposes canvas region with filename aria-label", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="Synthetic Policy Guide.pdf"
          initialPage={2}
        />
      </ThemeWrap>,
    );
    await waitFor(() => {
      expect(
        screen.getByLabelText("Synthetic Policy Guide.pdf PDF preview, page 2"),
      ).toBeInTheDocument();
    });
  });

  it("focuses figure region highlight from authorized location anchor", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="pump-manual.pdf"
          initialPage={2}
          anchorGeneration={1}
          anchor={{
            pageNumber: 2,
            region: { x: 0.12, y: 0.24, width: 0.66, height: 0.41 },
            sectionLabel: "4.2 Relief valve",
            fallback: "region",
            evidenceKind: "figure",
          }}
        />
      </ThemeWrap>,
    );
    const highlight = await screen.findByTestId("evidence-highlight");
    expect(highlight).toHaveAttribute("data-highlight-mode", "region");
    expect(screen.getByTestId("documents-pdf-preview")).toHaveAttribute(
      "data-anchor-state",
      "anchor-focused",
    );
    expect(screen.getByTestId("documents-pdf-anchor-status")).toHaveTextContent(
      "Figure on page 2 focused.",
    );
  });

  it("keeps region highlight geometry after rotate", async () => {
    const user = userEvent.setup();
    render(
      <ThemeWrap theme="zai-light">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="pump-manual.pdf"
          initialPage={12}
          anchorGeneration={2}
          anchor={{
            pageNumber: 12,
            region: { x: 0.1, y: 0.3, width: 0.8, height: 0.34 },
            fallback: "region",
            evidenceKind: "table",
          }}
        />
      </ThemeWrap>,
    );
    const highlight = await screen.findByTestId("evidence-highlight");
    const before = highlight.getAttribute("style");
    await user.click(screen.getByRole("button", { name: "Rotate page" }));
    await waitFor(() => {
      expect(screen.getByTestId("documents-pdf-preview")).toHaveAttribute("data-rotation", "90");
      expect(screen.getByTestId("evidence-highlight").getAttribute("style")).not.toBe(before);
    });
  });

  it("uses containing-block highlight for figure without region", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="pump-manual.pdf"
          initialPage={3}
          anchor={{
            pageNumber: 3,
            region: null,
            fallback: "section",
            sectionLabel: "Inspection",
            evidenceKind: "figure",
          }}
        />
      </ThemeWrap>,
    );
    const highlight = await screen.findByTestId("evidence-highlight");
    expect(highlight).toHaveAttribute("data-highlight-mode", "containing-block");
  });

  it("drops stale highlight when anchor generation changes to empty", async () => {
    const { rerender } = render(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="pump-manual.pdf"
          initialPage={2}
          anchorGeneration={1}
          anchor={{
            pageNumber: 2,
            region: { x: 0.12, y: 0.24, width: 0.66, height: 0.41 },
            fallback: "region",
            evidenceKind: "figure",
          }}
        />
      </ThemeWrap>,
    );
    await screen.findByTestId("evidence-highlight");
    rerender(
      <ThemeWrap theme="zai-dark">
        <PdfPreview
          objectUrl="blob:synthetic-preview"
          filename="pump-manual.pdf"
          initialPage={2}
          anchorGeneration={2}
          anchor={null}
        />
      </ThemeWrap>,
    );
    await waitFor(() => {
      expect(screen.queryByTestId("evidence-highlight")).not.toBeInTheDocument();
    });
  });
});
