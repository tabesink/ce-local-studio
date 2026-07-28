# Post-Phase 1 Release Roadmap

This directory preserves approved future intent without expanding the active production build. Release phases and Phase 1 work-package IDs are different concepts: `P0` through `P12` in `master-build-plan.md` are implementation stages inside release Phase 1.

| Release phase | Scope | Planned branch | Status |
| --- | --- | --- | --- |
| Phase 1 | Grounded RAG workstation, governed context, and the minimum operational-safety baseline | current production-build branch | active contract |
| Phase 2 | Operator-facing observability layer: Logs, Usage, and Server status | `feature/observability-layer` | future brief only |
| Phase 3 | Governed wiki publication and contribution layer | `feature/wiki-layer` | future brief only |

Related Phase 1 residual (not a release-phase activation): non-PDF/PPT
governed viewers are sketched in `document-preview-formats.md` and must not
expand Phase 1 routes or `previewKind` until that brief is contracted.

Related unassigned future capability: cloud Bedrock Cohere and private local
text reranking are planned in `reranking-layer.md`. It must not add a Phase 1
profile, provider surface, runtime service, retrieval behavior, or release gate.
ColPali remains outside that initial text-reranking plan because visual
late-interaction retrieval requires its own approved multimodal contract.

Before activation, each future brief is non-normative for every earlier release phase. It creates no earlier-phase schema, DTO, route, component, fixture, test, dependency, estimate, or release gate. A future branch begins only after the preceding release phase is accepted and its own contract and threat model are approved.
