# P12-07 U4 @release Evidence Checklist

Date: 2026-07-29  
Owner: P12-07 U4 → consumed by U5  
Gate: `CE_P12_07_RELEASE=1` (never default `scripts/verify.sh` / PR Playwright)

## Topology (record exact revision)

- [ ] Compose matrix: `compose.stack.yml` + `compose.stack.minio.yml` + `compose.stack.live.yml` (and TLS only if claiming ingress)
- [ ] `CE_STACK_PUBLIC_ORIGIN=http://127.0.0.1:<port>` (or HTTPS TLS lane)
- [ ] `CE_GRAPH_REF_KEY` present (≥32 bytes); value never pasted into evidence
- [ ] Git commit / image digests under test: `<fill>`
- [ ] Operator digests for production-supported Reducto/embedding labels: `<fill or NO-GO residual>`

## Budget freeze (AE5)

Run and attach stdout:

```bash
CE_P12_07_RELEASE=1 python app/scripts/p12_07_release_capacity_probe.py check
CE_P12_07_RELEASE=1 python app/scripts/p12_07_release_capacity_probe.py unit
```

Record:

| Budget | Value |
| --- | --- |
| graph global / per-domain / per-principal | from check JSON |
| graph wait queue depth | must be `0` |
| retrieval / synthesis / turn lease | from check JSON |
| L / L+1 shed codes | unit: `503 capacity_unavailable` before 2nd runtime call; shed &lt;1s |
| post-shed recovery | unit recovery `ok` |

## Browser @release

```bash
CE_P12_07_RELEASE=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm --prefix app/client run test:e2e:release
```

- [ ] E2E-C01 Mina/Noah concurrent isolation
- [ ] Dual graph workbench without private bags
- [ ] Graph → grounded figure question with `[1]` + pump/relief fact family (AE8/AE10)
- [ ] Documents library privacy (R9 surface)

## Live pipeline (optional; credential-gated)

Only when operator credentials + digests exist:

```bash
CE_P5_04_LIVE=1 …          # LightRAG live isolation credit
CE_PROVIDER_STAGING_SMOKE=1 CE_PROVIDER_STAGING_PROFILE=reducto \
  python app/scripts/provider_staging_smoke.py live
CE_P12_07_RELEASE=1 CE_P12_07_RELEASE_LIVE=1 \
  python app/scripts/p12_07_release_capacity_probe.py live --domain-id <opaque>
```

- [ ] Reducto prepare → extract/index → non-empty Pump→Relief valve graph
- [ ] Same domain answers figure question with mapped Evidence + PDF region
- [ ] Or honest **NO-GO**: missing digests/credentials — do not claim AE9 live

## Failure / privacy scan

- [ ] Runtime/provider failure UI shows request ID only (no paths/URLs/prompts)
- [ ] Failure artifacts under `app/client/test-results/` scanned — no secrets/raw hits
- [ ] Source delete removes graph contribution / redacts open surfaces (AE12) or residual named

## Explicit non-claims

- PR `verify-playwright-pr-fast` green does **not** prove this checklist
- Unit capacity probe does **not** prove live Reducto/provider prose
- Phase 2 observability / metric product APIs
