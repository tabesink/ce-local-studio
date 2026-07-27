import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { proxyContextEngineRequest, resolveBffProxyConfig } from "../src/lib/server/bff-proxy.ts";

const config = {
  apiBase: new URL("http://api.internal:8000"),
  publicOrigin: new URL("https://context.example.test"),
};

describe("same-origin Context Engine BFF", () => {
  it("fails closed when production public origin is absent", () => {
    assert.throws(
      () => resolveBffProxyConfig({ NODE_ENV: "production", CONTEXT_ENGINE_API_BASE: "http://api:8000" }),
      /Public origin is required/,
    );
  });

  it("uses only the configured upstream and allowlisted request headers", async () => {
    let capturedUrl;
    let capturedInit;
    const request = new Request("https://attacker.invalid/api/v1/conversations/c1/turns:stream?after=2", {
      method: "POST",
      headers: {
        accept: "text/event-stream",
        authorization: "Bearer forbidden",
        cookie: "ce_session=opaque",
        "content-type": "application/json",
        host: "attacker.invalid",
        origin: "https://attacker.invalid",
        "x-csrf-token": "csrf-safe",
        "x-user-id": "forbidden-user",
        "x-forwarded-for": "203.0.113.7",
        "x-upstream-url": "https://attacker.invalid",
      },
      body: '{"message":"hello"}',
      duplex: "half",
    });
    const response = await proxyContextEngineRequest(request, ["conversations", "c1", "turns:stream"], config, async (url, init) => {
      capturedUrl = String(url);
      capturedInit = init;
      return new Response("stream", { status: 200, headers: { "content-type": "text/event-stream" } });
    });

    assert.equal(capturedUrl, "http://api.internal:8000/api/v1/conversations/c1/turns%3Astream?after=2");
    const headers = new Headers(capturedInit.headers);
    assert.equal(headers.get("accept"), "text/event-stream");
    assert.equal(headers.get("cookie"), "ce_session=opaque");
    assert.equal(headers.get("x-csrf-token"), "csrf-safe");
    assert.equal(headers.get("origin"), "https://context.example.test");
    assert.equal(headers.get("x-forwarded-host"), "context.example.test");
    assert.equal(headers.get("x-forwarded-proto"), "https");
    for (const forbidden of ["authorization", "host", "x-user-id", "x-forwarded-for", "x-upstream-url"]) {
      assert.equal(headers.has(forbidden), false, forbidden);
    }
    assert.equal(capturedInit.signal, request.signal);
    assert.equal(capturedInit.redirect, "manual");
    assert.equal(await response.text(), "stream");
  });

  it("forwards Range and If-Range for governed document content", async () => {
    let capturedInit;
    const request = new Request("https://context.example.test/api/v1/documents/doc1/content", {
      method: "GET",
      headers: {
        range: "bytes=0-1023",
        "if-range": '"preview-etag-1"',
        cookie: "ce_session=opaque",
        authorization: "Bearer forbidden",
      },
    });
    const response = await proxyContextEngineRequest(request, ["documents", "doc1", "content"], config, async (_url, init) => {
      capturedInit = init;
      return new Response("pdf-slice", {
        status: 206,
        headers: {
          "accept-ranges": "bytes",
          "content-range": "bytes 0-1023/4096",
          "content-type": "application/pdf",
          etag: '"preview-etag-1"',
          "content-disposition": 'inline; filename="manual.pdf"',
        },
      });
    });

    const headers = new Headers(capturedInit.headers);
    assert.equal(headers.get("range"), "bytes=0-1023");
    assert.equal(headers.get("if-range"), '"preview-etag-1"');
    assert.equal(headers.has("authorization"), false);
    assert.equal(response.status, 206);
    assert.equal(response.headers.get("content-range"), "bytes 0-1023/4096");
    assert.equal(response.headers.get("etag"), '"preview-etag-1"');
    assert.equal(response.headers.get("accept-ranges"), "bytes");
    assert.equal(response.headers.get("cache-control"), "private, no-store, no-transform");
    assert.equal(await response.text(), "pdf-slice");
  });

  it("forwards X-Content-Type-Options nosniff on document content", async () => {
    const request = new Request("https://context.example.test/api/v1/documents/doc1/content", {
      method: "GET",
      headers: { cookie: "ce_session=opaque" },
    });
    const response = await proxyContextEngineRequest(request, ["documents", "doc1", "content"], config, async () =>
      new Response("%PDF", {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "x-content-type-options": "nosniff",
          etag: '"preview-etag-1"',
        },
      }),
    );
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("cache-control"), "private, no-store, no-transform");
  });

  it("streams the upstream body and exposes only safe no-store response headers", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode("first"));
        controller.enqueue(encoder.encode("-second"));
        controller.close();
      },
    });
    const response = await proxyContextEngineRequest(
      new Request("https://context.example.test/api/v1/conversations", { method: "GET" }),
      ["conversations"],
      config,
      async () => new Response(body, {
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "public, max-age=3600",
          "set-cookie": "ce_session=rotated; HttpOnly",
          "x-private-trace": "forbidden",
          "x-request-id": "request-safe",
        },
      }),
    );
    assert.equal(await response.text(), "first-second");
    assert.equal(response.headers.get("cache-control"), "private, no-store, no-transform");
    assert.equal(response.headers.get("set-cookie"), "ce_session=rotated; HttpOnly");
    assert.equal(response.headers.get("x-request-id"), "request-safe");
    assert.equal(response.headers.has("x-private-trace"), false);
  });

  it("propagates browser abort to the upstream fetch", async () => {
    const controller = new AbortController();
    const request = new Request("https://context.example.test/api/v1/conversations", { signal: controller.signal });
    let upstreamSignal;
    const pending = proxyContextEngineRequest(request, ["conversations"], config, async (_url, init) => {
      upstreamSignal = init.signal;
      return await new Promise((_resolve, reject) => {
        init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    });
    controller.abort();
    await assert.rejects(pending, (error) => error?.name === "AbortError");
    assert.equal(upstreamSignal.aborted, true);
  });
});
