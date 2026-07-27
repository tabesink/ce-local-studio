import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

async function loadDeepLinkModule() {
  const moduleUrl = pathToFileURL(join(root, "src/features/documents/libraryDeepLink.ts")).href;
  return import(moduleUrl);
}

describe("Phase 1 Library deep-link boundary (P9-03)", () => {
  it("parses inbound opaque params and builds canonical return-to-chat href", async () => {
    const { parseLibraryDeepLink, hasChatReturn, buildChatReturnHref } = await loadDeepLinkModule();

    const link = parseLibraryDeepLink(
      new URLSearchParams({
        document: "doc_safe_7",
        evidence: "ev_safe_12",
        page: "3",
        conversation: "conv_1",
        turn: "turn_9",
        domainId: "private-domain-id",
        sourceId: "private-source-id",
      }),
    );

    assert.deepEqual(link, {
      document: "doc_safe_7",
      evidence: "ev_safe_12",
      page: 3,
      conversation: "conv_1",
      turn: "turn_9",
    });
    assert.equal(hasChatReturn(link), true);
    assert.equal(
      buildChatReturnHref("conv_1", "turn_9", "ev_safe_12"),
      "/chat?conversation=conv_1&turn=turn_9&evidence=ev_safe_12",
    );
  });

  it("accepts legacy conversationId/turnId inbound for compatibility", async () => {
    const { parseLibraryDeepLink, hasChatReturn, buildChatReturnHref } = await loadDeepLinkModule();
    const link = parseLibraryDeepLink(
      new URLSearchParams({ conversationId: "c1", turnId: "t1" }),
    );
    assert.equal(hasChatReturn(link), true);
    assert.equal(buildChatReturnHref("c1", "t1"), "/chat?conversation=c1&turn=t1");
  });

  it("requires both conversation and turn for Back to chat chrome", async () => {
    const { parseLibraryDeepLink, hasChatReturn } = await loadDeepLinkModule();
    assert.equal(
      hasChatReturn(parseLibraryDeepLink(new URLSearchParams({ conversation: "c1" }))),
      false,
    );
    assert.equal(hasChatReturn(parseLibraryDeepLink(new URLSearchParams({ turn: "t1" }))), false);
  });

  it("wires member library, PdfPreview, and generated adapters without lifted SourceDocument shapes", () => {
    const page = readFileSync(join(root, "src/features/documents/DocumentsPage.tsx"), "utf8");
    const api = readFileSync(join(root, "src/features/documents/api.ts"), "utf8");

    assert.match(page, /listDocuments/);
    assert.match(page, /getEvidenceLocation/);
    assert.match(page, /PdfPreview/);
    assert.match(page, /documents-back-to-chat/);
    assert.match(page, /parseLibraryDeepLink/);
    assert.doesNotMatch(page, /governed member document library is not available/i);
    assert.doesNotMatch(page, /originalFilename/);

    assert.match(api, /DocumentSummaryDto|DocumentSummary/);
    assert.match(api, /AdminSourceDto|AdminSource/);
    assert.match(api, /If-Match/);
    assert.match(api, /getSourceOutline/);
    assert.doesNotMatch(api, /originalFilename/);
    assert.doesNotMatch(api, /originalSha256/);

    for (const forbidden of ["listMemberSources", "fetchSourcePreview", "/preview"]) {
      assert.equal((page + "\n" + api).includes(forbidden), false, forbidden);
    }
  });
});
