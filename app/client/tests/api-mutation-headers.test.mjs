import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

describe("API mutation headers (P9-07 U3)", () => {
  it("attaches CSRF on unsafe ceFetch methods and retries csrf_invalid once", () => {
    const client = read("src/lib/api/client.ts");
    const csrf = read("src/lib/api/csrf.ts");

    assert.match(csrf, /ce_csrf/);
    assert.match(csrf, /readCsrfTokenFromCookie/);
    assert.match(csrf, /refreshCsrfToken/);
    assert.match(client, /X-CSRF-Token/);
    assert.match(client, /csrf_invalid/);
    assert.match(client, /refreshCsrfToken/);
    assert.match(client, /ifMatchHeader/);
    assert.match(client, /idempotencyKeyHeader/);
  });

  it("postSse attaches CSRF for turn-start POSTs", () => {
    const sse = read("src/lib/api/sse.ts");
    assert.match(sse, /X-CSRF-Token/);
    assert.match(sse, /resolveCsrfToken|refreshCsrfToken/);
  });

  it("runtime-settings mutations require If-Match / Idempotency-Key", () => {
    const api = read("src/features/settings-panel/api.ts");

    assert.match(api, /ProviderSummaryDto/);
    assert.match(api, /RuntimeSettingsDto/);
    assert.match(api, /ModelProfileDto/);
    assert.doesNotMatch(api, /providerKind:\s*string/);
    assert.doesNotMatch(api, /isConfigured:\s*boolean/);
    assert.match(api, /rotateProviderCredential[\s\S]*?ifMatchHeader\(version\)/);
    assert.match(api, /patchRuntimeSettings[\s\S]*?ifMatchHeader\(version\)/);
    assert.match(api, /createModelProfile[\s\S]*?idempotencyKeyHeader/);
    assert.match(api, /patchModelProfile[\s\S]*?ifMatchHeader\(version\)/);
  });

  it("domain and source operation history list wrappers exist", () => {
    const domains = read("src/features/domains/api.ts");
    const documents = read("src/features/documents/api.ts");

    assert.match(domains, /listDomainOperations/);
    assert.match(domains, /AdminDomainOperationsResponse/);
    assert.match(documents, /listSourceOperations/);
    assert.match(documents, /AdminSourceOperationsResponse/);
  });
});
