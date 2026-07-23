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

describe("Phase 1 Library boundary", () => {
  it("preserves only safe return-to-chat ids and ignores raw source navigation params", async () => {
    const { parseLibraryDeepLink, hasChatReturn, buildChatReturnHref } =
      await loadDeepLinkModule();

    const link = parseLibraryDeepLink(
      new URLSearchParams({
        domainId: "private-domain-id",
        sourceId: "private-source-id",
        page: "3",
        conversationId: "conv_1",
        turnId: "turn_9",
      }),
    );

    assert.deepEqual(link, {
      conversationId: "conv_1",
      turnId: "turn_9",
    });
    assert.equal(hasChatReturn(link), true);
    assert.equal(buildChatReturnHref("conv_1", "turn_9"), "/chat?conversationId=conv_1&turnId=turn_9");
  });

  it("requires both conversationId and turnId for Back to chat chrome", async () => {
    const { parseLibraryDeepLink, hasChatReturn } = await loadDeepLinkModule();
    assert.equal(
      hasChatReturn(parseLibraryDeepLink(new URLSearchParams({ conversationId: "c1" }))),
      false,
    );
    assert.equal(hasChatReturn(parseLibraryDeepLink(new URLSearchParams({ turnId: "t1" }))), false);
  });

  it("renders deliberate unavailable states without active member or preview shortcuts", () => {
    const page = readFileSync(join(root, "src/features/documents/DocumentsPage.tsx"), "utf8");
    const api = readFileSync(join(root, "src/features/documents/api.ts"), "utf8");

    assert.match(page, /governed member document library is not available/);
    assert.match(page, /Governed document preview is not available/);
    assert.match(page, /documents-back-to-chat/);
    assert.match(page, /parseLibraryDeepLink/);
    assert.doesNotMatch(page, /PdfPreview/);

    for (const forbidden of ["listMemberSources", "fetchSourcePreview", "/preview"]) {
      assert.equal((page + "\n" + api).includes(forbidden), false, forbidden);
    }
  });
});
