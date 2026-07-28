import { existsSync } from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DocumentsPage } from "@/features/documents/DocumentsPage";

const stableSearchParams = new URLSearchParams();
const stableRouter = { push: vi.fn(), replace: vi.fn() };
const stableUser = { id: "user-synth", role: "member" };

vi.mock("next/navigation", () => ({
  useRouter: () => stableRouter,
  useSearchParams: () => stableSearchParams,
}));

vi.mock("@/features/auth/auth-store", () => ({
  useAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
      user: stableUser,
    }),
}));

vi.mock("@/features/domains/api", () => ({
  listMemberDomains: vi.fn().mockResolvedValue([
    {
      id: "synth-alpha",
      displayName: "Synthetic Alpha Domain",
      queryEligible: true,
    },
  ]),
}));

vi.mock("@/features/documents/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/documents/api")>();
  return {
    ...actual,
    listDocuments: vi.fn().mockResolvedValue({
      documents: [
        {
          ref: "doc-synth-one",
          label: "Synthetic Policy Guide.pdf",
          previewKind: "pdf",
          domain: { displayName: "Synthetic Alpha Domain" },
          pageCount: 12,
          updatedAt: "2026-07-01T12:00:00.000Z",
          contentType: "application/pdf",
        },
      ],
      nextCursor: null,
    }),
    listAdminSources: vi.fn().mockResolvedValue([]),
  };
});

const PARITY_ROOT = path.resolve(__dirname, "..");
const U5_TARGETS = [
  "document-library",
  "document-viewer",
  "settings-nav",
  "settings-group",
  "login",
  "graph-unavailable",
] as const;

function ThemeWrap({
  theme,
  children,
}: {
  theme: "zai-dark" | "zai-light";
  children: ReactNode;
}) {
  return <div data-theme={theme}>{children}</div>;
}

describe("Document library parity (R10)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("asserts U5 route-feature parity trios exist", () => {
    for (const name of U5_TARGETS) {
      expect(existsSync(path.join(PARITY_ROOT, "manifests", `${name}.json`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "fixtures", `${name}.html`))).toBe(true);
      expect(existsSync(path.join(PARITY_ROOT, "react", `${name}.test.tsx`))).toBe(true);
    }
  });

  it("renders library header and domain-scoped table rows", async () => {
    render(
      <ThemeWrap theme="zai-dark">
        <DocumentsPage />
      </ThemeWrap>,
    );
    expect(await screen.findByRole("heading", { name: "Source Documents" })).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByLabelText("Knowledge Domain")).toBeInTheDocument();
    expect(await screen.findByText("Synthetic Policy Guide.pdf")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Filter by filename...")).toBeInTheDocument();
  });

  it("shows member read-only library marker without admin upload", async () => {
    render(
      <ThemeWrap theme="zai-light">
        <DocumentsPage />
      </ThemeWrap>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("documents-member-readonly")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("documents-upload-button")).not.toBeInTheDocument();
  });
});
