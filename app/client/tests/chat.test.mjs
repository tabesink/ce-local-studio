import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const src = join(root, "src");

function read(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (entry === "node_modules" || entry === ".next") return [];
    if (statSync(path).isDirectory()) return walk(path);
    return [path];
  });
}

function sourceFiles() {
  return walk(src).filter((file) => /\.(ts|tsx)$/.test(file));
}

describe("F-012 chat via LS chat-shell", () => {
  it("routes /chat through the chat-shell feature module", () => {
    const page = read("src/app/chat/page.tsx");
    assert.match(page, /features\/chat-shell\/ChatShell/);
    assert.match(page, /force-dynamic/);
  });

  it("keeps chat network calls behind the slice adapter and shared SSE wrappers", () => {
    const api = read("src/features/chat-shell/api.ts");
    assert.match(api, /TurnDto/);
    assert.match(api, /EvidenceItemDto/);
    assert.match(api, /ConversationSummaryDto/);
    assert.match(api, /ConversationDetailResponseDto/);
    assert.match(api, /"\/composer-refs:discover"/);
    assert.match(api, /composerRefTokens/);
    assert.match(api, /postSse/);
    assert.match(api, /runResumableTurnStream/);
    assert.match(api, /consumer\.snapshot\(\)\.turnId/);

    const offenders = sourceFiles()
      .filter((file) => !file.endsWith(join("src", "lib", "api", "client.ts")))
      .filter((file) => !file.endsWith(join("src", "lib", "api", "sse.ts")))
      .filter((file) => !file.endsWith(join("src", "lib", "server", "bff-proxy.ts")))
      .filter((file) => /\bfetch\s*\(/.test(readFileSync(file, "utf8")))
      .map((file) => relative(root, file));
    assert.deepEqual(offenders, []);
  });

  it("feeds live and replay streams through the canonical lib/stream reducer", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /reduceTurnStreamEvent/);
    assert.match(hook, /from "@\/lib\/stream"/);
    assert.equal(hook.includes("applyTurnStreamEvent"), false, "hook must not embed a parallel applyTurnStreamEvent path");
    assert.equal(hook.includes("discoverComposerRefs"), false, "KTD1: zero discoverComposerRefs in hook");
    assert.equal(hook.includes("mentionQuery"), false, "hook must not own interactive @ mention discovery");

    const reducer = read("src/lib/stream/reducer.ts");
    for (const event of [
      '"turn.accepted"',
      '"route.selected"',
      '"retrieval.started"',
      '"retrieval.completed"',
      '"evidence.delta"',
      '"answer.delta"',
      '"turn.completed"',
      '"turn.failed"',
      '"turn.cancelled"',
      '"turn.redacted"',
    ]) {
      assert.match(reducer, new RegExp(`case ${event}`));
    }

    const protocol = read("src/lib/stream/turn-consumer.ts");
    assert.match(protocol, /schemaVersion\.split\("\."\)\[0\] !== "1"/);
    assert.match(protocol, /receivedSequence/);
    assert.match(protocol, /appliedSequence/);
    assert.match(protocol, /sequence gap/);
    assert.match(protocol, /frame\.id !== eventId/);
    assert.match(protocol, /closed before a terminal event/);
    const protocolReexport = read("src/features/chat-shell/stream-protocol.ts");
    assert.match(protocolReexport, /@\/lib\/stream/);
    const sse = read("src/lib/api/sse.ts");
    assert.match(sse, /response\.body\.getReader\(\)/);
    assert.match(sse, /attachTerminalSnapshot|terminalSnapshot/);
    const parser = read("src/lib/stream/sse-parser.ts");
    assert.match(parser, /ended mid-frame/);
    const parserReexport = read("src/lib/api/sse-parser.ts");
    assert.match(parserReexport, /@\/lib\/stream\/sse-parser/);

    assert.match(hook, /onEvent: handleStreamEvent/);
    assert.match(hook, /streamConversationTurn\([\s\S]*?onEvent: handleStreamEvent/);
    assert.match(
      hook,
      /streamConversationTurnEvents\(\{[\s\S]*?onEvent: handleStreamEvent/,
      "durable replay must feed the same canonical stream handler",
    );
    assert.equal(hook.includes("handleReplayEvent"), false, "replay must not use an error-only event handler");
    assert.match(hook, /streamTransportState/);
    assert.match(hook, /composerRefTokens: \[\]/);
    assert.match(hook, /isCursorExpiredError/);
    assert.match(hook, /getTerminalSnapshotFromError/);
    assert.match(hook, /domain_required/);
    assert.match(hook, /idempotency_conflict/);

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /acceptedRefs/);
    assert.match(component, /Evidence/);
    assert.match(component, /data-testid="ref-picker"/);
    assert.match(component, /aria-disabled/);
  });

  it("does not port uncontracted Local Studio agent controls", () => {
    const combined = ["src/features/chat-shell/ChatShell.tsx", "src/features/chat-shell/use-chat-shell.ts"]
      .map(read)
      .join("\n");
    for (const forbidden of [
      "abort(",
      "modelId",
      "browserToolEnabled",
      "cwd",
      "terminalTool",
      "enableTerminal",
      "PiTerminal",
    ]) {
      assert.equal(combined.includes(forbidden), false, forbidden);
    }
  });

  it("renders evidence in the turn-scoped inspector, not as timeline blocks", () => {
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    assert.match(panel, /citationLabel/);
    assert.match(panel, /sourceLabel/);
    assert.match(panel, /excerpt/);
    assert.match(panel, /onSelectEvidence/);
    assert.match(panel, /inspector-tab-evidence/);
    assert.match(panel, /inspector-tab-refs/);
    assert.match(panel, /inspector-tab-source/);
    assert.match(panel, /role="complementary"/);
    assert.equal(/\bfetch\s*\(/.test(panel), false, "Evidence Panel must not fetch");

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /<EvidencePanel/);
    assert.match(component, /panelEvidence/);
    assert.match(component, /panelAcceptedRefs/);

    const types = read("src/features/chat-shell/types.ts");
    assert.equal(types.includes('kind: "evidence"'), false, "evidence is not a timeline block kind");
  });

  it("scopes the panel to the current or selected turn and auto-opens on evidence", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /selectedTurnId/);
    assert.match(hook, /selectTurn/);
    assert.match(hook, /panelEvidence/);
    assert.match(hook, /setPanelOpen\(true\)/);
    assert.match(hook, /inspectorFenceRef|bumpInspectorFence/);
    // No private source identifiers or session-ledger port in panel state.
    for (const forbidden of ["sourceBlockId", "documentId", "chunkId", "sessionContextLedger", "pinned"]) {
      assert.equal(hook.includes(forbidden), false, forbidden);
    }
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    for (const forbidden of ["sourceBlockId", "documentId", "chunkId", "thumbnailUrl", "assetId"]) {
      assert.equal(panel.includes(forbidden), false, forbidden);
    }
  });

  it("gates interactive composer-ref discovery and submits empty opaque tokens", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.equal(hook.includes("discoverComposerRefs"), false);
    assert.equal(hook.includes("mentionQuery"), false);
    assert.match(hook, /composerRefTokens: \[\]/);
    assert.equal(hook.includes("template.body"), false);
    assert.equal(hook.includes("sourceText"), false);

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /data-testid="ref-picker"/);
    assert.match(component, /References discovery is unavailable|References unavailable/);
  });

  it("builds opaque Library deep links and keeps privacy sentinels out of hrefs", () => {
    const deepLink = read("src/features/chat-shell/documentsDeepLink.ts");
    assert.match(deepLink, /buildDocumentsDeepLinkHref/);
    assert.match(deepLink, /\/documents\?/);
    assert.match(deepLink, /document/);
    assert.match(deepLink, /evidence/);
    assert.match(deepLink, /page/);
    assert.match(deepLink, /LIBRARY_SURFACE_AVAILABLE/);

    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    assert.match(panel, /documentsDeepLink/);
    assert.match(panel, /open-in-library/);
    assert.match(panel, /document-navigation-unavailable/);

    const sources = [
      read("src/features/chat-shell/api.ts"),
      read("src/features/chat-shell/use-chat-shell.ts"),
      read("src/features/chat-shell/ChatShell.tsx"),
      panel,
      deepLink,
    ];
    for (const source of sources) {
      for (const forbidden of [
        "resolveEvidenceSourceRef",
        "/evidence-refs/",
        "s3://",
        "objectUrl",
        "sourceBlockId",
      ]) {
        assert.equal(source.includes(forbidden), false, forbidden);
      }
    }
  });

  it("bootstraps /chat return params by loading conversation and selecting the jump-from turn", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /loadConversation = useCallback\(\s*async \(conversationId: string, options\?: \{ turnId\?/);
    assert.match(hook, /setSelectedTurnId\(restoreTurn\.id\)/);
    assert.match(hook, /setPanelOpen\(restoreTurn\.evidence\.length > 0\)/);

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /useSearchParams/);
    assert.match(component, /conversationId/);
    assert.match(component, /turnId/);
    assert.match(component, /loadConversation\(conversationId, \{ turnId \}\)/);
  });

  it("migrates covered chat-shell kit imports to @/ui", () => {
    const component = read("src/features/chat-shell/ChatShell.tsx");
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    assert.match(component, /from "@\/ui"/);
    assert.match(panel, /from "@\/ui"/);
    assert.equal(component.includes("@/_shared/ui"), false);
    assert.equal(panel.includes("@/_shared/ui"), false);
  });
});
