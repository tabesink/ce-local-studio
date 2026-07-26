# Known Residuals - feat/p6-scoped-retrieval-provenance

Source review: structured LFG review of P6-01/P6-02 through `7009cd4`.
Validated adapter, contract, path-normalization, admission, and terminal
reauthorization corrections were applied in `f3ae7ec` and `7009cd4`.

## Applied from review

1. Retrieval admission and the single deadline cover domain resolution,
   eligibility work, provider retrieval, provenance mapping, and terminal
   reauthorization.
2. Terminal reauthorization reloads only the frozen source identities instead
   of materializing the complete eligible domain corpus a second time.
3. Native LightRAG treats only its explicit `no_results` failure reason as an
   empty result; dependency failures and malformed responses fail closed.
4. The stateless Evidence operation publishes canonical `404`, `409`, `422`,
   and `503` error-envelope schemas in OpenAPI and generated TypeScript.
5. The phase-scope checker requests `/` separators from ripgrep without
   rewriting literal backslashes in POSIX filenames.

## Testing gaps (accepted)

1. The POSIX literal-backslash filename fixture is skipped on Windows because
   Windows cannot create that filename; Linux CI owns that platform-specific
   assertion.
2. The exhaustive phase-scope mutation suite did not complete within a
   15-minute Git Bash wrapper budget on Windows. The canonical 65-file gate
   passed locally; the unchanged full fixture matrix remains a CI gate.

## Residual risks (deferred owners)

1. Initial eligibility freezing still renders every eligible source's complete
   block set to verify its immutable index identity. Persisted/index-time
   identity proof or an equivalent bounded strategy remains with P7/P10/P12
   capacity work.
2. Terminal reauthorization cannot eliminate the final read-to-response
   lifecycle window without a broader transaction/locking design. P7 durable
   Evidence redaction and P10/P12 deployed concurrency evidence own closure.
3. Admission is intentionally process-local. Deployment-wide capacity and
   overload behavior remain P10/P12 concerns.
