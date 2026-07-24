# Known Residuals — P1-05 review

Source: post-implementation review of `3ff6f16` / `7de9a4a` (2026-07-24)

Verdict: approve-with-nits. Applied: testing-bypass unit proof and enforced-ingress session rotation proof.

## Accepted residuals

1. CSRF signing-key previous-key compatibility window is documented but not implemented; operators cannot rotate `CE_CSRF_SIGNING_KEY` without invalidating outstanding tokens until a later contract-backed change.
2. Internal `Host` parsing splits on the first `:`, which is incorrect for bracketed IPv6 literals; current deployments use hostnames.
3. OpenAPI success-only auth operations omit typed `401`/`403`/`429` (+ `Retry-After`) response components; runtime and tests already assert the envelopes.
4. Compose/host-native defaults keep `CONTEXT_ENGINE_TESTING=true` with ingress unset so CSRF/origin/peer checks are bypassed until P9-05/P10 supply BFF headers and production settings.
5. Deployed direct-public API denial, BFF header stripping, and browser CSRF E2E remain with P9-05/P10.
