#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${CE_PHASE_SCOPE_ROOT:-$(cd "$script_dir/.." && pwd)}"
manifest="$repo_root/docs/phase-scope-manifest.md"

fail() {
  printf 'phase-scope: %s\n' "$*" >&2
  exit 1
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

[[ -f "$manifest" ]] || fail "missing docs/phase-scope-manifest.md"

declare -a record_classes=() subjects=() values=()
declare -A seen_keys=() scan_classes=() lexemes=()
header_count=0
separator_count=0
previous_key=''
table_state='before'

while IFS= read -r raw || [[ -n "$raw" ]]; do
  raw="${raw%$'\r'}"
  if [[ "$raw" == '| recordClass | subject | value | notes |' ]]; then
    [[ "$table_state" == before ]] || fail "canonical manifest header is misplaced or duplicated"
    ((header_count += 1))
    table_state='header'
    continue
  fi
  if [[ "$raw" == '| --- | --- | --- | --- |' ]]; then
    [[ "$table_state" == header ]] || fail "canonical manifest separator must immediately follow the header"
    ((separator_count += 1))
    table_state='data'
    continue
  fi
  if [[ "$raw" != \|* ]]; then
    if [[ "$table_state" != before && -n "$(trim "$raw")" ]]; then
      fail "manifest continuation or trailing prose is forbidden: $raw"
    fi
    continue
  fi
  [[ "$table_state" == data ]] || fail "manifest data row appears before the canonical header and separator"
  [[ "$raw" == *'|' ]] || fail "manifest row must end with a pipe: $raw"
  [[ "$raw" != *'\|'* ]] || fail "escaped pipe is forbidden in manifest row: $raw"

  body="${raw#|}"
  body="${body%|}"
  IFS='|' read -r raw_class raw_subject raw_value raw_notes extra <<< "$body"
  [[ -z "${extra:-}" ]] || fail "manifest row must contain exactly four cells: $raw"
  record_class="$(trim "$raw_class")"
  subject="$(trim "$raw_subject")"
  value="$(trim "$raw_value")"
  notes="$(trim "$raw_notes")"
  [[ -n "$record_class" && -n "$subject" && -n "$value" ]] || fail "manifest row has an empty required cell: $raw"
  for cell in "$record_class" "$subject" "$value" "$notes"; do
    [[ "$cell" != *'<'* ]] || fail "HTML is forbidden in manifest cells: $raw"
  done

  case "$record_class" in
    active-route|case-tombstone|child-ceiling|governed-ref-kind|phase-order|prohibited-lexeme|removed-public-surface|retained-safety-capability|scan-file) ;;
    *) fail "unknown record class: $record_class" ;;
  esac

  case "$record_class" in
    governed-ref-kind|prohibited-lexeme|removed-public-surface|retained-safety-capability)
      [[ "$subject" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail "manifest subject must be a lowercase kebab-case slug: $record_class/$subject"
      ;;
  esac

  case "$record_class" in
    active-route)
      [[ "$subject" == /* && "$subject" != *'?'* && "$subject" != *'#'* && "$value" == phase-1 ]] || fail "invalid active-route row: $subject=$value"
      ;;
    case-tombstone)
      [[ "$subject" =~ ^[MAC]-[0-9][0-9]$ && "$value" =~ ^(phase-2|phase-3|removed)$ ]] || fail "invalid case-tombstone row: $subject=$value"
      ;;
    child-ceiling)
      [[ "$subject" == docs/plans/*'#'* && "$value" == prohibited ]] || fail "invalid child-ceiling row: $subject=$value"
      ;;
    governed-ref-kind)
      [[ "$value" == phase-1 ]] || fail "invalid governed-ref-kind value: $subject=$value"
      ;;
    removed-public-surface)
      [[ "$value" =~ ^(route|http|dto|ref|table|case-family)$ ]] || fail "invalid removed-public-surface value: $subject=$value"
      ;;
    retained-safety-capability)
      [[ "$value" == phase-1-private ]] || fail "invalid retained-safety-capability value: $subject=$value"
      ;;
    scan-file)
      [[ "$subject" != /* && "$subject" != *$'\\'* && "$subject" != *'//'* && "$subject" != '.' && "$subject" != '..' && "$subject" != ./* && "$subject" != ../* && "$subject" != *'/./'* && "$subject" != *'/../'* && "$subject" != */ ]] || fail "invalid scan-file path: $subject"
      ;;
  esac

  key="$record_class"$'\t'"$subject"
  [[ -z "${seen_keys[$key]:-}" ]] || fail "duplicate manifest key: $record_class/$subject"
  seen_keys[$key]=1
  if [[ -n "$previous_key" && ! "$previous_key" < "$key" ]]; then
    fail "manifest rows are not bytewise sorted at: $record_class/$subject"
  fi
  previous_key="$key"
  record_classes+=("$record_class")
  subjects+=("$subject")
  values+=("$value")
  if [[ "$record_class" == scan-file ]]; then
    scan_classes[$subject]="$value"
  elif [[ "$record_class" == prohibited-lexeme ]]; then
    [[ "$value" != *$'\n'* && "$value" != *'|'* ]] || fail "invalid prohibited lexeme: $subject"
    lexemes[$subject]="$value"
  fi
done < "$manifest"

[[ "$header_count" -eq 1 ]] || fail "manifest must contain exactly one canonical header"
[[ "$separator_count" -eq 1 ]] || fail "manifest must contain exactly one canonical separator row"

class_set() {
  local wanted="$1" index
  for index in "${!record_classes[@]}"; do
    if [[ "${record_classes[$index]}" == "$wanted" ]]; then
      printf '%s=%s\n' "${subjects[$index]}" "${values[$index]}"
    fi
  done | sort
}

assert_set() {
  local class="$1" expected="$2" actual
  actual="$(class_set "$class")"
  [[ "$actual" == "$expected" ]] || fail "$class exact set mismatch"
}

assert_set active-route $'/chat=phase-1\n/database-visualize=phase-1\n/documents=phase-1\n/login=phase-1\n/settings=phase-1'
assert_set governed-ref-kind $'evidence=phase-1\nsource=phase-1\ntemplate=phase-1'
assert_set phase-order 'release-order=phase-1>phase-2-observability>phase-3-wiki'
assert_set retained-safety-capability $'allowlisted-logs=phase-1-private\nbounded-metrics=phase-1-private\ncorrelation=phase-1-private\nhealth-readiness=phase-1-private\nprivacy-checks=phase-1-private\nrunbooks=phase-1-private\ntransactional-audit=phase-1-private'
assert_set case-tombstone $'A-11=phase-2\nA-12=phase-2\nM-12=phase-3\nM-13=phase-3'
assert_set child-ceiling $'docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md#phase-boundary-override=prohibited\ndocs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md#public-http-dto-sse-ref-persistence-authority=prohibited\ndocs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#d0-application-completion=prohibited\ndocs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#live-stub-product-state=prohibited\ndocs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#new-route-authority=prohibited\ndocs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md#uncontracted-shared-primitive=prohibited'

removed_subject_set="$(class_set removed-public-surface | cut -d= -f1)"
lexeme_subject_set="$(class_set prohibited-lexeme | cut -d= -f1)"
[[ "$removed_subject_set" == "$lexeme_subject_set" ]] || fail "removed surfaces and prohibited lexeme subjects must match exactly"

for subject in "${!scan_classes[@]}"; do
  classification="${scan_classes[$subject]}"
  case "$classification" in
    active|mixed-removal|future|historical|manifest|evidence-output) ;;
    review-required) fail "review-required classification remains: $subject" ;;
    *) fail "unknown scan-file classification for $subject" ;;
  esac
  if [[ "$classification" != evidence-output ]]; then
    [[ -f "$repo_root/$subject" ]] || fail "classified file does not exist: $subject"
  fi
  case "$classification" in
    future)
      if [[ "$subject" == docs/plans/* ]]; then
        grep -Fq 'phase_compatibility: future' "$repo_root/$subject" || fail "future plan lacks compatible phase_compatibility: $subject"
      else
        [[ "$subject" == docs/future/* ]] || fail "future classification is limited to future briefs or explicitly compatible plans: $subject"
      fi
      ;;
    historical)
      if [[ "$subject" == docs/plans/* ]]; then
        grep -Fq 'phase_compatibility: historical' "$repo_root/$subject" || fail "historical plan lacks compatible phase_compatibility: $subject"
      else
        [[ "$subject" == docs/_scratch/code-docs-drift-review.md || "$subject" == docs/ideation/2026-07-22-lean-agent-shell-ideation.html ]] || fail "historical classification is limited to named evidence or explicitly compatible plans: $subject"
      fi
      ;;
    manifest)
      [[ "$subject" == docs/phase-scope-manifest.md ]] || fail "manifest classification must name docs/phase-scope-manifest.md"
      ;;
    evidence-output)
      [[ "$subject" == docs/_scratch/docs-phase-alignment-evidence.md ]] || fail "unexpected evidence-output path: $subject"
      ;;
    mixed-removal)
      [[ "$subject" == docs/plans/2026-07-22-001-docs-brownfield-phase-contract-alignment-plan.md || "$subject" == docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md ]] || fail "unexpected mixed-removal path: $subject"
      grep -Eq '^phase_compatibility: phase-1-' "$repo_root/$subject" || fail "active plan lacks compatible phase_compatibility: $subject"
      ;;
    active)
      if [[ "$subject" == docs/plans/* ]]; then
        grep -Eq '^phase_compatibility: phase-1-' "$repo_root/$subject" || fail "active plan lacks compatible phase_compatibility: $subject"
      fi
      ;;
  esac
done
manifest_class_count="$(class_set scan-file | grep -c '=manifest$' || true)"
evidence_class_count="$(class_set scan-file | grep -c '=evidence-output$' || true)"
[[ "$manifest_class_count" -eq 1 ]] || fail "exactly one manifest classification is required"
[[ "$evidence_class_count" -eq 1 ]] || fail "exactly one evidence-output classification is required"

cd "$repo_root"
declare -a candidates=()
for root_file in AGENTS.md DESIGN.md STRATEGY.md; do
  [[ -f "$root_file" ]] && candidates+=("$root_file")
done
while IFS= read -r -d '' path; do
  case "$path" in
    docs/plans/*) candidates+=("$path") ;;
    docs/_scratch/code-docs-drift-review.md) candidates+=("$path") ;;
    docs/_scratch/*) ;;
    docs/ideation/2026-07-22-lean-agent-shell-ideation.html) candidates+=("$path") ;;
    docs/ideation/*) ;;
    *.md|*.txt|*.html) candidates+=("$path") ;;
  esac
done < <(find docs -type f -print0)

mapfile -t discovered < <(printf '%s\n' "${candidates[@]}" | sort -u)
mapfile -t classified < <(
  for path in "${!scan_classes[@]}"; do
    if [[ "${scan_classes[$path]}" != evidence-output ]]; then
      printf '%s\n' "$path"
    fi
  done | sort -u
)
[[ "$(printf '%s\n' "${discovered[@]}")" == "$(printf '%s\n' "${classified[@]}")" ]] || {
  printf '%s\n' 'phase-scope: governed-file classification mismatch' >&2
  diff -u <(printf '%s\n' "${classified[@]}") <(printf '%s\n' "${discovered[@]}") >&2 || true
  exit 1
}

declare -A removal_ids=()
removal_pattern='^<!--[ ]phase-scope:removal-evidence[ ]id=([a-z0-9-]+)[ ]lexeme=([a-z0-9-]+)[ ]disposition=(removed|phase-2|phase-3)[ ]-->$'
marker_like_pattern='<!--[[:space:]]*phase-scope:removal-evidence'
for path in "${classified[@]}"; do
  classification="${scan_classes[$path]}"
  case "$classification" in
    future|historical|manifest) continue ;;
  esac
  if [[ "$classification" == mixed-removal ]]; then
    while IFS= read -r record; do
      [[ "$record" == *'<stable-id>'* && "$record" == *'<prohibited-lexeme-subject>'* ]] && continue
      [[ "$record" =~ $removal_pattern ]] || fail "malformed removal-evidence record in $path"
      removal_id="${BASH_REMATCH[1]}"
      lexeme_subject="${BASH_REMATCH[2]}"
      [[ -n "${lexemes[$lexeme_subject]:-}" ]] || fail "unknown removal-evidence lexeme in $path: $lexeme_subject"
      [[ -z "${removal_ids[$removal_id]:-}" ]] || fail "duplicate removal-evidence id: $removal_id"
      removal_ids[$removal_id]=1
    done < <(grep -E "$marker_like_pattern" "$path" || true)
  elif grep -Eq "$marker_like_pattern" "$path"; then
    fail "removal-evidence records are allowed only in mixed-removal files: $path"
  fi
  for lexeme_subject in "${!lexemes[@]}"; do
    if match="$(grep -F -n -m1 -- "${lexemes[$lexeme_subject]}" "$path" || true)" && [[ -n "$match" ]]; then
      fail "$path contains prohibited $lexeme_subject declaration at ${match%%:*}"
    fi
  done
done
for required in \
  docs/future/README.md \
  docs/future/observability-layer.md \
  docs/future/wiki-layer.md \
  docs/architecture/legacy-persistence-retirement.md \
  docs/brownfield-refactor-register.md \
  docs/frontend/AGENTS.md \
  DESIGN.md; do
  [[ -f "$required" ]] || fail "missing required file: $required"
done

declare -a required_links=(
  'docs/README.md|future/README.md'
  'docs/README.md|future/observability-layer.md'
  'docs/README.md|future/wiki-layer.md'
  'docs/master-build-plan.md|future/README.md'
  'docs/master-build-plan.md|future/observability-layer.md'
  'docs/master-build-plan.md|future/wiki-layer.md'
  'docs/architecture/as-built-gaps-and-decisions.md|../future/observability-layer.md'
  'docs/architecture/as-built-gaps-and-decisions.md|../future/wiki-layer.md'
  'docs/architecture/as-built-gaps-and-decisions.md|legacy-persistence-retirement.md'
)
for required_link in "${required_links[@]}"; do
  link_owner="${required_link%%|*}"
  link_target="${required_link#*|}"
  grep -Fq "$link_target" "$link_owner" || fail "required link is missing from $link_owner: $link_target"
done

markdown_section() {
  local path="$1" heading="$2" heading_count
  heading_count="$(grep -Fxc -- "$heading" "$path" || true)"
  [[ "$heading_count" -eq 1 ]] || fail "required Markdown section must occur exactly once: $path: $heading"
  awk -v heading="$heading" '
    $0 == heading { inside = 1; next }
    inside && /^## / { exit }
    inside { print }
  ' "$path"
}

assert_line_once() {
  local content="$1" expected="$2" diagnostic="$3" count
  count="$(grep -Fxc -- "$expected" <<< "$content" || true)"
  [[ "$count" -eq 1 ]] || fail "$diagnostic"
}

line_number_once() {
  local content="$1" expected="$2" diagnostic="$3"
  assert_line_once "$content" "$expected" "$diagnostic"
  grep -nF -x -m1 -- "$expected" <<< "$content" | cut -d: -f1
}

assert_line_after() {
  local content="$1" expected="$2" predecessor="$3" diagnostic="$4" expected_line predecessor_line
  expected_line="$(line_number_once "$content" "$expected" "$diagnostic")"
  predecessor_line="$(line_number_once "$content" "$predecessor" "$diagnostic")"
  [[ "$expected_line" -eq $((predecessor_line + 2)) ]] || fail "$diagnostic"
}

assert_last_nonblank_line() {
  local content="$1" expected="$2" diagnostic="$3" last_nonblank
  assert_line_once "$content" "$expected" "$diagnostic"
  last_nonblank="$(awk 'NF { line = $0 } END { print line }' <<< "$content")"
  [[ "$last_nonblank" == "$expected" ]] || fail "$diagnostic"
}

assert_ordered_numbered_list() {
  local content="$1" diagnostic="$2" expected_count="$3" previous=0 current expected
  shift 3
  [[ "$(grep -Ec '^[0-9]+\. ' <<< "$content" || true)" -eq "$expected_count" ]] || fail "$diagnostic"
  for expected in "$@"; do
    current="$(grep -nF -x -m1 -- "$expected" <<< "$content" | cut -d: -f1 || true)"
    [[ -n "$current" && "$current" -gt "$previous" ]] || fail "$diagnostic"
    previous="$current"
  done
}

agents_authority="$(markdown_section AGENTS.md '## Authority and Required Reading')"
assert_ordered_numbered_list "$agents_authority" 'authority precedence is missing or out of order' 7 \
  '1. This `AGENTS.md` and repository governance.' \
  '2. Approved product requirements and acceptance criteria: `docs/prd.md` and `docs/interaction-behavior-prd.md`.' \
  '3. Versioned HTTP, DTO, SSE, document/evidence, data, and AI contracts under `docs/contracts/` and `docs/database-schema.txt`.' \
  '4. Architecture, frontend, security, deployment, and quality specifications under `docs/architecture/`, `docs/frontend/`, and `docs/quality/`.' \
  '5. `docs/master-build-plan.md` and approved feature plans or task lists.' \
  '6. Code, migrations, tests, and observed runtime behavior.' \
  '7. Read-only reference implementations.'
assert_line_after "$agents_authority" 'Read `docs/README.md` first, then the smallest authoritative set for the task. At minimum:' '7. Read-only reference implementations.' 'coding-agent read order is missing'
assert_last_nonblank_line "$agents_authority" 'Do not invent a transition, public field, endpoint, event, error code, or browser capability that is absent from the approved contracts. If a requirement has no approved contract, stop and identify the missing authority.' 'missing-contract stop rule is missing'

docs_precedence="$(markdown_section docs/README.md '## Evidence and precedence')"
assert_ordered_numbered_list "$docs_precedence" 'authority precedence is missing or out of order' 7 \
  '1. repository `AGENTS.md` and governance constitution;' \
  '2. approved feature specifications and acceptance criteria;' \
  '3. versioned API, SSE, data, and AI contracts;' \
  '4. architecture and quality specifications;' \
  '5. feature plans and task lists;' \
  '6. code, migrations, tests, and runtime observations;' \
  '7. read-only reference implementations.'

product_scope="$(markdown_section AGENTS.md '## Product Identity and Scope')"
[[ "$(grep -Ec '^- ' <<< "$product_scope" || true)" -eq 5 ]] || fail "canonical product vocabulary list is incomplete or duplicated"
declare -a required_vocabulary=(
  '- A **Knowledge Domain** is the isolated retrieval boundary. It owns one private LightRAG runtime, one immutable embedding profile, its corpus, lifecycle, and query eligibility.'
  '- A **Source Document** belongs to exactly one domain. Canonical Source Blocks are parser-independent, ordered, stable citable units.'
  '- **Evidence** is a safe, authorized projection from private retrieval results to source labels, excerpts, document references, and semantic anchors.'
  '- A **Conversation** belongs to one member. A turn is either `domain_rag` with exactly one domain or `direct_llm` with none.'
  '- **Composer references** are short-lived opaque tokens for approved source, evidence, or template context. Store token hashes, not raw tokens.'
)
for vocabulary_line in "${required_vocabulary[@]}"; do
  assert_line_once "$product_scope" "$vocabulary_line" "canonical product vocabulary is missing: $vocabulary_line"
done
assert_line_after "$product_scope" 'Do not add a Workspace entity or use “domain” to mean a tenant, deployment, or runtime environment. Administrators gain operational capabilities; they do not automatically gain access to members’ private conversations or Evidence.' "${required_vocabulary[4]}" 'Workspace prohibition is missing'

workflow_scope="$(markdown_section AGENTS.md '## Implementation Workflow and Stop Conditions')"
declare -a required_workflow_rules=(
  '- Follow `docs/master-build-plan.md` in dependency order. Each phase is a vertical slice: migrations, contracts, service behavior, tests, acceptance evidence, and operational notes complete together.'
  '- Treat reviewed source as evidence, not proof that a rebuild task is done. Inspect `docs/architecture/as-built-gaps-and-decisions.md` before relying on scaffolded parsers, providers, native LightRAG/runtime control, tracing, PDF preview, graph, or node operations.'
  '- Do not scaffold future controls or fixture-only loaded states. When a contracted capability is unavailable, render the deliberate unavailable state only if the product contract permits it.'
  '- Keep one user intent per implementation slice and produce the evidence record required by `docs/quality/definition-of-done.md`.'
)
[[ "$(grep -Ec '^- ' <<< "$workflow_scope" || true)" -eq "${#required_workflow_rules[@]}" ]] || fail "coding-agent workflow rules are incomplete or duplicated"
for workflow_rule in "${required_workflow_rules[@]}"; do
  assert_line_once "$workflow_scope" "$workflow_rule" "coding-agent workflow rule is missing: $workflow_rule"
done
assert_line_after "$workflow_scope" 'Stop and obtain an explicit decision when:' "${required_workflow_rules[3]}" 'explicit decision stop conditions are missing'
declare -a required_stop_conditions=(
  '1. A browser feature needs a field, event, endpoint, source-content URL, runtime target, or private identifier absent from the approved contracts.'
  '2. Real parser/provider behavior would change canonical blocks, Evidence, streaming, or error semantics.'
  '3. Native LightRAG cannot prove provenance mapping, idempotent submit, readiness, or deletion.'
  '4. Production needs a queue, object-store technology, orchestrator, tenancy model, or topology outside the approved architecture.'
  '5. A destructive migration or delete/redaction flow lacks automated recovery and restore evidence.'
  '6. Visual parity conflicts with security or accessibility and no approved divergence exists.'
)
assert_ordered_numbered_list "$workflow_scope" 'explicit decision stop conditions are missing or out of order' "${#required_stop_conditions[@]}" "${required_stop_conditions[@]}"
assert_line_after "$workflow_scope" "${required_stop_conditions[0]}" 'Stop and obtain an explicit decision when:' 'explicit decision stop conditions are missing'

anchor='docs/prd.md#closed-phase-1-chat-capability-manifest'
grep -Fq '#### Closed Phase 1 chat capability manifest' docs/prd.md || fail "PRD capability manifest anchor is missing"
for consumer in AGENTS.md docs/frontend/content-and-microcopy.md docs/master-build-plan.md docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md; do
  grep -Fq "$anchor" "$consumer" || fail "$consumer does not reference the PRD capability manifest"
done

for consumer in AGENTS.md docs/frontend/content-and-microcopy.md docs/master-build-plan.md docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md; do
  ! grep -Fq '#### Closed Phase 1 chat capability manifest' "$consumer" || fail "$consumer contains a competing capability manifest definition"
done

plan2='docs/plans/2026-07-22-002-feat-lean-agent-shell-umbrella-plan.md'
plan3='docs/plans/2026-07-22-003-feat-ce-frontend-factory-plan.md'
grep -Fq 'phase_compatibility: phase-1-child' "$plan2" || fail "plan 002 is not a phase-1 child"
grep -Fq 'cannot independently authorize an endpoint, DTO, event, ref kind, persistence model' "$plan2" || fail "plan 002 public-contract ceiling is missing"
grep -Fq 'phase_compatibility: phase-1-child' "$plan3" || fail "plan 003 is not a phase-1 child"
grep -Fq 'cannot authorize a new route, stubbed product state, shared primitive, or completion credit' "$plan3" || fail "plan 003 authority ceiling is missing"
grep -Fq 'production Next build, same-origin BFF, and FastAPI with server-produced DTOs' "$plan3" || fail "plan 003 real Settings proof is missing"

for forbidden_claim in \
  'authorizes-new-public-contract: true' \
  'authorizes-new-http: true' \
  'authorizes-new-dto: true' \
  'authorizes-new-sse: true' \
  'authorizes-new-ref-kind: true' \
  'authorizes-new-persistence: true' \
  'authorizes-phase-boundary-override: true'; do
  ! grep -Fq "$forbidden_claim" "$plan2" || fail "plan 002 asserts prohibited authority: $forbidden_claim"
done
for forbidden_claim in \
  'authorizes-new-route: true' \
  'live-stub-product-state: true' \
  'authorizes-uncontracted-shared-primitive: true' \
  'd0-application-complete: true'; do
  ! grep -Fq "$forbidden_claim" "$plan3" || fail "plan 003 asserts prohibited authority: $forbidden_claim"
done

grep -Fq 'allowlisted logs, bounded service metrics, health/readiness, and transactional audit writes' docs/architecture/security-operations-and-quality.md || fail "private operational-safety baseline is missing"
grep -Fq 'privacy scans' docs/master-build-plan.md || fail "privacy-check requirement is missing"
grep -Fq 'operator runbook' docs/master-build-plan.md || fail "runbook requirement is missing"
grep -Fq 'transactional audit writes, allowlisted logs, correlation, health/readiness, bounded metrics, privacy checks and runbooks still have positive tests.' docs/master-build-plan.md || fail "operational-safety positive-test gate is missing"


lifecycle_doc='docs/architecture/data-and-lifecycle.md'
ownership_scope="$(markdown_section "$lifecycle_doc" '## Authoritative data ownership')"
assert_line_once "$ownership_scope" '| conversations, turns, Evidence and accepted refs | FastAPI/PostgreSQL; `owner_user_id` through conversation ownership | only the owning member; administrator role grants no implicit read access |' 'conversation ownership boundary is missing'
assert_line_once "$ownership_scope" 'PostgreSQL is authoritative for identity, authorization, lifecycle, operation intent, private linkage and durable product state. Governed object storage owns source bytes and durable derived objects referenced by PostgreSQL metadata. Per-domain runtime directories and LightRAG state are private rebuildable derivatives, never ownership or backup authority. Repositories persist within a service-supplied scope and never decide authorization.' 'authoritative persistence ownership is missing'

privacy_scope="$(markdown_section "$lifecycle_doc" '## Privacy classes and allowed sinks')"
for privacy_class in public_safe private_operational content_sensitive secret; do
  [[ "$(grep -Ec "^\\| \`$privacy_class\` \|" <<< "$privacy_scope" || true)" -eq 1 ]] || fail "privacy class is missing or duplicated: $privacy_class"
done
assert_line_once "$privacy_scope" 'Classification follows the value through copies, failures, fixtures and derived artifacts; renaming a field never downgrades it. Unknown values default to the more restrictive class. A public mapper is an allowlist and may not serialize an ORM model, adapter payload or exception wholesale.' 'privacy propagation/default rule is missing'

port_scope="$(markdown_section "$lifecycle_doc" '## Outbound port catalog')"
for port_name in 'clock and ID providers' 'credential cipher' 'governed object store' 'parser' 'domain runtime controller' 'LightRAG index' 'scoped retrieval' 'synthesis' 'operational telemetry'; do
  [[ "$(grep -Fc "| $port_name |" <<< "$port_scope" || true)" -eq 1 ]] || fail "outbound port is missing or duplicated: $port_name"
done
assert_line_once "$port_scope" 'Adapters implement ports and never authorize, commit product state, choose a domain, or expose provider/runtime payloads. Services freeze inputs and commit operation intent before an external call; the call runs outside the database transaction with bounded timeouts and a stable idempotency key. Timeout or transport loss with an unknown remote outcome enters reconciliation before retry. Selecting a concrete production object store, parser/provider behavior, controller topology or unsupported queue requires the owning architecture decision.' 'adapter/external-call boundary is missing'

state_machine_scope="$(markdown_section "$lifecycle_doc" '## State-machine convention')"
declare -a required_state_machine_rules=(
  '1. Each persisted state/status field has one closed vocabulary and one owning service; routes, repositories, adapters and browser code do not assign transitions.'
  '2. The service reauthorizes and locks current state in the committing transaction, validates the transition, advances the generation/fence, persists operation intent and required audit atomically, then returns an authoritative projection.'
  '3. External work occurs after intent commit. Workers claim with PostgreSQL locking, lease owner/expiry and the frozen generation; stale or lease-lost completion is a no-op.'
  '4. Success, failure and cancellation finalize only from an allowed active state and current generation. An uncertain remote outcome is non-terminal until reconciliation.'
  '5. Delete transitions fence reads/retrieval first and never restore access during cleanup retry. Redaction/invalidation precedes destructive remote/object/local cleanup.'
  '6. Invalid or concurrent transitions return the contracted conflict/error and current safe state where specified; they never queue invisibly or infer success from absence.'
  '7. Public DTO/SSE state is projected from committed server truth. Client optimism is limited to reversible presentation state and must reconcile after every mutation.'
)
assert_ordered_numbered_list "$state_machine_scope" 'state-machine conventions are missing or out of order' "${#required_state_machine_rules[@]}" "${required_state_machine_rules[@]}"
assert_last_nonblank_line "$state_machine_scope" 'The diagrams above define the shared Phase 1 lifecycle vocabulary. Exact transition tables, error codes, retry limits and PostgreSQL race proof land with P3-P7. Existing constants, protocols and state assignments in the lifted code are characterization evidence only until those packages map them to this convention.' 'lifted state-machine completion boundary is missing'

for number in $(seq -w 1 33); do
  drift_count="$(grep -c "^| DRIFT-$number |" docs/brownfield-refactor-register.md || true)"
  [[ "$drift_count" -eq 1 ]] || fail "DRIFT-$number must have exactly one primary row"
done
grep -Fq '### A-13' docs/interaction-behavior-prd.md || fail "surviving A-13 case was removed or renumbered"

if [[ "${1:-}" == '--print-inputs' ]]; then
  {
    for path in "${classified[@]}"; do printf '%s\n' "$path"; done
    printf '%s\n' scripts/check-doc-phase-scope.sh scripts/tests/check-doc-phase-scope.sh
  } | sort -u
elif [[ $# -ne 0 ]]; then
  fail "usage: scripts/check-doc-phase-scope.sh [--print-inputs]"
else
  printf 'phase-scope: PASS (%s governed files)\n' "${#classified[@]}"
fi
