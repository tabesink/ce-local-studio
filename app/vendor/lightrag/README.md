# Vendored LightRAG Runtime

Editable LightRAG source for private Context Engine runtime integration lives here per ADR-002.

- **Status:** promoted from `.references/code/lightrag/` on 2026-07-02
- **Pinned seed version:** LightRAG `1.4.16` (`_version.py`)
- **Edit policy:** surgical changes only; planned KG prompt tweaks belong mainly in `prompt.py`
- **Do not** use pip-only `lightrag-hku` as the runtime source of truth

See `specs/02-architecture/decisions/ADR-002-vendored-lightrag-package.md` and F-005 task `T-060`.
