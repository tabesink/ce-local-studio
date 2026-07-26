#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
checker="$repo_root/scripts/check-doc-phase-scope.sh"
fixture_root=''
baseline_root=''

cleanup_fixture() {
  [[ -z "$fixture_root" ]] || rm -rf -- "$fixture_root"
  fixture_root=''
}

cleanup() {
  cleanup_fixture
  [[ -z "$baseline_root" ]] || rm -rf -- "$baseline_root"
}
trap cleanup EXIT

new_fixture() {
  cleanup_fixture
  if [[ -z "$baseline_root" ]]; then
    baseline_root="$(mktemp -d)"
    cp -a "$repo_root/docs" "$baseline_root/docs"
    cp "$repo_root/AGENTS.md" "$repo_root/DESIGN.md" "$repo_root/STRATEGY.md" "$baseline_root/"
  fi
  fixture_root="$(mktemp -d)"
  cp -a --reflink=auto "$baseline_root/docs" "$fixture_root/docs" 2>/dev/null || cp -a "$baseline_root/docs" "$fixture_root/docs"
  cp -a --reflink=auto "$baseline_root/AGENTS.md" "$baseline_root/DESIGN.md" "$baseline_root/STRATEGY.md" "$fixture_root/" 2>/dev/null || \
    cp "$baseline_root/AGENTS.md" "$baseline_root/DESIGN.md" "$baseline_root/STRATEGY.md" "$fixture_root/"
}

fixture_passes() {
  local label="$1" output
  if ! output="$(CE_PHASE_SCOPE_ROOT="$fixture_root" bash "$checker" 2>&1)"; then
    printf 'fixture unexpectedly failed: %s\n%s\n' "$label" "$output" >&2
    exit 1
  fi
}

fixture_fails() {
  local label="$1" expected="${2:-}" output
  if output="$(CE_PHASE_SCOPE_ROOT="$fixture_root" bash "$checker" 2>&1)"; then
    printf 'fixture unexpectedly passed: %s\n' "$label" >&2
    exit 1
  fi
  if [[ -n "$expected" && "$output" != *"$expected"* ]]; then
    printf 'fixture failed without expected diagnostic: %s\nexpected: %s\nactual: %s\n' \
      "$label" "$expected" "$output" >&2
    exit 1
  fi
}

bash -n "$checker"
bash "$checker" >/dev/null

mapfile -t printed_inputs < <(bash "$checker" --print-inputs)
[[ "${#printed_inputs[@]}" -gt 2 ]]
[[ "${printed_inputs[0]}" == AGENTS.md ]]
[[ " ${printed_inputs[*]} " == *" docs/phase-scope-manifest.md "* ]]
[[ " ${printed_inputs[*]} " == *" scripts/check-doc-phase-scope.sh "* ]]
[[ " ${printed_inputs[*]} " == *" scripts/tests/check-doc-phase-scope.sh "* ]]
[[ " ${printed_inputs[*]} " != *" docs/_scratch/docs-phase-alignment-evidence.md "* ]]
diff -u <(printf '%s\n' "${printed_inputs[@]}") <(printf '%s\n' "${printed_inputs[@]}" | LC_ALL=C sort -u)
diff -u <(bash "$checker" --print-inputs) <(bash "$checker" --print-inputs)

declare -a forbidden_literals=(
  '/api/v1/admin/audit-events'
  '/api/v1/admin/diagnostics'
  'route: /logs'
  'route: /server'
  'route: /usage'
  '### M-12'
  'WikiPageDto'
  '/api/v1/wiki'
  "ref_kind = 'wiki'"
  'route: /wiki'
  'CREATE TABLE wiki_pages'
)

new_fixture
printf '%s\n' "${forbidden_literals[@]}" >> "$fixture_root/docs/future/wiki-layer.md"
fixture_passes future-lexemes

new_fixture
printf '\nroute: /wiki\n' >> "$fixture_root/docs/_scratch/code-docs-drift-review.md"
fixture_passes historical-lexeme

for literal in "${forbidden_literals[@]}"; do
  new_fixture
  printf '\n%s\n' "$literal" >> "$fixture_root/docs/prd.md"
  fixture_fails "active-prohibited-$literal" "docs/prd.md contains prohibited"
done

new_fixture
printf '\nWikiPageDto powers the selected-turn inspector.\n' >> "$fixture_root/docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md"
fixture_fails former-wiki-inspector

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=valid-wiki-route lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_passes valid-mixed-removal-record

new_fixture
printf '\n<!--  phase-scope:removal-evidence id=bad-spacing lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails malformed-marker-spacing removal-evidence

new_fixture
printf '\nprefix <!-- phase-scope:removal-evidence id=nested-marker lexeme=wiki-route disposition=phase-3 --> suffix\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails nested-marker removal-evidence

new_fixture
printf '\n`<!-- phase-scope:removal-evidence id=inline-marker lexeme=wiki-route disposition=phase-3 -->`\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails inline-marker removal-evidence

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=literal-record lexeme=wiki-route disposition=phase-3 route: /wiki -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails prohibited-literal-in-marker removal-evidence

new_fixture
printf '\n<!-- phase-scope:removal-evidence\nid=multiline lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails multiline-marker removal-evidence

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=unknown-subject lexeme=unknown disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails unknown-marker-subject unknown

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=duplicate-marker lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
printf '\n<!-- phase-scope:removal-evidence id=duplicate-marker lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md"
fixture_fails duplicate-marker duplicate

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=extra lexeme=wiki-route disposition=phase-3 extra=yes -->\n' \
  >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails extra-marker-content removal-evidence

new_fixture
printf '\n<!-- phase-scope:removal-evidence id=active-marker lexeme=wiki-route disposition=phase-3 -->\n' \
  >> "$fixture_root/docs/prd.md"
fixture_fails marker-in-active-file removal-evidence

new_fixture
printf '\nroute: /wiki\n' >> "$fixture_root/docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md"
fixture_fails mixed-surrounding-literal

new_fixture
sed -i '/^| active-route | \/chat |/s/ |$//' "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails manifest-missing-trailing-pipe 'manifest row must end with a pipe'

new_fixture
sed -i 's/| recordClass | subject | value | notes |/| record_class | subject | value | notes |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails malformed-header

new_fixture
sed -i 's/| active-route | \/chat | phase-1 | durable grounded chat workbench |/| active-route | \/chat | |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails missing-manifest-cell

new_fixture
printf '| active-route | /z | phase-1 | extra | cell |\n' >> "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails extra-manifest-cell

new_fixture
printf '| active-route | /z | phase-1 | escaped \\| pipe |\n' >> "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails escaped-manifest-pipe escaped

new_fixture
printf '| active-route | /z | phase-1 | <em>html</em> |\n' >> "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails manifest-html HTML

new_fixture
printf 'continued table cell\n' >> "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails manifest-continuation continuation

new_fixture
sed -i '/^| active-route | \/chat |/p' "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails duplicate-manifest-key duplicate

new_fixture
sed -i \
  -e 's#| active-route | /chat |#| active-route | /temporary |#' \
  -e 's#| active-route | /database-visualize |#| active-route | /chat |#' \
  -e 's#| active-route | /temporary |#| active-route | /database-visualize |#' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails unsorted-manifest-keys sorted

new_fixture
sed -i 's/| active-route |/| active_route |/' "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails unknown-record-class unknown

new_fixture
sed -i 's/| scan-file | docs\/README.md | active |/| scan-file | docs\/README.md | enabled |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails unknown-enum unknown

new_fixture
sed -i 's/| prohibited-lexeme | wiki-route |/| prohibited-lexeme | Wiki_Route |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails malformed-stable-slug slug

new_fixture
sed -i 's#| scan-file | AGENTS.md | active |#| scan-file | docs/../AGENTS.md | active |#' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails traversal-path invalid

new_fixture
sed -i 's#| scan-file | AGENTS.md | active |#| scan-file | docs\\\\AGENTS.md | active |#' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails backslash-path invalid

new_fixture
sed -i 's#| scan-file | docs/README.md | active |#| scan-file | docs/readme.md | active |#' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails case-alias-path

for ref_kind in source evidence template; do
  new_fixture
  sed -i "/^| governed-ref-kind | $ref_kind |/d" "$fixture_root/docs/phase-scope-manifest.md"
  fixture_fails "missing-governed-ref-$ref_kind"
done

new_fixture
sed -i 's/| scan-file | docs\/phase-scope-manifest.md | manifest |/| scan-file | docs\/phase-scope-manifest.md | active |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails missing-manifest-classification

new_fixture
sed -i 's/| scan-file | docs\/_scratch\/docs-phase-alignment-evidence.md | evidence-output |/| scan-file | docs\/_scratch\/docs-phase-alignment-evidence.md | manifest |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails duplicate-manifest-classification

new_fixture
sed -i 's/| scan-file | docs\/README.md | active |/| scan-file | docs\/README.md | review-required |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails review-required-at-freeze review-required

new_fixture
sed -i 's/| scan-file | docs\/prd.md | active |/| scan-file | docs\/prd.md | future |/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails active-file-reclassified-future future

new_fixture
fixture_passes manifest-lexemes-do-not-self-trigger

for plan_name in '.hidden-plan' 'unclassified-plan.json' 'unclassified-plan.yaml' 'ignored-plan.md' 'extensionless'; do
  new_fixture
  printf 'phase_compatibility: future\n' > "$fixture_root/docs/plans/$plan_name"
  if [[ "$plan_name" == ignored-plan.md ]]; then
    printf 'docs/plans/ignored-plan.md\n' > "$fixture_root/.gitignore"
  fi
  fixture_fails "unclassified-$plan_name" classification
done

new_fixture
printf '# unclassified\n' > "$fixture_root/docs/architecture/unclassified.md"
fixture_fails unclassified-governed-doc classification

case "$OSTYPE" in
  msys*|cygwin*) ;;
  *)
    new_fixture
    printf '# literal backslash path\n' > "$fixture_root/docs/architecture/literal\\name.md"
    fixture_fails literal-backslash-governed-doc classification
    ;;
esac

new_fixture
sed -i 's/phase-1>phase-2-observability>phase-3-wiki/phase-1>phase-3-wiki>phase-2-observability/' \
  "$fixture_root/docs/phase-scope-manifest.md"
fixture_fails reversed-phase-order

new_fixture
sed -i '/#### Closed Phase 1 chat capability manifest/d' "$fixture_root/docs/prd.md"
fixture_fails missing-prd-capability-anchor

new_fixture
printf '\n#### Closed Phase 1 chat capability manifest\n' >> "$fixture_root/AGENTS.md"
fixture_fails competing-capability-owner 'competing capability manifest'

safety_terms=(
  'transactional audit writes'
  'allowlisted logs'
  'correlation'
  'health/readiness'
  'bounded metrics'
  'privacy checks'
  'runbooks'
)
for term in "${safety_terms[@]}"; do
  new_fixture
  sed -i "/B0 — brownfield repository boundary:/s|$term|$term-removed|" \
    "$fixture_root/docs/master-build-plan.md"
  fixture_fails "missing-safety-$term" 'positive-test gate is missing'
done

for claim in \
  'authorizes-new-public-contract: true' \
  'authorizes-new-http: true' \
  'authorizes-new-dto: true' \
  'authorizes-new-sse: true' \
  'authorizes-new-ref-kind: true' \
  'authorizes-new-persistence: true' \
  'authorizes-phase-boundary-override: true'; do
  new_fixture
  printf '\n%s\n' "$claim" >> "$fixture_root/docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md"
  fixture_fails "plan-002-$claim" 'plan 002 asserts prohibited authority'
done

for claim in \
  'authorizes-new-route: true' \
  'live-stub-product-state: true' \
  'authorizes-uncontracted-shared-primitive: true' \
  'd0-application-complete: true'; do
  new_fixture
  printf '\n%s\n' "$claim" >> "$fixture_root/docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md"
  fixture_fails "plan-003-$claim" 'plan 003 asserts prohibited authority'
done

new_fixture
sed -i '/phase_compatibility: phase-1-child/d' \
  "$fixture_root/docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md"
fixture_fails missing-child-compatibility

new_fixture
sed -i 's#future/wiki-layer.md#future/missing-layer.md#' "$fixture_root/docs/README.md"
fixture_fails broken-required-relative-link 'required link is missing'

new_fixture
rm -f "$fixture_root/docs/future/observability-layer.md"
fixture_fails missing-future-brief 'classified file does not exist'

new_fixture
sed -i 's/1. repository `AGENTS.md` and governance constitution;/1. implementation observations;/' \
  "$fixture_root/docs/README.md"
printf '\n1. repository `AGENTS.md` and governance constitution;\n' >> "$fixture_root/docs/README.md"
fixture_fails governance-precedence 'authority precedence is missing or out of order'

new_fixture
sed -i 's#Read `docs/README.md` first, then the smallest authoritative set for the task. At minimum:#Consult the implementation before the documentation package.#' \
  "$fixture_root/AGENTS.md"
sed -i '/^| Work | Required documents |/i Read `docs/README.md` first, then the smallest authoritative set for the task. At minimum:\n' \
  "$fixture_root/AGENTS.md"
fixture_fails governance-read-order 'coding-agent read order is missing'

new_fixture
sed -i 's/A \*\*Knowledge Domain\*\* is the isolated retrieval boundary/A **Knowledge Domain** is an optional retrieval grouping/' \
  "$fixture_root/AGENTS.md"
sed -i '/^## Non-Negotiable Product Invariants/i - A **Knowledge Domain** is the isolated retrieval boundary. It owns one private LightRAG runtime, one immutable embedding profile, its corpus, lifecycle, and query eligibility.\n' \
  "$fixture_root/AGENTS.md"
fixture_fails governance-vocabulary 'canonical product vocabulary'

new_fixture
sed -i 's/Do not add a Workspace entity/Do not add an Account entity/' "$fixture_root/AGENTS.md"
sed -i '/^The closed Phase 1 chat-capability manifest/a Do not add a Workspace entity or use “domain” to mean a tenant, deployment, or runtime environment. Administrators gain operational capabilities; they do not automatically gain access to members’ private conversations or Evidence.\n' \
  "$fixture_root/AGENTS.md"
fixture_fails governance-workspace-prohibition 'Workspace prohibition is missing'

new_fixture
sed -i '/Stop and obtain an explicit decision when:/d' "$fixture_root/AGENTS.md"
sed -i '/^## Definition of Done/i Stop and obtain an explicit decision when:\n' "$fixture_root/AGENTS.md"
fixture_fails governance-stop-heading 'explicit decision stop conditions are missing'

new_fixture
sed -i 's/Production needs a queue, object-store technology, orchestrator, tenancy model, or topology outside the approved architecture/Production may choose any convenient queue or topology/' \
  "$fixture_root/AGENTS.md"
sed -i '/^## Definition of Done/i 4. Production needs a queue, object-store technology, orchestrator, tenancy model, or topology outside the approved architecture.\n' \
  "$fixture_root/AGENTS.md"
fixture_fails governance-stop-condition 'explicit decision stop conditions are missing or out of order'

new_fixture
sed -i 's/stop and identify the missing authority/continue with the nearest implementation pattern/' \
  "$fixture_root/AGENTS.md"
sed -i '/^| Work | Required documents |/i Do not invent a transition, public field, endpoint, event, error code, or browser capability that is absent from the approved contracts. If a requirement has no approved contract, stop and identify the missing authority.\n' \
  "$fixture_root/AGENTS.md"
fixture_fails governance-missing-authority-stop 'missing-contract stop rule is missing'


new_fixture
sed -i 's/administrator role grants no implicit read access/administrator role grants operational read access/' \
  "$fixture_root/docs/architecture/data-and-lifecycle.md"
fixture_fails p0-04-ownership 'conversation ownership boundary is missing'

new_fixture
sed -i 's/| `content_sensitive` |/| `content` |/' \
  "$fixture_root/docs/architecture/data-and-lifecycle.md"
fixture_fails p0-04-privacy 'privacy class is missing or duplicated'

new_fixture
sed -i 's/Adapters implement ports and never authorize/Adapters may authorize when convenient/' \
  "$fixture_root/docs/architecture/data-and-lifecycle.md"
fixture_fails p0-04-port-boundary 'adapter/external-call boundary is missing'

new_fixture
sed -i 's/An uncertain remote outcome is non-terminal until reconciliation/An uncertain remote outcome may be retried as failed/' \
  "$fixture_root/docs/architecture/data-and-lifecycle.md"
fixture_fails p0-04-state-machine 'state-machine conventions are missing or out of order'

printf 'phase-scope fixtures: PASS\n'
