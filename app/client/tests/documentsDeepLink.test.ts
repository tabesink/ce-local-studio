import { describe, expect, it } from "vitest";
import {
  buildDocumentsDeepLinkHref,
  isOpenInLibraryEnabled,
  LIBRARY_SURFACE_AVAILABLE,
} from "@/features/chat-shell/documentsDeepLink";

describe("documentsDeepLink (P9-02)", () => {
  it("builds opaque /documents hrefs from public evidence fields", () => {
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 18,
    });
    expect(href).toBe("/documents?document=doc_safe_7&evidence=ev_safe_12&page=18");
  });

  it("omits page when absent and returns null when refs are missing", () => {
    expect(
      buildDocumentsDeepLinkHref({
        documentRef: "doc_safe_7",
        evidenceRef: "ev_safe_12",
      }),
    ).toBe("/documents?document=doc_safe_7&evidence=ev_safe_12");

    expect(
      buildDocumentsDeepLinkHref({
        documentRef: "doc_safe_7",
        evidenceRef: null,
        page: 3,
      }),
    ).toBeNull();

    expect(
      buildDocumentsDeepLinkHref({
        documentRef: "  ",
        evidenceRef: "ev_safe_12",
      }),
    ).toBeNull();
  });

  it("never enables Open in Library while the Library surface is unavailable", () => {
    expect(LIBRARY_SURFACE_AVAILABLE).toBe(false);
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 1,
    });
    expect(isOpenInLibraryEnabled(href)).toBe(false);
    expect(isOpenInLibraryEnabled(href, false)).toBe(false);
    expect(isOpenInLibraryEnabled(href, true)).toBe(true);
    expect(isOpenInLibraryEnabled(null, true)).toBe(false);
  });

  it("keeps forbidden privacy sentinels out of constructed hrefs", () => {
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 18,
    });
    expect(href).not.toMatch(/s3:\/\//);
    expect(href).not.toMatch(/sourceBlockId/);
    expect(href).not.toMatch(/objectUrl|blob:/);
    expect(href).not.toMatch(/excerpt=/);
  });
});
