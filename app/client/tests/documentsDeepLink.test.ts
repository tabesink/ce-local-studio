import { describe, expect, it } from "vitest";
import {
  buildDocumentsDeepLinkHref,
  isOpenInLibraryEnabled,
  LIBRARY_SURFACE_AVAILABLE,
} from "@/features/chat-shell/documentsDeepLink";
import {
  buildChatReturnHref,
  hasChatReturn,
  parseLibraryDeepLink,
} from "@/features/documents/libraryDeepLink";

describe("documentsDeepLink outbound (P9-03 U6)", () => {
  it("builds opaque /documents hrefs from public evidence fields", () => {
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 18,
    });
    expect(href).toBe("/documents?document=doc_safe_7&evidence=ev_safe_12&page=18");
  });

  it("includes return-to-chat conversation/turn when both are present", () => {
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 18,
      conversation: "conv_1",
      turn: "turn_9",
    });
    expect(href).toBe(
      "/documents?document=doc_safe_7&evidence=ev_safe_12&page=18&conversation=conv_1&turn=turn_9",
    );
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

  it("enables Open in Library when the Library surface is available and refs exist", () => {
    expect(LIBRARY_SURFACE_AVAILABLE).toBe(true);
    const href = buildDocumentsDeepLinkHref({
      documentRef: "doc_safe_7",
      evidenceRef: "ev_safe_12",
      page: 1,
    });
    expect(isOpenInLibraryEnabled(href)).toBe(true);
    expect(isOpenInLibraryEnabled(href, false)).toBe(false);
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

describe("libraryDeepLink inbound + return (P9-03 U4)", () => {
  it("parses document, evidence, page and canonical return params", () => {
    const link = parseLibraryDeepLink(
      new URLSearchParams({
        document: "doc_safe_7",
        evidence: "ev_safe_12",
        page: "18",
        conversation: "conv_1",
        turn: "turn_9",
      }),
    );
    expect(link).toEqual({
      document: "doc_safe_7",
      evidence: "ev_safe_12",
      page: 18,
      conversation: "conv_1",
      turn: "turn_9",
    });
    expect(hasChatReturn(link)).toBe(true);
  });

  it("accepts legacy conversationId/turnId inbound but builds canonical return href", () => {
    const link = parseLibraryDeepLink(
      new URLSearchParams({
        conversationId: "conv_legacy",
        turnId: "turn_legacy",
        evidence: "ev_safe_12",
        domainId: "private-domain-id",
        sourceId: "private-source-id",
      }),
    );
    expect(link.conversation).toBe("conv_legacy");
    expect(link.turn).toBe("turn_legacy");
    expect(link.document).toBeNull();
    expect(buildChatReturnHref(link.conversation!, link.turn!, link.evidence)).toBe(
      "/chat?conversation=conv_legacy&turn=turn_legacy&evidence=ev_safe_12",
    );
  });

  it("ignores non-positive page values", () => {
    expect(parseLibraryDeepLink(new URLSearchParams({ page: "0" })).page).toBeNull();
    expect(parseLibraryDeepLink(new URLSearchParams({ page: "-2" })).page).toBeNull();
    expect(parseLibraryDeepLink(new URLSearchParams({ page: "abc" })).page).toBeNull();
  });
});
