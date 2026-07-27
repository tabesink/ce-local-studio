import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function readDomainsApi() {
  return readFileSync(join(root, "src/features/domains/api.ts"), "utf8");
}

describe("Domains API closed DTO alignment (P9-04 U2)", () => {
  it("does not expose storageSummary or available public type fields", () => {
    const source = readDomainsApi();

    assert.doesNotMatch(source, /storageSummary/);
    assert.doesNotMatch(source, /\bavailable\s*:/);
  });

  it("parses start/stop as DomainOperationMutationResponse {operation}", () => {
    const source = readDomainsApi();

    assert.match(source, /OperationDto/);
    assert.match(source, /DomainOperationMutationResponse/);
    assert.match(source, /startDomain[\s\S]*?return body\.operation/);
    assert.match(source, /stopDomain[\s\S]*?return body\.operation/);
    assert.doesNotMatch(source, /startDomain[\s\S]*?return body\.domain/);
    assert.doesNotMatch(source, /stopDomain[\s\S]*?return body\.domain/);
  });

  it("deleteDomain requires version and sends If-Match", () => {
    const source = readDomainsApi();

    assert.match(source, /deleteDomain\s*\(\s*domainId\s*:\s*string\s*,\s*version/);
    assert.match(source, /If-Match/);
    assert.match(source, /ifMatchHeader/);
    assert.match(source, /version == null|version === ""|version == null \|\| version === ""/);
  });

  it("MemberDomain / DomainSummaryDto uses queryEligible", () => {
    const source = readDomainsApi();
    const openapi = readFileSync(join(root, "src/lib/api/generated/openapi.ts"), "utf8");
    const chatShell = readFileSync(join(root, "src/features/chat-shell/ChatShell.tsx"), "utf8");
    const documentsPage = readFileSync(join(root, "src/features/documents/DocumentsPage.tsx"), "utf8");

    assert.match(source, /DomainSummaryDto/);
    assert.match(
      source,
      /export type MemberDomain = components\["schemas"\]\["DomainSummaryDto"\]/,
    );
    assert.doesNotMatch(source, /\bavailable\s*:/);

    // Field lives on the generated closed DTO; call sites must use it (not available).
    assert.match(openapi, /DomainSummaryDto:[\s\S]*?queryEligible:\s*boolean/);
    assert.match(chatShell, /domain\.queryEligible/);
    assert.match(documentsPage, /domain\.queryEligible/);
    assert.doesNotMatch(chatShell, /domain\.available/);
    assert.doesNotMatch(documentsPage, /domain\.available/);
  });
});
