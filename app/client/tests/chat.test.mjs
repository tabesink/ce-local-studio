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

  it("translates EVT-001 SSE events into LS timeline blocks", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    const applicationPath = hook.match(
      /const applyTurnStreamEvent = useCallback\(\(event: TurnStreamEvent\) => \{[\s\S]*?\n  \}, \[\]\);/,
    )?.[0];
    assert.ok(applicationPath, "chat streams must use one canonical event application callback");
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
      assert.match(applicationPath, new RegExp(`event\.type === ${event}`));
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
    assert.match(
      hook,
      /const handleLiveStreamEvent = useCallback\([\s\S]*?=> applyTurnStreamEvent\(event\),/,
      "live streaming must feed the canonical event application callback",
    );
    assert.match(hook, /streamConversationTurn\([\s\S]*?onEvent: handleLiveStreamEvent/);
    assert.match(
      hook,
      /streamConversationTurnEvents\(\{[\s\S]*?onEvent: applyTurnStreamEvent/,
      "durable replay must feed the same canonical event application callback",
    );
    assert.equal(hook.includes("handleReplayEvent"), false, "replay must not use an error-only event handler");
    assert.match(hook, /streamTransportState/);
    assert.match(hook, /setInput\(\(current\) => current \|\| message\)/);
    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /acceptedRefs/);
    assert.match(component, /Evidence/);
    assert.match(component, /SegmentedControl/);
  });

  it("does not port uncontracted Local Studio agent controls", () => {
    const combined = ["src/features/chat-shell/ChatShell.tsx", "src/features/chat-shell/use-chat-shell.ts"]
      .map(read)
      .join("\n");
    for (const forbidden of ["abort(", "modelId", "browserToolEnabled", "cwd", "terminal"]) {
      assert.equal(combined.includes(forbidden), false, forbidden);
    }
  });

  it("renders evidence in the turn-scoped Evidence Panel, not as timeline blocks", () => {
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    assert.match(panel, /citationLabel/);
    assert.match(panel, /sourceLabel/);
    assert.match(panel, /excerpt/);
    assert.match(panel, /onSelectEvidence/);
    assert.equal(/\bfetch\s*\(/.test(panel), false, "Evidence Panel must not fetch");

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /<EvidencePanel/);
    assert.match(component, /panelEvidence/);

    const types = read("src/features/chat-shell/types.ts");
    assert.equal(types.includes('kind: "evidence"'), false, "evidence is not a timeline block kind");
  });

  it("scopes the panel to the current or selected turn and auto-opens on evidence", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /selectedTurnId/);
    assert.match(hook, /selectTurn/);
    assert.match(hook, /panelEvidence/);
    assert.match(hook, /setPanelOpen\(true\)/);
    // No private source identifiers or session-ledger port in panel state.
    for (const forbidden of ["sourceBlockId", "documentId", "chunkId", "sessionContextLedger", "pinned"]) {
      assert.equal(hook.includes(forbidden), false, forbidden);
    }
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");
    for (const forbidden of ["sourceBlockId", "documentId", "chunkId", "thumbnailUrl", "assetId"]) {
      assert.equal(panel.includes(forbidden), false, forbidden);
    }
  });

  it("owns composer picker state in the hook and submits opaque ref tokens only", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /mentionQuery/);
    assert.match(hook, /lastIndexOf\("@"/);
    assert.match(hook, /composerRefTokens: refs\.map\(\(ref\) => ref\.refToken\)/);
    assert.equal(hook.includes("template.body"), false);
    assert.equal(hook.includes("sourceText"), false);
  });

  it("keeps document navigation unavailable until governed opaque routes exist", () => {
    const api = read("src/features/chat-shell/api.ts");
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    const component = read("src/features/chat-shell/ChatShell.tsx");
    const panel = read("src/features/chat-shell/EvidencePanel.tsx");

    for (const source of [api, hook, component, panel]) {
      for (const forbidden of [
        "resolveEvidenceSourceRef",
        "/evidence-refs/",
        "openEvidenceInLibrary",
        "buildLibraryDeepLinkHref",
        "onOpenInLibrary",
        "open-in-library",
      ]) {
        assert.equal(source.includes(forbidden), false, forbidden);
      }
    }

    assert.match(panel, /evidence-selected-detail/);
    assert.match(panel, /document-navigation-unavailable/);
    assert.match(panel, /Document navigation is unavailable/);
    assert.match(panel, /governed evidence-location/);
    assert.equal(/\bfetch\s*\(/.test(panel), false, "Evidence Panel must not fetch");
  });

  it("bootstraps /chat return params by loading conversation and selecting the jump-from turn", () => {
    const hook = read("src/features/chat-shell/use-chat-shell.ts");
    assert.match(hook, /loadConversation = useCallback\(async \(conversationId: string, options\?: \{ turnId\?/);
    assert.match(hook, /setSelectedTurnId\(restoreTurn\.id\)/);
    assert.match(hook, /setPanelOpen\(restoreTurn\.evidence\.length > 0\)/);

    const component = read("src/features/chat-shell/ChatShell.tsx");
    assert.match(component, /useSearchParams/);
    assert.match(component, /conversationId/);
    assert.match(component, /turnId/);
    assert.match(component, /loadConversation\(conversationId, \{ turnId \}\)/);
  });
});
